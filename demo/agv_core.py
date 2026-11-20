"""Core adapted from the team demo. Run experiments with run_demo.py."""

from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from heapq import heappop, heappush


HEADWAY = 2
MANUAL_TRAVEL = 480
MANUAL_CYCLE = 960
MIN_BATTERY = 1000  # Battery is stored in hundredths of a percentage point.
FULL_BATTERY = 10000


@dataclass(frozen=True)
class Job:
    name: str
    track: str
    load: str
    unload: str
    release: int
    duration: int = 16
    cart: bool = False
    deadline: int = 99999


@dataclass(frozen=True)
class Visit:
    node: str
    arrive: int
    leave: int
    action: str = "pass"
    job: str = ""
    battery: int | None = None  # At arrival, before service or charging.


@dataclass
class Track:
    depot: str
    fleet: tuple
    edges: dict
    cross: dict
    charger: str = ""
    charge_time: int = 0
    moving_rate: int = 0
    service_rate: int = 0
    reserve_depot_junction: bool = False
    ticks_per_second: int = 1
    cart_nodes: tuple = ("Y_Pickup", "Y_Return")

    @property
    def headway(self):
        return HEADWAY * self.ticks_per_second


@dataclass(frozen=True)
class Trip:
    vehicle: str
    track: str
    visits: tuple
    jobs: tuple
    end_battery: int | None


@dataclass(frozen=True)
class Manual:
    job: str
    cart_id: int
    operator: int
    start: int
    drop: int
    free: int


class ScheduleError(Exception):
    pass


def require(condition, detail):
    if not condition:
        raise ScheduleError(detail)


def shortest_path(track, source, target):
    queue = [(0, source, (source,))]
    seen = set()
    while queue:
        distance, node, path = heappop(queue)
        if node in seen:
            continue
        if node == target:
            return path
        seen.add(node)
        for (start, end), duration in track.edges.items():
            if start == node and end not in seen:
                heappush(queue, (distance + duration, end, path + (end,)))
    raise ScheduleError(f"No path from {source} to {target}")


def reservations(track, visits):
    """Reserve road resources and optionally every instantaneous Start crossing."""
    for visit in visits:
        if visit.node != track.depot or track.reserve_depot_junction:
            resource = track.cross.get(visit.node, visit.node)
            yield ("node", resource), visit.arrive, visit.leave + track.headway
    for left, right in zip(visits, visits[1:]):
        # Exclusive occupancy also on one-way edges is a conservative no-passing rule.
        edge = tuple(sorted((left.node, right.node)))
        yield ("edge", edge), left.leave, right.arrive


def first_slot(book, slots, start):
    """Shift a whole trip right until none of its resources overlaps a booking."""
    while True:
        after_conflicts = start
        for key, left, right in slots:
            calendar = book[key]
            index = bisect_left(calendar, (start + right,)) - 1
            if index >= 0 and calendar[index][1] > start + left:
                after_conflicts = max(after_conflicts, calendar[index][1] - left)
        if after_conflicts == start:
            return start
        start = after_conflicts


def reserve(calendar, start, end):
    """Keep the occupied intervals sorted and merge touching or overlapping bookings."""
    index = bisect_left(calendar, (start,))
    if index > 0 and calendar[index - 1][1] >= start:
        index -= 1
        start = calendar[index][0]
    stop = index
    while stop < len(calendar) and calendar[stop][0] <= end:
        end = max(end, calendar[stop][1])
        stop += 1
    calendar[index:stop] = [(start, end)]


def make_trip(track_name, track, vehicle, jobs, free, battery, cart_ready, book, paths):
    actions = []
    for job in jobs:
        actions.extend(((job.load, "load", job.name, job.duration),
                        (job.unload, "unload", job.name, job.duration)))
    actions.append((track.depot, "pass", "", 0))

    def build(stop_at_charger):
        visits = [Visit(track.depot, 0, 0, battery=battery)]
        remaining = battery
        stops = actions
        if stop_at_charger:
            stops = [(track.charger, "charge", "", track.charge_time), *actions]
        for node, action, name, dwell in stops:
            path = paths.get((track_name, visits[-1].node, node))
            if path is None:
                return None
            for source, target in zip(path, path[1:]):
                duration = track.edges[source, target]
                arrival = visits[-1].leave + duration
                if remaining is not None:
                    remaining -= duration * track.moving_rate
                    if remaining < MIN_BATTERY:
                        return None
                visits.append(Visit(target, arrival, arrival, battery=remaining))
            visits[-1] = replace(visits[-1], leave=visits[-1].arrive + dwell,
                                 action=action, job=name)
            if action == "charge":
                remaining = FULL_BATTERY
            elif remaining is not None:
                remaining -= dwell * track.service_rate
                if remaining < MIN_BATTERY:
                    return None
        return visits, remaining

    built = build(False)
    if built is None and track.charger:
        built = build(True)
    if built is None:
        return None
    visits, end_battery = built
    load_times = {v.job: v.arrive for v in visits if v.action == "load"}
    earliest = max(free, *(job.release - load_times[job.name] for job in jobs))
    if any(not job.cart and job.track == "Y" for job in jobs):
        material = next(job for job in jobs if not job.cart)
        earliest = max(earliest, cart_ready - load_times[material.name])
    start = first_slot(book, list(reservations(track, visits)), earliest)
    visits = tuple(replace(v, arrive=v.arrive + start, leave=v.leave + start) for v in visits)
    deadlines = {job.name: job.deadline for job in jobs}
    if any(v.action == "unload" and v.leave > deadlines[v.job] for v in visits):
        return None
    return Trip(vehicle, track_name, visits, tuple(job.name for job in jobs), end_battery)


def dispatch(tracks, materials, initial_carts=0, bundle_green=False, scoring="original", *,
             bundle_yellow=True):
    require(len({track.ticks_per_second for track in tracks.values()}) == 1,
            "dispatch tracks must use the same time unit")
    available = {vehicle: 0 for track in tracks.values() for vehicle in track.fleet}
    battery = {vehicle: FULL_BATTERY if track.charger else None
               for track in tracks.values() for vehicle in track.fleet}
    used = Counter()
    pending = {job.name: job for job in materials}
    all_jobs = dict(pending)
    cart_stock = {number: 0 for number in range(1, initial_carts + 1)}
    cart_for_job = {}
    operator_free = [0, 0]
    trips, transfers = [], []
    book = defaultdict(list)
    paths = {}
    for name, track in tracks.items():
        nodes = {track.depot, track.charger} - {""}
        for job in materials:
            if job.track == name:
                nodes.update((job.load, job.unload))
        if name == "Y":
            nodes.update(track.cart_nodes)
        for source in nodes:
            for target in nodes:
                try:
                    paths[name, source, target] = shortest_path(track, source, target)
                except ScheduleError:
                    continue

    def transfer(job_name, cart_id, operator, release):
        ticks = tracks["Y"].ticks_per_second
        start = max(release, operator_free[operator])
        move = Manual(job_name, cart_id, operator, start,
                      start + MANUAL_TRAVEL * ticks, start + MANUAL_CYCLE * ticks)
        transfers.append(move)
        operator_free[operator] = move.free
        return move.drop

    while pending:
        best = None
        cart_id = min(cart_stock, key=cart_stock.get) if cart_stock else None
        ready = cart_stock[cart_id] if cart_id is not None else None
        returns = sorted((job for job in pending.values() if job.cart),
                         key=lambda job: (job.release, job.name))
        green_first = {}
        if bundle_green:
            for job in sorted(pending.values(), key=lambda job: (job.release, job.name)):
                if job.track == "G":
                    green_first.setdefault(job.load, job)
        for job in pending.values():
            if job.track == "Y" and not job.cart and cart_id is None:
                continue
            bundles = [(job,)]
            if bundle_yellow and job.track == "Y" and not job.cart and returns:
                bundles.append((job, returns[0]))
            if bundle_green and job.track == "G":
                bundles.extend((job, second) for station, second in green_first.items() if station != job.load)
            track = tracks[job.track]
            for vehicle in track.fleet:
                for bundle in bundles:
                    trip = make_trip(job.track, track, vehicle, bundle, available[vehicle],
                                     battery[vehicle], ready, book, paths)
                    if trip is None:
                        continue
                    finish = next(v.leave for v in trip.visits if v.action == "unload")
                    if job.cart and (ready is None or ready > finish):
                        # A return unlocks later loading, but only after the second handoff.
                        finish = max(finish, operator_free[1]) + MANUAL_TRAVEL * track.ticks_per_second
                    home = trip.visits[-1].leave
                    last_unload = max(v.leave for v in trip.visits if v.action == "unload")
                    if scoring == "work_rate":
                        # Compare calendar time committed per completed job, including the
                        # delay from the next vehicle availability to return to the depot.
                        priority = (home - available[vehicle]) * 2 // len(bundle)
                        rank = (priority, last_unload, finish, -len(bundle), home)
                    elif scoring == "balanced_completion":
                        # Charge a paired candidate half its additional time to the first delivery.
                        rank = (finish + last_unload, -len(bundle), home)
                    else:
                        rank = (finish, -len(bundle), home)
                    score = (bool(used[vehicle]), *rank, vehicle, job.name)
                    if best is None or score < best[0]:
                        best = score, trip
        require(best is not None, f"No feasible trip found with {len(pending)} jobs pending. "
                "Check directed connectivity, service windows, cart availability and battery reserve.")
        trip = best[1]
        trips.append(trip)
        used[trip.vehicle] += 1
        track = tracks[trip.track]
        available[trip.vehicle] = trip.visits[-1].leave + track.headway
        battery[trip.vehicle] = trip.end_battery
        for key, start, end in reservations(track, trip.visits):
            reserve(book[key], start, end)
        finishes = {v.job: v.leave for v in trip.visits if v.action == "unload"}
        for name in trip.jobs:
            job = pending.pop(name)
            if trip.track != "Y":
                continue
            if job.cart:
                returned = cart_for_job[name]
                cart_stock[returned] = transfer(name, returned, 1, finishes[name])
            else:
                cart_stock.pop(cart_id)
                return_name = f"Return-{name}"
                release = transfer(name, cart_id, 0, finishes[name])
                return_job = Job(return_name, "Y", *track.cart_nodes, release,
                                 16 * track.ticks_per_second, cart=True,
                                 deadline=99999 * track.ticks_per_second)
                pending[return_name] = all_jobs[return_name] = return_job
                cart_for_job[name] = cart_for_job[return_name] = cart_id
    return trips, transfers, all_jobs, cart_for_job


def validate(tracks, materials, trips, transfers, all_jobs, cart_for_job, initial_carts):
    """Replay the emitted schedule without using the dispatcher's booking table."""
    movements, stops, by_vehicle = defaultdict(list), defaultdict(list), defaultdict(list)
    executions = defaultdict(list)
    track_by_vehicle = {vehicle: name for name, track in tracks.items() for vehicle in track.fleet}
    for trip in trips:
        require(track_by_vehicle.get(trip.vehicle) == trip.track, "vehicle track mismatch")
        by_vehicle[trip.vehicle].append(trip)
    require(set(by_vehicle) == set(track_by_vehicle), "unused vehicle")
    for vehicle, vehicle_trips in by_vehicle.items():
        track = tracks[track_by_vehicle[vehicle]]
        battery = FULL_BATTERY if track.charger else None
        free = 0
        for trip in sorted(vehicle_trips, key=lambda item: item.visits[0].arrive):
            visits = trip.visits
            require(visits[0].node == visits[-1].node == track.depot, "trip must return to depot")
            require(visits[0].arrive >= free, "overlapping vehicle trips")
            seen = []
            for index, visit in enumerate(visits):
                if index:
                    prev = visits[index - 1]
                    duration = track.edges.get((prev.node, visit.node))
                    require(duration is not None and prev.leave + duration == visit.arrive,
                            "illegal edge or travel duration")
                    pair = frozenset((prev.node, visit.node))
                    movements[pair].append((prev.leave, visit.arrive, vehicle))
                    if battery is not None:
                        battery -= duration * track.moving_rate
                require(visit.battery == battery and (battery is None or battery >= MIN_BATTERY),
                        "battery mismatch or reserve violation")
                dwell = visit.leave - visit.arrive
                if visit.action in ("load", "unload"):
                    job = all_jobs.get(visit.job)
                    require(job is not None and job.track == trip.track, "unknown job or wrong track")
                    require(visit.node == getattr(job, visit.action) and dwell == job.duration,
                            "wrong service node or duration")
                    executions[job.name].append((visit, trip))
                    seen.append((job.name, visit.action))
                elif visit.action == "charge":
                    require(battery is not None and visit.node == track.charger
                            and dwell == track.charge_time, "invalid charge event")
                    battery = FULL_BATTERY
                else:
                    require(visit.action == "pass" and dwell == 0, "invalid waypoint action")
                if battery is not None and visit.action != "charge":
                    battery -= dwell * track.service_rate
                    require(battery >= MIN_BATTERY, "battery reserve violation during service")
                if visit.node != track.depot or track.reserve_depot_junction:
                    location = track.cross.get(visit.node, visit.node)
                    stops[location].append((visit.arrive, visit.leave + track.headway, vehicle))
            require(trip.jobs and seen == [(name, action) for name in trip.jobs
                                          for action in ("load", "unload")], "invalid trip tasks")
            require(battery == trip.end_battery, "ending battery mismatch")
            free = visits[-1].leave + track.headway

    for resource_type, resource_table in (("edge", movements), ("node/crossing", stops)):
        for resource, intervals in resource_table.items():
            active_until = {}
            for start, end, vehicle in sorted(intervals):
                require(all(other == vehicle or until <= start for other, until in active_until.items()),
                        f"{resource_type} conflict at {resource}")
                active_until[vehicle] = max(end, active_until.get(vehicle, 0))

    material_names = {job.name for job in materials}
    yellow = {job.name for job in materials if job.track == "Y"}
    expected = material_names | {f"Return-{name}" for name in yellow}
    require(set(executions) == expected == set(all_jobs), "missing or unexpected job")
    for job in materials:
        require(all_jobs[job.name] == job, "input job modified")
    timing = {}
    for name, events in executions.items():
        require(len(events) == 2, "duplicate job service")
        (load, first), (unload, second) = events
        job = all_jobs[name]
        require(first is second and load.action == "load" and unload.action == "unload"
                and job.release <= load.arrive and load.leave <= unload.arrive
                and unload.leave <= job.deadline, f"job timing violation for {name}")
        timing[name] = load.arrive, unload.leave

    by_operator = defaultdict(list)
    ticks = tracks["Y"].ticks_per_second if "Y" in tracks else 1
    for move in transfers:
        require(move.operator in (0, 1), "unknown operator")
        by_operator[move.operator].append(move)
    for operator, moves in by_operator.items():
        free = 0
        for move in sorted(moves, key=lambda item: item.start):
            require(move.start >= free and move.drop == move.start + MANUAL_TRAVEL * ticks
                    and move.free == move.start + MANUAL_CYCLE * ticks,
                    f"operator {operator + 1} timing violation")
            free = move.free
    handoffs = {(move.operator, move.job): move for move in transfers}
    expected_handoffs = {(0, name) for name in yellow} | {(1, f"Return-{name}") for name in yellow}
    require(set(handoffs) == expected_handoffs and len(handoffs) == len(transfers), "invalid handoff count")
    require(set(cart_for_job) == yellow | {f"Return-{name}" for name in yellow}, "invalid cart assignments")
    cart_ready = dict.fromkeys(range(1, initial_carts + 1), 0)
    for name in sorted(yellow, key=lambda key: timing[key][0]):
        returned = f"Return-{name}"
        cart = cart_for_job[name]
        pickup, delivery = handoffs[0, name], handoffs[1, returned]
        expected_return = Job(returned, "Y", *tracks["Y"].cart_nodes, pickup.drop,
                              16 * ticks, cart=True, deadline=99999 * ticks)
        require(all_jobs[returned] == expected_return, "empty cart job metadata mismatch")
        require(cart in cart_ready and cart_ready[cart] <= timing[name][0], "empty cart stock violation")
        require(cart == pickup.cart_id == delivery.cart_id == cart_for_job[returned], "cart identity mismatch")
        require(timing[name][1] <= pickup.start and pickup.drop <= timing[returned][0]
                and timing[returned][1] <= delivery.start,
                "empty cart handoff precedence violation")
        cart_ready[cart] = delivery.drop
    return timing


def road(edges, left, right, seconds, two_way=False):
    edges[left, right] = seconds
    if two_way:
        edges[right, left] = seconds


def fixtures():
    # Problem statement -1.pdf, Fig. 1 and Appendix 1. Entries are loading station:release.
    green_rows = """
    1:3312 1:1518 2:3346 2:3094 2:1490 1:3404 2:813 2:2670 2:2022 1:1420
    2:1072 1:2648 1:1025 1:1217 2:1597 1:2825 2:1000 1:3024 2:534 1:2445
    1:2076 2:2750 1:1671 1:1231 1:501 1:1989 2:3505 1:1985 2:1906 1:1611
    1:1023 1:2605 1:1528 2:1743 1:1 2:633 1:353 2:1404 2:2571 1:3128
    1:1659 1:1384 1:3271 1:2111 1:21 2:3018 1:2272 1:110 2:1885 1:3274
    2:765 2:2742 2:84 1:51 1:1700 2:3204 2:2100 1:1498 1:2027 2:714
    1:1876 1:3503 1:2866 2:258 2:2198 2:2944 2:788 2:1286 1:708 1:2352
    1:2783 2:3347 2:307 1:2876 1:1271 1:1484 2:3456 2:3035 1:2283 1:778
    2:712 2:1428 1:3295 2:1206 1:2151 2:1568 1:2278 2:1865 1:2116 1:1152
    2:3015 1:618 2:3287 2:47 1:893 1:312 2:841 2:2758 1:715 1:1445
    """
    green_edges = {}
    for left, right, duration, two_way in (
        ("Start", "UnloadingStation1", 10, False), ("UnloadingStation1", "T2", 17, False),
        ("T2", "T3", 7, False), ("T3", "LoadingStation1", 5, False),
        ("LoadingStation1", "T1", 22, False), ("T1", "Start", 7, True),
        ("T1", "UnloadingStation2", 41, True), ("UnloadingStation2", "LoadingStation2", 26, True),
        ("LoadingStation2", "T4", 11, True),
    ):
        road(green_edges, f"G_{left}", f"G_{right}", duration, two_way)
    tracks = {"G": Track("G_Start", ("G_V01", "G_V02", "G_V03"), green_edges, {})}
    jobs = []
    for number, row in enumerate(green_rows.split(), 1):
        station, release = map(int, row.split(":"))
        jobs.append(Job(f"Job-{number}", "G", f"G_LoadingStation{station}",
                        f"G_UnloadingStation{3 - station}", release))

    # Compact one-way demo layout, with the first 12 release times in sorted order
    # from Problem statement -2.pdf, Appendix 1. Human timings follow that statement.
    yellow_edges = {}
    for left, right, duration in (
        ("Start", "Load", 14), ("Load", "Unload", 48), ("Unload", "Pickup", 14),
        ("Pickup", "Return", 68), ("Return", "Start", 18),
    ):
        road(yellow_edges, f"Y_{left}", f"Y_{right}", duration)
    tracks["Y"] = Track("Y_Start", ("Y_V01", "Y_V02"), yellow_edges, {})
    for number, release in enumerate((8, 31, 80, 199, 205, 206, 224, 231, 239, 280, 292, 300), 101):
        jobs.append(Job(f"Job-{number}", "Y", "Y_Load", "Y_Unload", release))

    # Synthetic loops with equal free-flow approach times at the physical crossing.
    # Accelerated demo rates and durations intentionally exercise the charging branch.
    for name, count, charge_time, service in (("R", 2, 90, 14), ("P", 1, 60, 16)):
        edges = {}
        for left, right, duration in (("Start", "Charge", 4), ("Charge", "X", 5),
                                     ("X", "Load", 5), ("Load", "Unload", 12), ("Unload", "Start", 8)):
            road(edges, f"{name}_{left}", f"{name}_{right}", duration)
        vehicles = tuple(f"{name}_V{i:02}" for i in range(1, count + 1))
        tracks[name] = Track(f"{name}_Start", vehicles, edges, {f"{name}_X": "Shared_X"},
                             f"{name}_Charge", charge_time, 120, 25)
        for release in (0, 0, 10, 20):
            jobs.append(Job(f"Job-{len(jobs) + 1}", name, f"{name}_Load", f"{name}_Unload", release, service))
    return tracks, jobs, 8


