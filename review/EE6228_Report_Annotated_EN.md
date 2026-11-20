# EE6228 Factory AGV Scheduling — Annotated Draft

> This historical draft and its review comments describe earlier experiments.
> For the current schedule, commands, and results, see the [revised report](../EE6228_Report_Materials_EN.md).

## Reservation-Based Dispatching for Factory AGV Scheduling

This draft follows the six report requirements. Its experiments use `agv_demo.py`, `demo_output/summary.json`, `job_schedule.csv`, `manual_transfers.csv`, and `agv_routes.txt`. Green uses all 100 jobs in the problem appendix. Yellow and Red/Purple use smaller instances. The results reflect the data, parameters, and modeling assumptions stated here.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** The main experiment uses the 100 material jobs on Green to compare single-job and paired trips under the same topology and reservations. Smaller Yellow and Red/Purple examples demonstrate empty-cart circulation, intersection reservations, and charging. The report presents the mathematical model, solution method, results, and a 2D replay of schedule events.  
> **Rationale.** The opening paragraph identifies the research question, main comparison, and scope. The submission can add the course code, group number, member names, and student IDs before the title. The course announcement calls for each member to submit the same group report in PDF or a DOC format accepted by the portal.
>
> **End of comment**
<!-- review:end -->

## 1. Introduction to the use case

### 1.1 Factory transport

Material moves between workstations during production. An automated guided vehicle (AGV) picks up material at a loading station, delivers it to the specified unloading station, and then continues or returns to the depot. When vehicles share roads, assignment, route, and timing affect one another. A dispatched vehicle may occupy an edge another needs. Waiting for loading or charging can also delay other jobs. Le-Anh and de Koster [1] review these related decisions, including vehicle scheduling, routing, and deadlock resolution.

The project covers four tracks, Green, Yellow, Red, and Purple, with eight AGVs in total. Each AGV stays on its own track. The full problem has three scenarios and 300 specified jobs. The Yellow scenario also generates empty-cart returns as material moves. The course-provided case materials supply the track layouts, job lists, and operating assumptions.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** The main experiment uses Green, three AGVs, and all 100 appendix jobs. The other two rows describe the constraints exercised by the extensions. Yellow uses the 12 earliest-released jobs and a simplified loop. Red/Purple uses a synthetic topology, jobs, and battery parameters.  
> **Rationale.** The original review treated the three scenarios as candidate project topics for a group project of manageable scope. This wording preserves the extensions and makes clear that eight AGVs, 120 material jobs, and 12 cart returns describe the demo.
>
> **End of comment**
<!-- review:end -->

| Scenario | Vehicles | Main decisions and constraints |
| --- | --- | --- |
| Green | 3 AGVs | 100 material jobs, two fixed station pairs, bidirectional-edge coordination, and no overtaking |
| Yellow | 2 AGVs | Loading uses empty carts. Two operators and AGVs return the carts, and inventory affects when loading can start. |
| Red/Purple | 2 Red AGVs and 1 Purple AGV | Both tracks share a physical intersection. The battery-constrained case also schedules charging. |

### 1.2 Objective and experiment scope

The primary objective is to minimize makespan, the time when the last unloading operation in the specified job set finishes. The schedule must satisfy release times, service precedence, road directions, headway, resource occupancy, and depot returns.

The project implements a reproducible constructive heuristic. The full Green job set exercises basic scheduling. Smaller Yellow and Red/Purple instances demonstrate cart circulation, shared intersections, and charging.

The case materials describe different configurations. The Yellow case specifies 100 material jobs, eight initial empty carts, and two operators. Red/Purple uses stated synthetic battery parameters. Start is modeled as a parking area with separate bays, so parked vehicles do not reserve a common road node. Each AGV carries one job at a time and unloads before loading the next job.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** The Yellow example uses the initial carts and manual handling rules specified for Yellow and the 12 earliest-released appendix jobs. Red/Purple is a synthetic mechanism test. The implementation treats Start as a parking area exempt from node reservations. Once the official topology is available, distinguish parallel parking bays from the shared public junction.  
> **Rationale.** Independent bays account for parking. Each of the two Green schedules has 44 mid-trip visits to Start that may use a public passage. The draft data and HTML use the original convention, which can be updated after topology verification and model revision.
>
> **End of comment**
<!-- review:end -->

## 2. Mathematical formulation

This section defines a constrained scheduling model using visit sequences and time intervals. The implementation constructs and verifies schedules against these relationships. Exclusive reservations at roads and stations make the feasible region conservative.

<!-- review:start -->
> **Review comment**
>
> **Proposed addition.** The formulation defines feasibility, and the solver explores a subset of candidates. It uses fixed shortest paths, whole-trip shifts, and at most two jobs per candidate trip. Performance is measured by comparisons under matching conditions.  
> **Rationale.** State the model and the scope of the heuristic. The reported schedules establish feasibility for the modeled instance. A separate proof would be needed to establish global optimality.
>
> **End of comment**
<!-- review:end -->

### 2.1 Sets, parameters, and variables

| Symbol | Meaning |
| --- | --- |
| \(G_r=(V_r,E_r)\) | Directed graph of track \(r\), with a bidirectional road represented as two opposing arcs |
| \(K_r\) | Fleet available on track \(r\) |
| \(J_M,J_C\) | Sets of material jobs and empty-cart returns |
| \(J=J_M\cup J_C\) | All AGV transport jobs required in this experiment |
| \(L_j,U_j,r_j,D_j\) | Loading station, unloading station, release time, and service upper bound of job \(j\) |
| \(p_j^L,p_j^U\) | Loading and unloading durations |
| \(d_{uv},v_k\) | Road length and vehicle speed, giving travel time \(\tau_{uv}=d_{uv}/v_k\) |
| \(h\) | Node headway of 2 s |
| \(x_{jk}\in\{0,1\}\) | Whether vehicle \(k\) performs job \(j\) |
| \(\pi_{kc}\) | Ordered visits on trip \(c\) of vehicle \(k\), with a node, action, and job ID for each visit |
| \(a_{kcn},d_{kcn}\) | Arrival and departure times of the \(n\)th visit |
| \(s_j^L,s_j^U,C_j\) | Loading start, unloading start, and unloading completion |
| \(B^-_{kcn},B^+_{kcn}\) | Battery level before and after service, in percent of full charge |

Times are in seconds. Battery consumption rates are in percentage points per second. Each visit has a separate number, even when the same physical node is visited more than once.

<!-- review:start -->
> **Review comment**
>
> **Proposed addition.** Define the track set, track of each material job, depot \(o\), availability for each trip, and visit count. Waiting, loading, unloading, and charging durations are nonnegative. Use \(L\) or \(\ell\) for edge length and reserve \(d\) for departure. Vehicle load is 0 or 1, increases by 1 at loading, decreases by 1 at unloading, and is 0 on return.  
> **Rationale.** Give distance and departure distinct notation. Express capacity and nonnegative durations explicitly so they can be checked against the code.
>
> **End of comment**
<!-- review:end -->

### 2.2 Objective function

\[
\min C_{\max}^{J}
\]

\[
C_{\max}^{J}\ge C_j,\qquad \forall j\in J.
\tag{1}
\]

To distinguish material delivery from empty-cart cleanup, also report

\[
C_{\max}^{M}=\max_{j\in J_M}C_j,\qquad
T_{\mathrm{home}}=\max_{k,c}d_{kc,N_{kc}}.
\tag{2}
\]

The demo schedules one complete Yellow empty-cart return for each material job. It sends the final carts back to the loading station even if no later material job needs them. This is the experiment's cleanup policy. The two candidates are ranked first by \(C_{\max}^{J}\), then by \(C_{\max}^{M}\) for ties. Final manual cart delivery is recorded separately.

<!-- review:start -->
> **Review comment**
>
> **Proposed addition.** The main comparison uses Green material makespan. For the extensions, report material completion, last AGV cart-return unloading, last depot return, and last manual delivery separately. For an objective that covers cleanup and manual work, define the last completion time across all required activities.  
> **Rationale.** The 11,234 s and 11,836 s values measure AGV cart-return unloading and manual delivery, respectively. The original mixed-scenario objective omits manual delivery.
>
> **End of comment**
<!-- review:end -->

### 2.3 Unique job assignment, vehicle use, and visit linkage

\[
\sum_{k\in K_{r(j)}}x_{jk}=1,\qquad \forall j\in J.
\tag{3}
\]

\[
\sum_{j:r(j)=r}x_{jk}\ge1,\qquad \forall k\in K_r.
\tag{4}
\]

If \(x_{jk}=1\), vehicle \(k\) must visit \(L_j\) once to load job \(j\) and \(U_j\) once to unload it. If \(x_{jk}=0\), the vehicle has no service visit for that job. Loading and unloading times match \(a,d\) for the corresponding visits.

<!-- review:start -->
> **Review comment**
>
> **Proposed final sentence.** If visit \(n\) serves job \(j\), the service starts at \(s=a+w\) and the vehicle departs at \(d=s+p\), with \(q=0\) for loading or unloading. The implementation has \(w=0\) away from Start, so \(s=a\).  
> **Rationale.** Equation (9) allows node waiting. Arrival equals the start of service only when waiting is zero. An explicit link between visits and time variables keeps the model consistent with its implementation.
>
> **End of comment**
<!-- review:end -->

Each used trip completes at least one transport job. Vehicles stay on their assigned tracks. If jobs \(i,j\) are performed in that order on the same trip, impose

\[
s_j^L\ge C_i+\text{actual travel time from }U_i\text{ to }L_j.
\tag{5}
\]

This ensures the first job is unloaded before the next job is loaded. The visit sequence must also obey the edge constraints below, so actual route time is used in equation (5).

### 2.4 Release times, service precedence, and routes

\[
s_j^L\ge r_j,\qquad
s_j^U\ge s_j^L+p_j^L,\qquad
C_j=s_j^U+p_j^U,\qquad C_j\le D_j.
\tag{6}
\]

This experiment interprets the 99,999 s end of the service window as the unloading deadline.

For \(\pi_{kc}=(v_{kc1},\ldots,v_{kc,N_{kc}})\), require

\[
v_{kc1}=v_{kc,N_{kc}}=o_{r(k)},\qquad
(v_{kcn},v_{kc,n+1})\in E_{r(k)}.
\tag{7}
\]

\[
a_{kc,n+1}=d_{kcn}+\tau_{v_{kcn},v_{kc,n+1}}.
\tag{8}
\]

\[
d_{kcn}=a_{kcn}+w_{kcn}+p_{kcn}+q_{kcn}.
\tag{9}
\]

Here, \(w\) is waiting time, \(p\) is loading or unloading duration, and \(q\) is charging time. A visit can include at most one service action. The demo puts traffic waiting at the depot, so \(w=0\) at all other nodes. Vehicles do not wait in the middle of an edge.

Consecutive trips also satisfy

\[
a_{k,c+1,1}\ge d_{kc,N_{kc}}+h.
\tag{10}
\]

Trips are defined by dispatch batches. A shortest path may pass Start mid-trip. A depot return is recorded when the dispatch batch ends. If each passage through Start defines a cycle boundary, split and verify the visits accordingly.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** A trip begins when a vehicle leaves its parking bay and ends when it returns to a bay. Passing the public junction does not end a trip. The revised model reserves the junction while vehicles wait in separate bays. The transcribed network in this draft has not split the two, so the tables use the original rule.  
> **Rationale.** Start serves as a network node and a depot. An explicit trip boundary explains the 44 mid-trip passages and distinguishes them from depot returns in the replay.
>
> **End of comment**
<!-- review:end -->

### 2.5 Road, node, and intersection constraints

Kim and Tanchoco [2] use node time windows to find conflict-free AGV routes on bidirectional networks. This project uses timed reservations to check the feasibility of fixed candidate paths.

For a physical road \(e=\{u,v\}\), a traversal occupies

\[
I_e=[d_{kcn},a_{kc,n+1}).
\]

The two directions of a bidirectional road share one resource. Traversals by different vehicles must satisfy

\[
I_e^{(1)}\cap I_e^{(2)}=\varnothing.
\tag{11}
\]

The demo applies equation (11) to one-way roads as well. Exclusive occupation prevents overtaking and reduces possible same-direction throughput.

A visit to a node \(v\) away from the depot reserves

\[
I_v=[a_{kcn},d_{kcn}+h).
\tag{12}
\]

Reservations by different vehicles at a node are disjoint. Red and Purple nodes at the same physical intersection are mapped to one resource and use the same constraint. For a potential conflict, the demo moves one vehicle's departure later so it arrives in an available slot.

Equation (12) models safety at an abstract node. If the physical intersection has a nonzero extent, the interval should run from entry until the vehicle clears the entire conflict zone. Under the separate-bay assumption, parking waits are exempt from equation (12). Any shared narrow access lane should be reserved separately.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** Equation (12) represents public-node occupancy and headway by the half-open interval \([a,d+h)\). Visits by two vehicles to the same conflict zone must satisfy \(d_1+h\le a_2\) or \(d_2+h\le a_1\). For a conflict zone with physical extent, use the interval from entry to full clearance. Separate parking bays use no public-node capacity.  
> **Rationale.** The two possible orderings make disjoint reservations directly testable. The report can describe the abstraction and show it in the replay.
>
> **End of comment**
<!-- review:end -->

### 2.6 Yellow carts and manual resources

Zhou et al. [3] study production scheduling with limited fixture and material pallets. In this case, loading also depends on the availability of a finite pool of carriers, the empty carts.

Let \(H(t)\) be the number of available carts at the loading station, \(H_0=8\) the initial inventory, and \(R_c\) the arrival time of the \(c\)th manual cart delivery. Then

\[
H(t)=H_0+\sum_c\mathbf{1}(R_c\le t)
-\sum_{j\in J_M^Y}\mathbf{1}(s_j^L\le t)\ge0.
\tag{13}
\]

A cart delivered at a given time can be used by a loading operation starting at that time. Unique cart IDs prevent a cart from serving two jobs at once.

For Yellow material job \(j\), let \(\bar j\) be its cart-return job and let \(A_{1j},A_{2j}\) be the start times of the two manual transfer legs.

\[
A_{1j}\ge C_j,\qquad
r_{\bar j}=A_{1j}+480,\qquad
s_{\bar j}^{L}\ge r_{\bar j}.
\tag{14}
\]

\[
A_{2j}\ge C_{\bar j},\qquad R_j=A_{2j}+480.
\tag{15}
\]

The first operator occupies \([A_{1j},A_{1j}+960)\) and the second occupies \([A_{2j},A_{2j}+960)\). Assignments for the same operator cannot overlap. The 480 s one-way time determines cart delivery, and the 960 s round trip determines when the operator is available again. The demo releases a cart for manual handling as soon as unloading ends. If production adds a processing delay, include it in equation (14).

<!-- review:start -->
> **Review comment**
>
> **Proposed addition.** The same cart ID is tracked around the entire loop. The cleanup policy also returns carts no longer needed for production. The 12 cart-return jobs use an initial stock of eight carts.  
> **Rationale.** Distinguish inventory from return-job count and explain why cart returns continue after material completion.
>
> **End of comment**
<!-- review:end -->

### 2.7 Red/Purple battery use and charging

The battery starts at 100%. For travel and node service without charging, use

\[
B^+_{kcn}=B^-_{kcn}-\rho_s p_{kcn}-\rho_w w_{kcn},
\tag{16}
\]

\[
B^-_{kc,n+1}=B^+_{kcn}-\rho_m\tau_{v_{kcn},v_{kc,n+1}}.
\tag{17}
\]

Waiting at Start uses zero energy in the demo, and vehicles do not wait at other nodes. If a vehicle takes a full charge on arriving at the charging station, then

\[
q_{kcn}=H_{r(k)},\qquad B^+_{kcn}=100.
\tag{18}
\]

The next trip starts with the battery level recorded at the previous depot return. At least 10% must remain before and after each action. If an uncharged candidate trip would breach the reserve, try fully charging at the first charging stop after departure and check the entire trip again.

This rule protects the battery reserve in advance. Each charge occupies the station for a fixed time \(H_r\), regardless of the initial charge. The demo uses complete charging sessions. Station occupancy also follows equation (12).

Singh et al. [4] jointly schedule transport and charging under battery constraints. Their model allows partial recharging and can inform a variable-duration charging extension.

<!-- review:start -->
> **Review comment**
>
> **Proposed addition.** The Red/Purple case lists both unlimited battery capacity and charging requirements. The case overview and the track-specific materials use different consumption rates. The example uses the stated synthetic parameters and a 10% reserve to exercise charging. In the example, the vehicle arrives at the charger with 47.4% because the next trip is predicted to cross the reserve.  
> **Rationale.** Explain the difference between preventive charging and charging triggered after reaching a threshold. The short charging times come from the synthetic example.
>
> **End of comment**
<!-- review:end -->

## 3. Solution strategy and tools

### 3.1 Overview

Construct candidate routes with shortest paths, reserve resources, select candidates greedily, and update resources with events. Shortest paths use Dijkstra's algorithm [5].

The scheduler knows all release times in advance and works offline. It computes event times and resource availability without stepping through every second.

### 3.2 Candidate routes and earliest departure

The baseline proposes a trip from the depot to loading, then unloading, then back to the depot for each vehicle. Yellow can pair a material job with a generated cart return. The improved Green policy can add a job at a different loading station, serving load A, unload A, load B, and unload B in order.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** The Green baseline returns after one job. The paired policy also considers the earliest-released pending job at the other loading station and loads it after the first delivery. Both policies use the same network, jobs, vehicles, and reservations. Pairing of Yellow material jobs with returns is enabled in both runs of this historical comparison.  
> **Rationale.** Isolate the comparison and clarify that the heuristic considers one second-job candidate.
>
> **End of comment**
<!-- review:end -->

Suppose all actions in a candidate have fixed offsets from departure. Let \(\ell_j\) be the loading offset of job \(j\) and \(f_k\) the earliest availability of vehicle \(k\). Its initial departure bound is

\[
t_0=\max\{f_k,\max_{j\in J_{\mathrm{trip}}}(r_j-\ell_j)\}.
\tag{19}
\]

Yellow material loading also requires \(t_0\ge R_{\mathrm{cart}}-\ell_j\), where \(R_{\mathrm{cart}}\) is when the selected cart is available at the loading station.

Let \([\alpha,\beta)\) be the candidate's relative reservation and \([u,v)\) an existing reservation on the same resource. At departure time \(t\), the conflict condition is

\[
t+\alpha<v,\qquad u<t+\beta.
\]

On a conflict, move \(t\) to at least \(v-\alpha\) and recheck every resource. The relative timing inside the trip stays fixed. All traffic waits take place at the depot.

Commit a candidate once the resources are conflict-free, the battery is sufficient, and the time windows are met. Update reservations, vehicle availability, job status, cart IDs, and operator events together.

### 3.3 Dispatch priorities and policy comparison

The code compares candidates lexicographically in the following order.

1. Prefer vehicles that have yet to perform a job.
2. Prefer earlier expected unloading of the first job. For a return that resolves a cart shortage, include the second manual delivery time.
3. For ties, prefer more jobs on the trip, then an earlier depot return.
4. Use vehicle and job IDs for a stable final tie-break.

The baseline and Green paired policy each build and verify a schedule from scratch. Select the shorter makespan. The improvement comes from expanding the candidate trips in a heuristic comparison. This draft reports neither an optimal lower bound nor an optimality gap.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** Both policies are independently constructed and checked. The main comparison reports Green directly. The original mixed-instance export ranks final schedules by last AGV job completion, then by material makespan. Record trip ranking and final schedule selection separately.  
> **Rationale.** Dispatch compares the estimated unloading of the first job. Final selection compares makespan. Distinguish the greedy scoring rule from the scheduling objective.
>
> **End of comment**
<!-- review:end -->

### 3.4 Tools and their roles

| Tool or function | Purpose |
| --- | --- |
| Python 3.10+, with 3.12.14 recorded | Run the demo using the standard library |
| `heapq` | Priority queue for shortest paths. [Python documentation](https://docs.python.org/3.12/library/heapq.html) |
| `bisect` | Find potential conflicts in ordered reservation intervals |
| `dataclasses` | Represent jobs, visits, tracks, trips, and operator events |
| `csv`, `json`, `pathlib` | Export job tables, routes, and results |
| `time.perf_counter` | Measure wall-clock solve time. [Python documentation](https://docs.python.org/3.12/library/time.html#time.perf_counter) |
| `shortest_path` | Find valid directed routes |
| `make_trip`, `first_slot`, `reserve` | Construct candidates, find conflict-free slots, and commit reservations |
| `dispatch` | Assign work and update resources |
| `validate`, `negative_checks` | Independently replay schedules and test rejection of deliberate faults |

The solver is a constructive heuristic implemented in Python. Most of the work is candidate routing and interval conflict checks. Reservation calendars avoid time-step scanning. Cost still depends on the number of jobs and candidates, route lengths, and the number of conflict shifts. The experiment uses no population-based metaheuristic or iterative fitness record.

## 4. Results and discussion

### 4.1 Experiment setup

| Item | Experiment data |
| --- | --- |
| Green | All 100 material jobs in the Green case, with 56 from Loading Station 1 and 44 from Loading Station 2 |
| Yellow | The 12 earliest-released material jobs in the Yellow case on a synthetic simplified loop, with 12 cart returns |
| Red/Purple | A synthetic loop, four material jobs per track, and one shared abstract intersection |
| Total scope | Eight AGVs, 120 material jobs, and 12 cart-return jobs |
| Green service | 16 s each for loading and unloading |
| Yellow service and manual transfers | 16 s each for loading and unloading, 480 s one way and 960 s round trip for manual transfers |
| Red/Purple service | 14 s per loading or unloading on Red and 16 s on Purple |
| Red/Purple test battery parameters | Motion at 1.20 percentage points/s, service at 0.25 percentage points/s, and charging for 90 s on Red and 60 s on Purple |
| Computing environment | Windows 11 Build 26200 and Python 3.12.14 |

The Red/Purple test uses shortened charges to exercise charging. The Green map was transcribed segment by segment and still needs checking against the official topology. The draft did not reliably record CPU and memory details, so the final submission should include measured machine information.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** The Green case text and the topology summary list eight physical edges, four directed and four bidirectional. The script transcribes nine from the figure, five directed and four bidirectional. The table shows the current transcription. Confirm directions against the official topology, especially LoadingStation2–T4 and the edges incident to Start.  
> **Rationale.** Reproducibility depends on the network data. If directions or the depot rule change, rerun both policies and regenerate the tables, screenshots, and replay.
>
> | Physical edge in the code | Direction | Distance (m) | Travel time (s) |
> | --- | --- | ---: | ---: |
> | Start–UnloadingStation1 | → | 5 | 10 |
> | UnloadingStation1–T2 | → | 8.5 | 17 |
> | T2–T3 | → | 3.5 | 7 |
> | T3–LoadingStation1 | → | 2.5 | 5 |
> | LoadingStation1–T1 | → | 11 | 22 |
> | T1–Start | ↔ | 3.5 | 7 |
> | T1–UnloadingStation2 | ↔ | 20.5 | 41 |
> | UnloadingStation2–LoadingStation2 | ↔ | 13 | 26 |
> | LoadingStation2–T4 | ↔ | 5.5 | 11 |
>
> **Source.** See the Green case drawing for lengths and `fixtures()` in `agv_demo.py` for the transcribed directions and travel times. All 100 jobs were checked against the appendix for loading and unloading stations, release times, and deadlines.
>
> **End of comment**
<!-- review:end -->

### 4.2 Baseline and improved results

The table comes from `demo_output/summary.json`. Solve times are from one run.

<!-- review:start -->
> **Review comment**
>
> **Proposed table.** Recompute the Green metrics from vehicle events in both runs under the same topology and Start rule. Keep the mixed demo's 13.08% and its three-scenario table in the appendix, labeled with their scope.
>
> | Green metric | Single-job baseline | Two-job trips |
> | --- | ---: | ---: |
> | Material jobs completed | 100 | 100 |
> | Last unloading | 12,924 s | 8,641 s |
> | Trips | 100 | 56 |
> | Two-job trips | 0 | 44 |
> | Cumulative driving time | 17,904 s | 13,680 s |
> | T1 ↔ UnloadingStation2 crossings | 200 | 112 |
> | Last depot return | 12,982 s | 8,689 s |
>
> **Rationale.** These changes explain the 4,283 s gain. Keep original solve times as single observations. A runtime comparison should use repeated runs on the same device and report the median and environment.
>
> **End of comment**
<!-- review:end -->

| Metric | Baseline | Green paired policy |
| --- | ---: | ---: |
| Last Green unloading | 12,924 s | 8,641 s |
| Last material unloading across the demo | 12,924 s | 8,641 s |
| Last AGV unloading, including cart returns | 12,924 s | 11,234 s |
| Solve time | 1.826 s | 2.222 s |
| Independent constraint check | PASS | PASS |

Green makespan reduction

\[
\frac{12924-8641}{12924}\times100\%=33.14\%.
\]

Makespan reduction for all AGV jobs in the mixed demo

\[
\frac{12924-11234}{12924}\times100\%=13.08\%.
\]

These percentages refer to different job sets. The 33.14% comparison is for Green.

Track-level results for the selected policy

| Track | Material jobs | Last material unloading | Last unloading across all AGV jobs |
| --- | ---: | ---: | ---: |
| Green | 100 | 8,641 s | 8,641 s |
| Yellow | 12 | 4,236 s | 11,234 s |
| Red | 4 | 300 s | 300 s |
| Purple | 4 | 444 s | 444 s |

The last AGV returns at 11,252 s. The last cart is manually delivered to the Yellow loading station at 11,836 s. This second metric measures completion of manual cart circulation.

### 4.3 Workload, charging, and energy

| Vehicle | Material jobs | Cart returns | Cumulative energy use (percentage points) |
| --- | ---: | ---: | ---: |
| G_V01 | 49 | 0 | Unmodeled |
| G_V02 | 48 | 0 | Unmodeled |
| G_V03 | 3 | 0 | Unmodeled |
| Y_V01 | 8 | 12 | Unmodeled |
| Y_V02 | 4 | 0 | Unmodeled |
| R_V01 | 2 | 0 | 95.6 |
| R_V02 | 2 | 0 | 95.6 |
| P_V01 | 4 | 0 | 195.2 |

All eight vehicles participate. Green jobs are concentrated on two vehicles because the greedy rule favors earlier completions after assigning work to each vehicle. A secondary objective such as maximum individual workload, utilization, or workload imbalance could be added and its effect on makespan measured.

The selected schedule includes 45 multi-job trips, 24 manual transfers, and five full charges. Cumulative energy use can exceed 100 percentage points when vehicles recharge. Green and Yellow use unlimited battery capacity, and their route files show 100% as the default interface value.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** Green completes 44 two-job trips. The mixed demo includes one additional paired Yellow trip, giving 45 multi-job trips, together with 24 manual transfers and five full charges.  
> **Rationale.** Label the counts by experiment. To interpret the Green distribution of 49 / 48 / 3, report each vehicle's travel, service, and waiting times and examine the road bottleneck and scoring rule.
>
> **End of comment**
<!-- review:end -->

### 4.4 Feasibility verification

The independent verifier reconstructs movements and node use from final visits without consulting the dispatcher's reservation book. The checks use the model and inputs for this run.

| Area | Check | Result |
| --- | --- | --- |
| Jobs | Exactly one completion, loading and unloading by the same vehicle, loading after release, and unloading after loading | PASS |
| Vehicles | Assigned track, legal edges, travel times, nonoverlapping trips for each vehicle, and depot returns | PASS |
| Traffic | Exclusive use of roads, 2 s node headway, and shared intersection reservations | PASS |
| Yellow | Cart IDs and availability, cart-return precedence, and the two operator calendars | PASS |
| Battery | Travel and service consumption, charging reset, and minimum reserve | PASS |

The verifier must also reject the following deliberate faults.

| Injected fault | Verification result |
| --- | --- |
| Move the Purple arrival to overlap a Red vehicle at the intersection | Rejected for a Shared_X conflict |
| Set the battery recorded at a visit to 0 | Rejected for a battery mismatch or reserve violation |
| Set initial empty-cart stock to 0 | Rejected for insufficient cart inventory |
| Move a manual delivery 1 s earlier | Rejected for incorrect manual-transfer duration |

These checks establish feasibility for the modeled problem. Vehicle geometry, positioning error, intersection dimensions, and real traffic controllers are outside their scope.

<!-- review:start -->
> **Review comment**
>
> **Proposed addition.** The draft verifier replays in-memory trips and covers the rules in the table. The export fields in the route TXT require a separate check. The Yellow verifier also reads generated cart-return definitions from the dispatcher. Reconstruct those jobs independently from material inputs, topology, and manual events.  
> **Rationale.** In the original review, a generated return could be reclassified as material and given a different deadline while still passing `validate()`. The four negative checks cover distinct faults. Export read-back and independent reconstruction address the additional gap.
>
> **End of comment**
<!-- review:end -->

### 4.5 Interpretation and limitations

After the first delivery, Green pairing sends the vehicle directly to the other loading station, reducing empty travel back to the depot. The shared road still limits parallel movement by the three AGVs. Pairing gains and workload should be interpreted in light of this bottleneck.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** Pairing cuts Green trips from 100 to 56 and T1 ↔ UnloadingStation2 crossings from 200 to 112. Cumulative driving falls by 23.59%. Fewer shared-edge crossings are consistent with the makespan dropping from 12,924 s to 8,641 s. The 33.14% reduction is relative to the baseline that returns after every job.  
> **Rationale.** Use the observed road activity to explain the improvement and limit the claim to the tested instance and baseline.
>
> **End of comment**
<!-- review:end -->

Yellow material finishes at 4,236 s, while the final AGV cart return unloads at 11,234 s under the cleanup policy. Each operator handles one cart at a time, so circulation affects the end of the schedule. For a material-only objective, a separate experiment could stop returning carts once no future production job needs them.

The small Red/Purple instance exercises joint intersection reservations and charging. The consumption and charge times are synthetic. The 300 s and 444 s measurements apply to this test instance.

Fixed shortest paths and waiting at the depot can miss useful detours. One-way edge exclusivity, exclusive service nodes, and full charges with a fixed duration also restrict the search. Verify parking bays, time-window interpretation, trip boundaries, and the extent of intersections against the problem and official topology. The reported schedules are feasible under the modeled assumptions. Global optimality remains open.

## 5. Simulation demo and reproduction

### 5.1 Reproducing the original demo

Extract `EE6228_AGV_demo.zip` and run this command from the directory containing `agv_demo.py`.

    python agv_demo.py --out demo_output

Use Python 3.10 or later. The code uses the standard library, constructs and independently checks both schedules, runs four negative checks, and exports the selected schedule.

| Output | What it demonstrates |
| --- | --- |
| `summary.json` | Makespan, job count, charging, and validation |
| `job_schedule.csv` | Vehicle assignment, loading start, unloading completion, and cart IDs |
| `manual_transfers.csv` | One-way delivery and round-trip operator availability |
| `agv_routes.txt` | Nodes visited by each vehicle, waiting, charging, battery level, and service completion |

### 5.2 Three clips to verify

**Clip A. Green pairing.** G_V01 starts loading Job-35 at 39 s and finishes unloading at 134 s. It starts loading Job-94 at 160 s and finishes unloading at 276 s. The job table and route show service order and the path connecting the two jobs.

**Clip B. Yellow cart reuse.** Job-101 uses cart 1, starts loading at 14 s, and finishes unloading at 94 s. The first operator leaves at 94 s, delivers the cart to the pickup station at 574 s, and returns at 1,054 s. The AGV begins pickup at 696 s and unloads at the return station at 796 s. The second operator leaves at 796 s, delivers the cart to the loading station at 1,276 s, and returns at 1,756 s. Job-109 starts loading at 1,276 s using cart 1 again.

**Clip C. Intersection and charging.** R_V01 reaches the shared intersection at 9 s. P_V01 departs 2 s later to reach the intersection at 11 s, meeting the demo headway. On its second trip R_V01 reaches the charger at 68 s with 47.4% battery. It charges until 158 s and returns to 100%. This preventive charge protects the 10% reserve on the rest of the trip.

### 5.3 Optional simulation demo

The draft includes a runnable scheduler, event exports, and a constraint replay. The optional simulation can demonstrate vehicle routes, job progress, and shared-edge use.

<!-- review:start -->
> **Review comment**
>
> **Proposed wording.** Open `EE6228_AGV_Replay.html` offline. It uses visit and service events from both schedules to show Green vehicle travel, waiting, and operations. It supports policy switching, pause, playback speed, and timeline controls. In the paired clip, G_V01 finishes unloading Job-35 at 134 s and starts loading Job-94 at 160 s. In the shared-edge clip, G_V01 uses the edge at 202–243 s and G_V02 uses it in the opposite direction at 245–286 s.  
> **Rationale.** The demo uses schedule data that can be checked against the report. The layout is schematic, and motion is interpolated along each edge. Verification uses the discrete scheduling events.
>
> **End of comment**
<!-- review:end -->

## 6. References

1. Le-Anh, T., & de Koster, M. B. M. (2006). A review of design and control of automated guided vehicle systems. *European Journal of Operational Research, 171*(1), 1–23. [DOI](https://doi.org/10.1016/j.ejor.2005.01.036)
2. Kim, C. W., & Tanchoco, J. M. A. (1991). Conflict-free shortest-time bidirectional AGV routeing. *International Journal of Production Research, 29*(12), 2377–2391. [DOI](https://doi.org/10.1080/00207549108948090)
3. Zhou, Y., Du, S., Lv, J., Shen, X., Matta, A., & Wang, S. (2025). Flexible pallet automation system scheduling with limited fixture-pallets and material-pallets: A case study from an engine manufacturing enterprise. *Journal of Manufacturing Systems, 83*, 357–371. [DOI](https://doi.org/10.1016/j.jmsy.2025.09.015)
4. Singh, N., Dang, Q.-V., Akcay, A., Adan, I., & Martagan, T. (2022). A matheuristic for AGV scheduling with battery constraints. *European Journal of Operational Research, 298*(3), 855–873. [DOI](https://doi.org/10.1016/j.ejor.2021.08.008)
5. Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. *Numerische Mathematik, 1*, 269–271. [DOI](https://doi.org/10.1007/BF01386390)

---

> **Additional demo review for Section 4.5**
>
> **Proposed addition.** To test the depot assumption, use the same 100 Green jobs and nine transcribed edges, reserve Start for 2 s at departures, returns, and mid-trip passages, and keep parking waits in separate bays. Under the new rule, the regenerated baseline finishes at 13,012 s and the paired schedule at 8,641 s, a reduction of 33.59%. The old baseline has a Start conflict under the new rule. The paired makespan is the same under both rules.
>
> **Proposed addition.** Compare alternate candidate scores under each depot rule. Turnaround per job gives 9,534 s under both rules. The mean of first and last unloading gives 12,924 s with Start exempt and 13,012 s with Start reserved. Keep the original paired scoring for this instance. The comparison covers the tested policies.
>
> **Rationale.** The reruns show how the depot rule affects the comparison and how the alternate scores performed. If the new rule is the main result, update Section 4.2's baseline and percentage together. The official topology is still needed to confirm the depot assumption.
>
> **Additional demo review for Section 5.3**
>
> **Proposed wording.** The replay has two depot rules and four policies. To check the original clips in Section 5.2 and the comment above, choose Start exempt and Two-job trips. Switch to Shared Start reserved to compare baseline and pairing under that rule. The replay uses events read back from each policy's `visits.csv`.
>
> **Rationale.** The replay initially shows Shared Start reserved. Check individual vehicle events under the selected rule even though both paired schedules have the same makespan.
