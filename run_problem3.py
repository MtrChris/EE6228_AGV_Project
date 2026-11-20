"""Schedule the two intersecting tracks from Problem 3 and replay the exported visits.

Use the original project's graph and resource-reservation functions. Energy arithmetic
uses integers: one tick of stationary operation costs 1 unit and one moving tick costs 2.
"""
from __future__ import annotations
from argparse import ArgumentParser
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from time import perf_counter
import csv
import json
import sys

TICKS = 100
HEADWAY = 2 * TICKS
CAPACITY = {'unlimited': None, 'eight_hour': 2 * 8 * 3600 * TICKS,
            'per_second': 10000 * TICKS}
CHARGE_DURATION = {'R': 8 * 3600 * TICKS, 'P': 3 * 3600 * TICKS}
DATA = Path(__file__).resolve().parent / 'data'


def fail_if(condition, reason):
    if condition:
        raise ValueError(reason)


def to_ticks(value):
    number = Decimal(str(value)) * TICKS
    fail_if(number != number.to_integral_value(), 'Time exceeds clock resolution')
    return int(number)


def seconds(ticks):
    return ticks / TICKS


def percent(units, capacity):
    return 100.0 if capacity is None else round(100 * units / capacity, 6)


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def problem(core):
    edges = {'R': {}, 'P': {}}
    for r in read_csv(DATA / 'problem3_edges.csv'):
        track = r['track']
        u, v = (track + '_' + r[k] for k in ('from_node','to_node'))
        duration = to_ticks(Decimal(r['length_m']) / Decimal('0.5'))
        core.road(edges[track], u, v, duration, r['direction']=='both')
    tracks = {t: core.Track(t+'_Start', tuple(t+f'_V{i:02d}' for i in range(1,n+1)),
                            edges[t], {t+'_ConflictPoint1':'X1', t+'_ConflictPoint2':'X2'},
                            charger=t+'_ChargingStation1',charge_time=CHARGE_DURATION[t],
                            reserve_depot_junction=True,ticks_per_second=TICKS)
              for t,n in (('R',2),('P',1))}
    jobs = []
    for row in read_csv(DATA / 'appendix_jobs.csv'):
        t = row['track']
        if t not in tracks: continue
        global_id = (200 if t=='R' else 250) + int(row['appendix_row'])
        jobs.append(core.Job('Job-'+str(global_id), t, t+'_'+row['load'],t+'_'+row['unload'],
                             to_ticks(row['release_s']),to_ticks(row['service_s']),deadline=to_ticks(row['deadline_s'])))
    fail_if(Counter(j.track for j in jobs) != {'R':50,'P':50},'Incorrect appendix job counts')
    return tracks, jobs


@dataclass(frozen=True)
class Pattern:
    visits: tuple
    slots: tuple
    loads: tuple
    unloads: tuple
    end: int
    split_cost: tuple   # energy to the charger and energy after charging, or (total, 0)


def scheduler(core, tracks, materials, capacity, policy):
    @lru_cache(maxsize=None)
    def path(t,u,v):
        return core.shortest_path(tracks[t],u,v)

    @lru_cache(maxsize=None)
    def pattern(bundle,charge_first):
        t = bundle[0].track
        track = tracks[t]
        visits = [core.Visit(track.depot,0,0)]
        stops = [(track.charger,'charge','',track.charge_time)] if charge_first else []
        for job in bundle:
            stops.extend(((job.load,'load',job.name,job.duration),(job.unload,'unload',job.name,job.duration)))
        stops.append((track.depot,'pass','',0))
        spent, before = 0, 0
        for destination,action,code,dwell in stops:
            route = path(t,visits[-1].node,destination)
            for u,v in zip(route,route[1:]):
                drive=track.edges[u,v];spent+=2*drive
                arrival=visits[-1].leave+drive
                visits.append(core.Visit(v,arrival,arrival))
            last=visits[-1]
            visits[-1]=replace(last,leave=last.arrive+dwell,action=action,job=code)
            if action=='charge': before,spent=spent,0
            else: spent+=dwell
        loads=tuple(v.arrive for v in visits if v.action=='load')
        unloads=tuple(v.leave for v in visits if v.action=='unload')
        return Pattern(tuple(visits),tuple(core.reservations(track,visits)),loads,unloads,visits[-1].leave,
                       (before,spent) if charge_first else (spent,0))

    calendars=defaultdict(list)
    vehicles=[v for tr in tracks.values() for v in tr.fleet]
    ready={v:0 for v in vehicles}; battery=dict.fromkeys(vehicles,capacity)
    used=Counter(); pending={j.name:j for j in materials}; output=[]
    reserve=(capacity//10) if capacity is not None else 0
    depot_margin={}
    for t,track in tracks.items():
        charge_route=path(t,track.depot,track.charger)
        depot_margin[t]=2*sum(track.edges[u,v] for u,v in zip(charge_route,charge_route[1:]))

    def candidate(bundle,vehicle):
        t=bundle[0].track
        for charge in ((False,True) if capacity is not None else (False,)):
            pat=pattern(bundle,charge)
            start=max(ready[vehicle]+(HEADWAY if used[vehicle] else 0),
                      *(j.release-offset for j,offset in zip(bundle,pat.loads)))
            start=core.first_slot(calendars,pat.slots,start)
            if any(start+end>job.deadline for job,end in zip(bundle,pat.unloads)): continue
            end_soc=None
            if capacity is not None:
                start_soc=battery[vehicle]-(start-ready[vehicle])
                arrival_or_end=start_soc-pat.split_cost[0]
                if arrival_or_end < reserve: continue
                end_soc=capacity-pat.split_cost[1] if charge else arrival_or_end
                # Keep a reachable charger on the next departure, with the two-second headway.
                if end_soc < reserve+depot_margin[t]+HEADWAY: continue
            rank=(bool(used[vehicle]),start+pat.unloads[0],-len(bundle),start+pat.end,vehicle,
                  tuple(job.name for job in bundle))
            return rank,vehicle,pat,start,end_soc,bundle
        return None

    while pending:
        best=None
        ordered=sorted(pending.values(),key=lambda j:(j.release,j.name))
        by_load=defaultdict(list)
        for j in ordered: by_load[j.load].append(j)
        flows=defaultdict(list)
        for j in ordered:
            if len(flows[j.track,j.load,j.unload])<2: flows[j.track,j.load,j.unload].append(j)
        for first in ordered:
            variants=[(first,)]
            if policy=='matched':
                # Pair an unloading at station i with an available loading at station i.
                compatible=by_load[first.unload.replace('_UnloadingStation','_LoadingStation')]
                if compatible: variants.append((first,compatible[0]))
            elif policy=='paired':
                # Test an early-released successor from each station pair on the same track.
                for (track_code,_,_),early in flows.items():
                    if track_code!=first.track: continue
                    other=next((j for j in early if j!=first),None)
                    if other is not None: variants.append((first,other))
            for bundle in variants:
                for vehicle in tracks[first.track].fleet:
                    attempt=candidate(bundle,vehicle)
                    if attempt and (best is None or attempt[0] < best[0]): best=attempt
        if best is None:
            counts = dict(Counter(j.track for j in pending.values()))
            fleet_status = {v: (seconds(ready[v]), percent(battery[v],capacity)) for v in ready}
            raise ValueError(f'No feasible heuristic continuation with {counts} pending. Last returns and battery: {fleet_status}')
        _,vehicle,pat,start,end_soc,bundle=best
        for key,left,right in pat.slots: core.reserve(calendars[key],start+left,start+right)
        output.append((vehicle,used[vehicle]+1,start,pat.visits));used[vehicle]+=1
        ready[vehicle]=start+pat.end;battery[vehicle]=end_soc
        for job in bundle: del pending[job.name]
    return output


def save_visits(directory, schedule, tracks, capacity):
    rows=[]; last_end=Counter(); state={v:capacity for t in tracks.values() for v in t.fleet}
    for vehicle,trip,start,visits in sorted(schedule,key=lambda x:(x[0],x[1])):
        t=vehicle[0]; energy=state[vehicle]
        for i,v in enumerate(visits):
            arrive=start+v.arrive; leave=start+v.leave
            if capacity is not None:
                delta=arrive-last_end[vehicle]
                energy-=delta if i==0 else 2*delta
            after=energy
            if capacity is not None: after=capacity if v.action=='charge' else energy-(leave-arrive)
            rows.append(dict(vehicle=vehicle,track=t,trip=trip,visit=i+1,node=v.node,arrival_s=seconds(arrive),
                             departure_s=seconds(leave),action=v.action,job=v.job,soc_arrival_pct=percent(energy,capacity),
                             soc_departure_pct=percent(after,capacity)))
            last_end[vehicle]=leave; energy=after
        state[vehicle]=energy
    write_csv(directory/'visits.csv',rows)


def verify(directory, tracks, jobs, capacity):
    # Read back the file. No reservations or candidate decisions from the solver are reused.
    inputs={j.name:j for j in jobs}; resource=defaultdict(list); groups=defaultdict(list); joblog={}
    for r in read_csv(directory/'visits.csv'):
        for key in ('arrival_s','departure_s'): r[key]=to_ticks(r[key])
        groups[r['vehicle'],int(r['trip'])].append(r)
    fail_if({v for v,_ in groups} != {v for tr in tracks.values() for v in tr.fleet}, 'Unexpected or missing vehicle')
    metrics={}; crossing_rows=[]; charge_rows=[]; summaries={}; route_lines=[]; resources_min={}
    for t,track in tracks.items():
        for vehicle in track.fleet:
            state=capacity; used_energy=0; lowest=100.; last_end=0; count=trips=charges=0; route=[]
            move_total=idle_total=dwell_total=0
            for key,sequence in sorted(groups.items()):
                if key[0]!=vehicle:continue
                trips+=1
                fail_if(key[1]!=trips,'Trip numbering')
                fail_if(sequence[0]['node']!=track.depot or sequence[-1]['node']!=track.depot,'Depot boundary')
                fail_if(trips>1 and sequence[0]['arrival_s']<last_end+HEADWAY,'Overlapping trips')
                onboard=None; trip_jobs=0
                gap=sequence[0]['arrival_s']-last_end
                fail_if(gap<0,'Negative parking time')
                if route:route[-1][3]=seconds(gap)
                if capacity is not None: state-=gap;used_energy+=gap
                idle_total+=gap
                for i,r in enumerate(sequence):
                    node,action,j=r['node'],r['action'],r['job']; a,d=r['arrival_s'],r['departure_s'];dw=d-a
                    fail_if(r['track']!=t or int(r['visit'])!=i+1 or dw<0,'Visit sequence')
                    if i:
                        prev=sequence[i-1];u=prev['node']; dep=prev['departure_s']; dur=a-dep
                        fail_if(track.edges.get((u,node))!=dur or dur<=0,'Travel time or direction')
                        resource[('edge',*sorted((u,node)))].append((dep,a,vehicle))
                        if capacity is not None: state-=2*dur;used_energy+=2*dur
                        move_total+=dur
                    before=percent(state,capacity);lowest=min(lowest,before)
                    fail_if(capacity is not None and state < capacity//10,'Reserve breached on arrival')
                    fail_if(abs(float(r['soc_arrival_pct'])-before)>0.000001,'Arrival energy')
                    physical_node=track.cross.get(node,node)
                    resource[('node',physical_node)].append((a,d+HEADWAY,vehicle))
                    if physical_node in ('X1','X2'):
                        crossing_rows.append(dict(crossing=physical_node,vehicle=vehicle,trip=trips,
                                                  entry_s=seconds(a),free_s=seconds(d+HEADWAY)))
                    if action=='charge':
                        fail_if(capacity is None or node!=track.charger or dw!=CHARGE_DURATION[t] or j,'Charge stop')
                        charges+=1;state=capacity
                        charge_rows.append(dict(vehicle=vehicle,trip=trips,node=node,start_s=seconds(a),
                                                end_s=seconds(d),arrival_pct=before,departure_pct=100))
                    elif action in ('load','unload'):
                        fail_if(j not in inputs or inputs[j].track!=t,'Unknown job')
                        job=inputs[j];fail_if(dw!=job.duration,'Service time')
                        if action=='load':
                            fail_if(onboard is not None or j in joblog or node!=job.load or a<job.release,'Illegal pickup')
                            onboard=(j,a)
                        else:
                            fail_if(not onboard or onboard[0]!=j or node!=job.unload or d>job.deadline,'Illegal delivery')
                            joblog[j]=dict(job=j,track=t,appendix_row=int(j[4:])-(200 if t=='R' else 250),
                                           vehicle=vehicle,trip=trips,load_node=job.load,unload_node=job.unload,
                                           release_s=seconds(job.release),deadline_s=seconds(job.deadline),load_start_s=seconds(onboard[1]),unload_end_s=seconds(d))
                            onboard=None;count+=1;trip_jobs+=1
                        if capacity is not None:state-=dw;used_energy+=dw
                        dwell_total+=dw
                    else:fail_if(action!='pass' or dw or j,'Unexpected waypoint action')
                    after=percent(state,capacity);lowest=min(lowest,after)
                    fail_if(capacity is not None and state < capacity//10,'Battery below reserve')
                    fail_if(abs(float(r['soc_departure_pct'])-after)>0.000001,'Departure energy')
                    if trips==1 or i>0:
                        arrival_for_txt=0 if trips==1 and i==0 else seconds(a)
                        wait=seconds(a) if trips==1 and i==0 else 0
                        energy_for_txt=100 if trips==1 and i==0 else before
                        route.append([vehicle,arrival_for_txt,node,wait,seconds(dw) if action=='charge' else 0,
                                      energy_for_txt,j or '-1',seconds(d) if j else -1])
                fail_if(trip_jobs==0 or onboard,'Trip without a completed job or returns loaded')
                last_end=sequence[-1]['departure_s']
            fail_if(not count,'Unused vehicle')
            metrics[vehicle]=dict(jobs=count,trips=trips,charges=charges,home_s=seconds(last_end),
                                  motion_s=seconds(move_total),parked_s=seconds(idle_total),service_s=seconds(dwell_total),
                                  min_soc_pct=lowest if capacity else None,energy_pp=percent(used_energy,capacity) if capacity else None)
            route_lines.append(vehicle+': {'+'; '.join('['+','.join(map(str,x))+']' for x in route)+'}')
    for key,periods in resource.items():
        previous={};gap=None
        for a,b,vehicle in sorted(periods):
            for other,end in previous.items():
                if other!=vehicle:
                    fail_if(end>a,f'Collision on {key} between {other} and {vehicle}')
                    if key[0]=='node' and key[1] in ('X1','X2') and other[0]!=vehicle[0]:
                        gap=a-end+HEADWAY if gap is None else min(gap,a-end+HEADWAY)
            previous[vehicle]=max(previous.get(vehicle,0),b)
        if gap is not None:resources_min[key[1]]=seconds(gap)
    fail_if(set(joblog)!=set(inputs),'Task coverage mismatch')
    for t in tracks:
        key=[row['unload_end_s'] for row in joblog.values() if row['track']==t]
        summaries[t]={'jobs':len(key),'makespan_s':max(key)}
    write_csv(directory/'job_schedule.csv',[joblog[j.name] for j in jobs]);write_csv(directory/'crossings.csv',sorted(crossing_rows,key=lambda q:q['entry_s']))
    if charge_rows:write_csv(directory/'charging.csv',sorted(charge_rows,key=lambda q:q['start_s']))
    elif (directory/'charging.csv').exists():(directory/'charging.csv').unlink()
    (directory/'agv_routes.txt').write_text('\n'.join(route_lines)+'\n',encoding='utf-8')
    return dict(tracks=summaries,vehicles=metrics,crossing_passages=dict(Counter(x['crossing'] for x in crossing_rows)),
                minimum_cross_track_separation_s=resources_min,material_makespan_s=max(x['unload_end_s'] for x in joblog.values()),
                last_home_s=max(x['home_s'] for x in metrics.values()),validation='PASS')


def main():
    p=ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True,
                        help='Root of MtrChris/EE6228_AGV_Project at commit 5d0ec287')
    p.add_argument('--out',type=Path,default=Path('problem3_results'))
    p.add_argument('--power',choices=list(CAPACITY),nargs='+',default=list(CAPACITY))
    p.add_argument('--policy',choices=['single','matched','paired'],nargs='+',default=['single','paired'])
    args=p.parse_args();sys.path.insert(0,str(args.project.resolve()/'demo'));import agv_core as core
    tracks,jobs=problem(core)
    for mode in args.power:
        for policy in args.policy:
            out=args.out/(mode+'_'+policy);out.mkdir(parents=True,exist_ok=True)
            start=perf_counter()
            try:schedule=scheduler(core,tracks,jobs,CAPACITY[mode],policy)
            except ValueError as exc:
                if 'No feasible heuristic continuation' not in str(exc):raise
                for name in ('visits.csv','job_schedule.csv','charging.csv','agv_routes.txt','crossings.csv'):
                    (out/name).unlink(missing_ok=True)
                result={'power':mode,'policy':policy,'validation':'no schedule','detail':str(exc),'solve_s':round(perf_counter()-start,4)}
            else:
                elapsed=perf_counter()-start
                save_visits(out,schedule,tracks,CAPACITY[mode]);result=verify(out,tracks,jobs,CAPACITY[mode]);result.update(power=mode,policy=policy,solve_s=round(elapsed,4))
            (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            print(mode,policy,result.get('material_makespan_s'),result.get('tracks'),result.get('solve_s'),result.get('detail',''),flush=True)

if __name__=='__main__':main()
