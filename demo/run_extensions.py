"""Run the full Yellow appendix on the Fig. 1 reconstruction and the Red/Purple smoke test."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from time import perf_counter
import csv

from agv_core import (Job, Manual, ScheduleError, Track, Trip, Visit, dispatch,
                      fixtures, require, road, validate)
from run_demo import write_csv, write_json, write_route_txt


# Problem statement -2, Appendix 1, in printed order.
YELLOW_RELEASES = tuple(map(int, """
1607 2885 1509 1368 2982 1569 3122 802 300 2424
993 2290 2025 2315 1486 3221 2361 2069 715 1792
3010 1746 80 410 1200 206 3537 2267 1798 1777
800 1953 419 3525 2511 2799 541 292 916 1107
615 821 1949 2165 2463 1170 2792 3372 8 1873
757 2944 3365 3108 1999 31 1661 1146 1165 586
3051 2455 2737 2026 964 199 2840 2127 2595 1837
1599 1741 977 239 2304 1918 1640 2727 280 2649
518 2997 914 1463 1975 224 574 1018 1671 751
3405 205 355 3384 477 1961 1938 393 310 231
""".split()))


def yellow_fixture(bottom_edge_m):
    # Six labeled sides on the loop plus two depot links are read from Fig. 1.
    # The unlabeled T1 -> T2 edge uses the supplied assumption, not a measured distance.
    edges = {}
    for source, target, metres, two_way in (
        ("Start", "LoadingStation1", "6.85", True),
        ("LoadingStation1", "T1", "16.6", True),
        ("T1", "T2", bottom_edge_m, False),
        ("T2", "UnloadingStation1", "23.95", False),
        ("UnloadingStation1", "Pick-upStation1", "6.7", False),
        ("Pick-upStation1", "T3", "3.2", False),
        ("T3", "T4", "41.6", False),
        ("T4", "ReturnStation1", "26.1", False),
        ("ReturnStation1", "T1", "7.75", False),
    ):
        ticks = Decimal(metres) * 20  # 0.5 m/s with tenth-second ticks.
        require(ticks > 0 and ticks == int(ticks), "Yellow edge length must be a positive multiple of 0.05 m")
        road(edges, f"Y_{source}", f"Y_{target}", int(ticks), two_way)
    track = Track("Y_Start", ("Y_V01", "Y_V02"), edges, {}, reserve_depot_junction=True,
                  ticks_per_second=10, cart_nodes=("Y_Pick-upStation1", "Y_ReturnStation1"))
    materials = [Job(f"Job-{index}", "Y", "Y_LoadingStation1", "Y_UnloadingStation1",
                     release * 10, 160, deadline=999990)
                 for index, release in enumerate(YELLOW_RELEASES, 1)]
    return {"Y": track}, materials


def export_case(directory, tracks, materials, *, initial_carts=0, bundle_yellow=True):
    start = perf_counter()
    trips, moves, jobs, carts = dispatch(tracks, materials, initial_carts, bundle_yellow=bundle_yellow)
    elapsed = perf_counter() - start
    timing = validate(tracks, materials, trips, moves, jobs, carts, initial_carts)
    scale = next(iter(tracks.values())).ticks_per_second

    def seconds(ticks):
        return ticks if scale == 1 else ticks / scale

    def ticks(value):
        decoded = Decimal(value) * scale
        require(decoded == int(decoded), "time does not match the track clock resolution")
        return int(decoded)

    def battery(value):
        return None if value == "" else int(value)

    directory.mkdir(parents=True, exist_ok=True)
    trip_count = Counter()
    vehicle_jobs = defaultdict(Counter)
    energy = Counter()
    assignments = {}
    visit_rows = []
    by_car = defaultdict(list)
    ordered = sorted(trips, key=lambda trip: (trip.vehicle, trip.visits[0].arrive))
    for trip in ordered:
        by_car[trip.vehicle].append(trip)
        trip_count[trip.vehicle] += 1
        track = tracks[trip.track]
        for number, visit in enumerate(trip.visits, 1):
            visit_rows.append((trip.vehicle, trip.track, trip_count[trip.vehicle], number, visit.node,
                               seconds(visit.arrive), seconds(visit.leave), visit.action, visit.job,
                               visit.battery, trip.end_battery))
            if visit.action == "unload":
                assignments[visit.job] = trip.vehicle
                vehicle_jobs[trip.vehicle]["carts" if jobs[visit.job].cart else "materials"] += 1
        if track.charger:
            move_ticks = sum(b.arrive - a.leave for a, b in zip(trip.visits, trip.visits[1:]))
            service_ticks = sum(v.leave - v.arrive for v in trip.visits if v.action in ("load", "unload"))
            energy[trip.vehicle] += move_ticks * track.moving_rate + service_ticks * track.service_rate

    visits_file = directory / "visits.csv"
    move_file = directory / "manual_transfers.csv"
    route_job_names = {f"Return-{job.name}": f"Job-{len(materials) + index}"
                       for index, job in enumerate(materials, 1)} if initial_carts else {}
    write_route_txt(directory / "agv_routes.txt", by_car, scale, route_job_names)
    write_csv(visits_file, ["vehicle", "track", "trip", "visit", "node", "arrival_s", "departure_s",
                            "action", "job", "battery_basis_points", "trip_end_battery_basis_points"], visit_rows)
    write_csv(move_file, ["job", "cart_id", "operator", "start_s", "drop_s", "free_s"],
              ((m.job, m.cart_id, m.operator, seconds(m.start), seconds(m.drop), seconds(m.free)) for m in moves))
    write_csv(directory / "job_schedule.csv",
              ["job", "vehicle", "load_node", "unload_node", "release_s", "deadline_s", "load_start_s",
               "unload_end_s", "cart_id", "kind", "route_job"],
              ((j.name, assignments[j.name], j.load, j.unload, seconds(j.release), seconds(j.deadline),
                *map(seconds, timing[j.name]), carts.get(j.name), "cart" if j.cart else "material",
                route_job_names.get(j.name, j.name))
               for j in jobs.values()))

    groups = defaultdict(list)
    ends = {}
    with visits_file.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["vehicle"], row["track"], row["trip"])
            visits = groups[key]
            require(int(row["visit"]) == len(visits) + 1, "unordered visit index")
            visits.append(Visit(row["node"], ticks(row["arrival_s"]), ticks(row["departure_s"]),
                                row["action"], row["job"], battery(row["battery_basis_points"])))
            ends[key] = battery(row["trip_end_battery_basis_points"])
    restored = [Trip(key[0], key[1], tuple(visits), tuple(v.job for v in visits if v.action == "load"), ends[key])
                for key, visits in groups.items()]
    with move_file.open(encoding="utf-8", newline="") as stream:
        transfers = [Manual(r["job"], int(r["cart_id"]), int(r["operator"]),
                            ticks(r["start_s"]), ticks(r["drop_s"]), ticks(r["free_s"]))
                     for r in csv.DictReader(stream)]
    require(restored == ordered and transfers == moves, "extension export differs from schedule")
    require(validate(tracks, materials, restored, transfers, jobs, carts, initial_carts) == timing,
            "extension export job timing differs")

    if initial_carts:
        return_name = next(name for name, job in jobs.items() if job.cart)
        corrupt = dict(jobs)
        corrupt[return_name] = replace(jobs[return_name], cart=False)
        try:
            validate(tracks, materials, restored, transfers, corrupt, carts, initial_carts)
        except ScheduleError as error:
            require("empty cart job metadata mismatch" in str(error), "wrong return-job validation failure")
        else:
            raise ScheduleError("invalid empty cart type accepted")

    stats = {
        "tracks": {name: {"material_jobs": sum(j.track == name and not j.cart for j in jobs.values()),
                          "cart_jobs": sum(j.track == name and j.cart for j in jobs.values()),
                          "material_makespan_s": seconds(max(timing[j.name][1] for j in materials if j.track == name)),
                          "all_jobs_makespan_s": seconds(max(timing[j.name][1] for j in jobs.values() if j.track == name))}
                   for name in tracks},
        "last_home_s": seconds(max(t.visits[-1].leave for t in restored)),
        "last_manual_delivery_s": seconds(max((m.drop for m in transfers), default=0)) if transfers else None,
        "trips": len(restored),
        "multi_job_trips": sum(len(t.jobs) > 1 for t in restored),
        "vehicle_jobs": {vehicle: dict(counts) for vehicle, counts in vehicle_jobs.items()},
        "manual_transfers": len(transfers),
        "charge_events": sum(v.action == "charge" for t in restored for v in t.visits),
        "operation_consumption_pct_points": {vehicle: value / 100 for vehicle, value in energy.items()},
        "solve_seconds": round(elapsed, 4),
        "visits_csv_validation": "PASS",
    }
    write_json(directory / "summary.json", stats)
    return stats


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("results") / "extensions")
    parser.add_argument("--yellow-bottom-edge-m", type=Decimal, default=Decimal("41.6"))
    options = parser.parse_args()
    yellow, materials = yellow_fixture(options.yellow_bottom_edge_m)
    tracks, demo_jobs, _ = fixtures()
    results = {"yellow_assumed_T1_T2_m": float(options.yellow_bottom_edge_m)}
    for name, tandem in (("yellow_separate", False), ("yellow_tandem", True)):
        results[name] = export_case(options.out / name, yellow, materials, initial_carts=8, bundle_yellow=tandem)
    results["red_purple_smoke_test"] = export_case(options.out / "red_purple_smoke_test",
                                                  {name: tracks[name] for name in ("R", "P")},
                                                  [job for job in demo_jobs if job.track in ("R", "P")])
    summary = options.out / "summary.json"
    write_json(summary, results)
    print(summary.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
