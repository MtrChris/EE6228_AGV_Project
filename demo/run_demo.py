"""Re-run the green-track study and regenerate the standalone replay."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from time import perf_counter
import csv
import json

from agv_core import Trip, Visit, dispatch, fixtures, require, validate, ScheduleError

SHARED = {"G_T1", "G_UnloadingStation2"}
POLICIES = {
    "baseline": (False, "original"),
    "paired": (True, "original"),
    "work_rate": (True, "work_rate"),
    "mean_completion": (True, "balanced_completion"),
}

def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_route_txt(path, by_car, scale=1, route_job_names=None):
    """Write the course appendix's eight fields using the team's depot-wait convention."""
    route_job_names = route_job_names or {}

    def seconds(ticks):
        return ticks if scale == 1 else ticks / scale

    lines = []
    for car, trips in sorted(by_car.items()):
        trips = sorted(trips, key=lambda trip: trip.visits[0].arrive)
        route = []
        for index, trip in enumerate(trips):
            for number, visit in enumerate(trip.visits):
                if index > 0 and number == 0:
                    continue
                arrival = 0 if number == index == 0 else visit.arrive
                wait = visit.leave - arrival if visit.action == "pass" else 0
                if number == len(trip.visits) - 1 and index + 1 < len(trips):
                    wait = trips[index + 1].visits[0].arrive - visit.leave
                charge = visit.leave - visit.arrive if visit.action == "charge" else 0
                energy = 100 if visit.battery is None else visit.battery / 100
                job = route_job_names.get(visit.job, visit.job) or "-1"
                completion = seconds(visit.leave) if visit.job else -1
                route.append(f"[{car},{seconds(arrival)},{visit.node},{seconds(wait)},"
                             f"{seconds(charge)},{energy},{job},{completion}]")
        lines.append(f"{car}: {{" + "; ".join(route) + "}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect(trips, timing):
    cars = defaultdict(list)
    done, road, pairs = [], [], []
    drive = 0
    for trip in trips:
        visits = trip.visits
        cars[trip.vehicle].append([[v.node, v.arrive, v.leave, v.action, v.job] for v in visits])
        done.extend([v.leave, v.job, trip.vehicle] for v in visits if v.action == "unload")
        for left, right in zip(visits, visits[1:]):
            drive += right.arrive - left.leave
            if {left.node, right.node} == SHARED:
                road.append([left.leave, right.arrive, trip.vehicle, left.node, right.node])
        if len(trip.jobs) == 2:
            first_unload = next(v for v in visits if v.action == "unload")
            second_load = next(v for v in visits if v.action == "load" and v.job == trip.jobs[1])
            pairs.append([first_unload.leave, second_load.arrive, trip.vehicle, *trip.jobs,
                          first_unload.node, second_load.node])
    for sequences in cars.values():
        sequences.sort(key=lambda sequence: sequence[0][1])
    road.sort()
    done.sort()
    require(len(done) == len(timing) == 100, "green replay task count")
    require(all(a[1] <= b[0] for a, b in zip(road, road[1:])), "shared-edge replay overlap")
    handoffs = [(a, b) for a, b in zip(road, road[1:])
                if a[2] != b[2] and a[3] == b[4] and b[0] - a[1] <= 12]
    return {
        "cars": dict(sorted(cars.items())), "done": done, "road": road, "finish": done[-1][0],
        "home": max(q.visits[-1].leave for q in trips), "trips": len(trips), "drive": drive,
        "pairs": len(pairs), "clips": {"road": handoffs[0] if handoffs else None,
                                       "pair": min(pairs) if pairs else None},
    }

def read_visits(path):
    visits = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["vehicle"], int(row["trip"]))
            require(int(row["visit"]) == len(visits[key]) + 1, "unordered visit index")
            visits[key].append(Visit(row["node"], int(row["arrival_s"]), int(row["departure_s"]),
                                     row["action"], row["job"]))
    return [Trip(vehicle, "G", tuple(seq), tuple(v.job for v in seq if v.action == "load"), None)
            for (vehicle, _), seq in visits.items()]

def export_case(directory, trips, timing, tracks, materials):
    directory.mkdir(parents=True, exist_ok=True)
    by_car = defaultdict(list)
    job_car = {}
    for trip in trips:
        by_car[trip.vehicle].append(trip)
        job_car.update({j: trip.vehicle for j in trip.jobs})
    visit_rows = []
    for car, car_trips in sorted(by_car.items()):
        car_trips.sort(key=lambda trip: trip.visits[0].arrive)
        for k, trip in enumerate(car_trips, 1):
            for n, visit in enumerate(trip.visits, 1):
                visit_rows.append([car,k,n,visit.node,visit.arrive,visit.leave,visit.action,visit.job])
    write_route_txt(directory / "agv_routes.txt", by_car)
    fields = ["vehicle","trip","visit","node","arrival_s","departure_s","action","job"]
    visit_path = directory / "visits.csv"
    write_csv(visit_path, fields, visit_rows)
    write_csv(directory / "job_schedule.csv",
              ["job","vehicle","load_node","unload_node","release_s","deadline_s","load_start_s","unload_end_s"],
              ([j.name,job_car[j.name],j.load,j.unload,j.release,j.deadline,*timing[j.name]] for j in materials))
    restored = read_visits(visit_path)
    observed = validate(tracks, materials, restored, [], {j.name:j for j in materials}, {}, 0)
    require(observed == timing, "round-trip job timing differs")
    return restored

def probe_validator(tracks, materials, trips):
    jobs = {j.name:j for j in materials}
    def reject(items, expected):
        try:
            validate(tracks, materials, items, [], jobs, {}, 0)
        except ScheduleError as exc:
            require(expected in str(exc), f"wrong validation failure: {exc}")
            return str(exc)
        raise ScheduleError("invalid schedule accepted")
    missed = reject(trips[1:], "missing or unexpected job")
    trip = trips[0]
    shifted = replace(trip.visits[1], arrive=trip.visits[1].arrive + 1)
    bad = replace(trip, visits=(trip.visits[0], shifted, *trip.visits[2:]))
    edge = reject([bad, *trips[1:]], "illegal edge or travel duration")
    return {"remove_trip":missed,"alter_travel_time":edge}

def main():
    parser = ArgumentParser(description=__doc__)
    demo = Path(__file__).resolve().parent
    parser.add_argument("--out", type=Path, default=demo / "results")
    parser.add_argument("--html", type=Path, default=demo.parent / "replay" / "EE6228_AGV_Replay.html")
    options = parser.parse_args()
    base_tracks, all_jobs, _ = fixtures()
    materials = [j for j in all_jobs if j.track == "G"]
    options.out.mkdir(parents=True, exist_ok=True)
    results, checks = [], {}
    replay = {"edges": [[u,v,s] for (u,v),s in base_tracks["G"].edges.items()], "rules": {}}
    for rule, junction in [("original",False), ("junction",True)]:
        track = replace(base_tracks["G"], reserve_depot_junction=junction)
        tracks = {"G":track}
        cases = {}
        for name, (bundle, scoring) in POLICIES.items():
            start = perf_counter()
            trips, moves, jobs, cart_ids = dispatch(tracks, materials, bundle_green=bundle, scoring=scoring)
            elapsed = perf_counter() - start
            timing = validate(tracks, materials, trips, moves, jobs, cart_ids, 0)
            directory = options.out / rule / name
            restored = export_case(directory, trips, timing, tracks, materials)
            original_data, restored_data = collect(trips,timing), collect(restored,timing)
            require(original_data == restored_data, "replay differs from exported visits")
            cases[name] = restored_data
            if rule == "original" and name == "baseline":
                legacy_baseline = restored
            if rule == "junction" and name == "baseline":
                try:
                    validate(tracks, materials, legacy_baseline, [], {j.name:j for j in materials}, {}, 0)
                except ScheduleError as error:
                    require("node/crossing conflict at G_Start" in str(error), "unexpected cross-rule failure")
                    checks["original_baseline_under_junction"] = str(error)
                else:
                    raise ScheduleError("original baseline should fail the public Start reservation check")
            stats = {"rule":rule,"policy":name,"jobs":len(timing),
                     "makespan_s":restored_data["finish"],"last_home_s":restored_data["home"],
                     "trips":restored_data["trips"],"paired_trips":restored_data["pairs"],
                     "drive_s":restored_data["drive"],"shared_passes":len(restored_data["road"]),
                     "vehicle_jobs":dict(sorted(Counter(x[2] for x in restored_data["done"]).items())),
                     "solve_seconds":round(elapsed,4),"visits_csv_validation":"PASS"}
            results.append(stats)
            write_json(directory / "summary.json", stats)
            if name == "paired":
                checks[rule] = probe_validator(tracks,materials,restored)
        best = min(cases, key=lambda name: (cases[name]["finish"], cases[name]["home"], cases[name]["drive"], name))
        replay["rules"][rule] = {"cases":cases,"best":best}
    fields = [k for k in results[0] if k != "vehicle_jobs"]
    write_csv(options.out / "comparison.csv", fields, ([row[key] for key in fields] for row in results))
    write_json(options.out / "summary.json",
               {"cases":results, "best_by_rule":{key:val["best"] for key,val in replay["rules"].items()},
                "validation_probes":checks})
    template = Path(__file__).with_name("replay_template.html").read_text(encoding="utf-8")
    options.html.parent.mkdir(parents=True, exist_ok=True)
    options.html.write_text(template.replace("__EVENTS__",json.dumps(replay,separators=(",",":"))),encoding="utf-8")
    print((options.out / "comparison.csv").read_text(encoding="utf-8"))

if __name__ == "__main__":
    main()
