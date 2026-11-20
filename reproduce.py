"""Rebuild the published tables and factory exports without writing to the base project."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys

import run_problem3 as rp

HERE=Path(__file__).resolve().parent
BASE='5d0ec287ad7a9682363f5dcb63975bacd235df21'

def read_json(p): return json.loads(p.read_text(encoding='utf-8'))
def save_json(p,d): p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
def run(cmd): subprocess.run([str(x) for x in cmd],check=True)
def ensure(x,msg):
    if not x:raise ValueError(msg)


def build_factory(out, original, red_dir):
    target=out/'factory';target.mkdir(exist_ok=True)
    appendix={(r['track'],int(r['appendix_row'])):r for r in rp.read_csv(HERE/'data/appendix_jobs.csv')}
    joined=[];route_lines=[];route_events=defaultdict(list);station_dwell={}
    # Numbers 1-300 are the Green, Yellow, Red and Purple appendix rows in that order.
    # Numbers 301-400 refer to generated Yellow cart tasks.
    for scenario,folder in [('G',original/'junction/paired'),('Y',original/'extensions/yellow_tandem'),('RP',red_dir)]:
        def gid(raw):
            n=int(raw[4:]);return n if scenario!='Y' else n+100 if n<=100 else n+200
        for r in rp.read_csv(folder/'job_schedule.csv'):
            track=r['vehicle'][0];num=gid(r.get('route_job',r['job']));generated=num>300
            index=num-(300 if generated else {'G':0,'Y':100,'R':200,'P':250}[track]);src=appendix[track,index]
            if not generated:
                ensure(r['load_node']==track+'_'+src['load'] and r['unload_node']==track+'_'+src['unload'] and
                       Decimal(r['release_s'])==Decimal(src['release_s']) and Decimal(r['deadline_s'])==Decimal(src['deadline_s']),f'Appendix mismatch on {track} row {index}')
            station_dwell[num]=16 if generated else int(src['service_s'])
            joined.append(dict(global_job=f'Job-{num}',track=track,appendix_row=index if not generated else '',
                source_material_job='Job-'+str(100+index) if generated else '',kind='cart' if generated else 'material',
                vehicle=r['vehicle'],load_node=r['load_node'],unload_node=r['unload_node'],release_s=r['release_s'],
                deadline_s=r['deadline_s'],load_start_s=r['load_start_s'],unload_end_s=r['unload_end_s'],cart_id=r.get('cart_id','')))
        for line in (folder/'agv_routes.txt').read_text().splitlines():
            vehicle,payload=line.split(':',1);new=[]
            for entry in re.findall(r'\[([^\]]+)\]',payload):
                fields=entry.split(',');ensure(len(fields)==8 and fields[0]==vehicle and ' ' not in fields[2], 'Route TXT format')
                if fields[6]!='-1':
                    n=gid(fields[6]);fields[6]='Job-'+str(n)
                    route_events[n].append((vehicle,fields[2],Decimal(fields[7])))
                new.append('['+','.join(fields)+']')
            ensure(new and '_Start,' in new[0] and '_Start,' in new[-1], 'Missing depot visit')
            route_lines.append(vehicle+': {'+'; '.join(new)+'}')
    joined.sort(key=lambda r:int(r['global_job'][4:]))
    ensure([r['global_job'] for r in joined]==['Job-'+str(i) for i in range(1,401)],'Incomplete 400-job manifest')
    ensure(set(route_events)==set(range(1,401)) and len(route_lines)==8,'Unexpected dispatch output')
    for r in joined:
        n=int(r['global_job'][4:]);x=route_events[n]
        ensure(x==[(r['vehicle'],r['load_node'],Decimal(r['load_start_s'])+station_dwell[n]),
                   (r['vehicle'],r['unload_node'],Decimal(r['unload_end_s']))],f'Route TXT/CSV mismatch for Job-{n}')
    rp.write_csv(target/'job_schedule.csv',joined)
    (target/'agv_routes.txt').write_text('\n'.join(route_lines)+'\n',encoding='utf-8')
    material=[r for r in joined if r['kind']=='material']; red=read_json(red_dir/'summary.json'); y=read_json(original/'extensions/yellow_tandem/summary.json');g=read_json(original/'junction/paired/summary.json')
    totals={t:max(float(r['unload_end_s']) for r in material if r['track']==t) for t in 'GYRP'}
    result={'appendix_material_jobs':len(material),'generated_yellow_returns':len(joined)-len(material),'vehicles':len(route_lines),
            'material_makespan_s':max(totals.values()),'all_agv_jobs_makespan_s':max(float(r['unload_end_s']) for r in joined),
            'last_agv_home_s':max(g['last_home_s'],y['last_home_s'],red['last_home_s']),'last_manual_delivery_s':y['last_manual_delivery_s'],
            'track_material_makespan_s':totals,'workload_material':dict(Counter(r['vehicle'] for r in material)),
            'selected_cases':['junction/paired','yellow_tandem, 41.6 m','per_second_paired'],'source_job_fields':'PASS','txt_vs_csv_events':sum(len(e) for e in route_events.values())}
    save_json(target/'summary.json',result);return result


def main():
    parser=ArgumentParser(description=__doc__);parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=HERE/'results');args=parser.parse_args()
    project=args.project.resolve();base=project/'demo';out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    original=out/'upstream/demo/results';page=out/'upstream/replay/EE6228_AGV_Replay.html'
    run([sys.executable,base/'run_demo.py','--out',original,'--html',page]);run([sys.executable,base/'run_extensions.py','--out',original/'extensions'])
    replay_state='Node.js not available'
    if shutil.which('node'):
        checker=original.parent/'check_replay.cjs';shutil.copyfile(base/'check_replay.cjs',checker)
        try:run(['node',checker]);replay_state='PASS'
        finally:checker.unlink(missing_ok=True)
    sys.path.insert(0,str(base));import run_extensions as ext
    sensitivity=[]
    for length in ['33.6','41.6','49.6']:
        tracks,jobs=ext.yellow_fixture(Decimal(length))
        for key,pair in [('yellow_separate',False),('yellow_tandem',True)]:
            stats=(read_json(original/'extensions'/key/'summary.json') if length=='41.6' else
                   ext.export_case(out/'length_sensitivity'/length/key,tracks,jobs,initial_carts=8,bundle_yellow=pair))
            c=stats['tracks']['Y'];sensitivity.append(dict(length_m=length,policy=key,
                material_makespan_s=c['material_makespan_s'],all_agv_jobs_s=c['all_jobs_makespan_s'],
                trips=stats['trips'],paired_trips=stats['multi_job_trips'],wall_s=stats['solve_seconds']))
    (out/'length_sensitivity').mkdir(exist_ok=True);rp.write_csv(out/'length_sensitivity'/'comparison.csv',sensitivity)
    run([sys.executable,HERE/'run_problem3.py','--project',project,'--out',out/'problem3'])
    factory=build_factory(out,original,out/'problem3/per_second_paired')
    try:sha=subprocess.check_output(['git','-C',str(project),'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):sha=None
    cpu=platform.processor() or platform.machine()
    if Path('/proc/cpuinfo').is_file():
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):cpu=line.split(':',1)[1].strip();break
    save_json(out/'environment.json',dict(base_commit=sha,pin=BASE,os=platform.platform(),python=platform.python_version(),cpu=cpu,
                   visible_cpus=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count(),replay_validation=replay_state))
    print(json.dumps(factory,indent=2))

if __name__=='__main__':main()
