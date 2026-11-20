# EE6228 Factory AGV Scheduling

**Resource reservation, vehicle routing, and feasibility checks**

This project uses shortest paths and timed resource reservations to assign jobs, route vehicles, and schedule their movements. The Green and Yellow experiments each use all 100 material jobs from the corresponding problem appendix. On Green, two-job trips reduced the last unloading time from **13,012 s to 8,641 s** when vehicles reserved the shared depot junction. On Yellow, combining material and cart-return jobs reduced the last material unloading time from **90,452.7 s to 89,027.9 s**, assuming a value for an unlabeled road length. Eight synthetic jobs exercise the shared intersection and charging logic on Red and Purple. A full 300-job factory experiment requires the official topology and a complete Red/Purple schedule.



## 1. Use case

The factory uses automated guided vehicles (AGVs) to move material from loading stations to designated unloading stations. Each vehicle stays on its own track. Dispatching assigns a vehicle to a job, routing determines which resources it uses, and scheduling determines when it uses each resource. A single vehicle completes each job along its specified loading and unloading pair. The primary performance metric is the time when the last unloading operation ends. We also report when the last vehicle returns to its depot.

Le-Anh and de Koster [1] review guide-path design, vehicle scheduling, routing, and battery management as related decisions in AGV systems. The job lists, layouts, and operating rules used in this report come from the course-provided case materials.

| Problem | Inputs and requirements | Experiment coverage |
| --- | --- | --- |
| Green, three AGVs | 100 material jobs, two station pairs, exclusive use of bidirectional edges, and participation and return of all vehicles | 100 appendix jobs, topology transcribed from Figure 1, and two depot rules |
| Yellow, two AGVs | 100 material jobs, eight initial empty carts, and two operators for cart circulation | 100 appendix material jobs and 100 cart returns, scheduled on the illustrated network with one assumed road length |
| Red/Purple, two Red AGVs and one Purple AGV | 100 material jobs across both tracks, shared physical intersections, and charging | An eight-job example with intersection, charging, and battery events |
| Factory | Routes across four tracks, track and factory makespan, workload, applicable energy consumption, and computation time | Track-level experiments. The factory result depends on the official Red/Purple topology, battery rules, and schedule. |

The Yellow experiment uses the track-specific configuration of 100 material jobs, eight initial carts, and two operators. The case overview describes a different configuration with two loading stations and 20 initial carts at each. The Red/Purple case specifies both unlimited battery capacity and recharging. For Red, the track-specific materials list a moving consumption rate of 0.02%, while the case overview lists 0.05%. The reproducible example uses its own battery parameters. The full model requires confirmation of the rate and its basis, battery use while waiting at the depot, the extent of the intersection zones, and charging queues.



## 2. Mathematical formulation

We plan trips for fleet $K_r$ on the directed graph $G_r=(V_r,E_r)$ of track $r$. For job $j$, let $L_j$, $U_j$, $r_j$, and $D_j$ denote its loading station, unloading station, release time, and time-window upper bound. Binary variable $x_{jk}$ indicates whether vehicle $k$ performs job $j$. A visit records its node, arrival time $a$, departure time $d$, and action. Repeated visits to a physical node have separate records. All vehicles travel at 0.5 m/s, so travel time is road length divided by speed.

### 2.1 Objective and job constraints

Let $J_M$ denote the material jobs, $J_C$ the Yellow empty-cart returns, and $C_j$ the unloading completion time for job $j$. The objective is to minimize material makespan $C_M=\max_{j\in J_M}C_j$. For Yellow, we also report $C_{M+C}=\max_{j\in J_M\cup J_C}C_j$, the last depot return, and the last manual delivery. The Yellow experiment generates one cart return per material job under its end-of-run cleanup policy. Both strategies use the same scope.

$$
\sum_{k\in K_{r(j)}}x_{jk}=1,\qquad
\sum_{j:\,r(j)=r}x_{jk}\ge 1\quad(k\in K_r).
$$

$$
s_j^L\ge r_j,\qquad s_j^U\ge s_j^L+p_j^L,\qquad
C_j=s_j^U+p_j^U\le D_j.
$$

Loading and unloading take $p_j^L$ and $p_j^U$, respectively, each 16 s on Green and Yellow. Every trip starts and ends at the depot and completes at least one transport job. A vehicle carries at most one job at a time. In a paired trip, it unloads the first job before traveling to the second loading station. The implementation treats the appendix value of 99,999 s as an unloading deadline and applies the same bound to generated Yellow cart returns.

### 2.2 Routes, headway, and depot use

Consecutive visits to $u,v$ on a trip require a directed arc $(u,v)\in E_r$ with $a_v=d_u+\tau_{uv}$. The travel interval is $[d_u,a_v)$. Both directions of the same physical bidirectional edge use a single reservation calendar. The implementation also reserves one-way edges exclusively as a conservative way to prevent overtaking. At a public node or shared intersection, the reservation is $[a,d+2\,\text{s})$. Reservations for the same resource must be pairwise disjoint.

Under the Green shared-junction rule, departures, returns, and mid-trip visits to Start reserve the public node for 2 s. Longer waits before departure or after return take place in separate parking bays. Paired routes can pass through Start. The trip ID in the visit log identifies trip boundaries. Treating every passage through Start as a trip end would require a different model and confirmation of the official parking and access layout. The comparison also includes the original rule, which exempts Start from node reservations.

Kim and Tanchoco [2] use available time windows to search for conflict-free routes on bidirectional AGV networks. Here, reservations serve as a feasibility check for a fixed path. If a reservation conflicts, the scheduler shifts the trip's departure.

### 2.3 Yellow empty-cart circulation

The industrial pallet scheduling study by Zhou et al. [3] illustrates how limited material carriers can constrain production scheduling. In the Yellow case, the relevant carriers are the empty carts.

Loading a material job requires an available empty cart. After unloading the material, Operator 1 moves the cart from the unloading station to the pickup station. An AGV takes it to the return station, and Operator 2 brings it back to the loading station. Each operator takes 480 s for a one-way trip. The cart becomes available upon delivery. The operator can take another assignment after the 960 s round trip. For material job $j$ and its corresponding return $q(j)$, let $u_j$ and $v_j$ denote the start times of the two manual transfers.

$$
u_j\ge C_j,\qquad s^L_{q(j)}\ge u_j+480,\qquad
v_j\ge C_{q(j)}.
$$

The same cart ID is tracked throughout this chain. The cart's next loading can start at or after $v_j+480$. The operators occupy $[u_j,u_j+960)$ and $[v_j,v_j+960)$, respectively. Intervals for a given operator cannot overlap. A paired material and return trip can use a generated cart-return job when the cart is ready by the time the vehicle reaches the pickup station.

### 2.4 Red/Purple intersection and battery model

Nodes that represent the same physical Red/Purple intersection share a reservation resource. The full instance requires a mapping for every intersection. In the example, $B$ is the battery level on arrival. Travel of duration $\Delta t$ uses $\rho_{\mathrm{move}}\Delta t$, and a loading or unloading stop uses $\rho_{\mathrm{service}}\Delta t$. At least 10% must remain after each travel or service step. Charging reserves the charging node and restores the battery to 100%. If a trip would breach the reserve without charging, the algorithm tries fully charging after departure and before service. The full instance still requires rules for energy use while waiting, charging queues along the track, and interrupted charging. Parking at the depot uses zero energy in the example.

Singh et al. [4] jointly schedule transport and charging and allow partial recharging. Their formulation provides a reference for extending this example to variable charging durations.

## 3. Solution strategy and tools

1. Compute Dijkstra shortest paths between the required service points on each directed track. [5]
2. Build single-job candidates for each vehicle. The Green pairing policy can add the earliest-released pending job at the other loading station after the first delivery. The Yellow pairing policy can append the earliest-released generated cart return after a material job.
3. Determine the earliest start from vehicle availability, job release times, and cart availability. If a road or node conflict occurs, shift the entire trip later and check reservations, deadlines, and battery again. Vehicles wait for traffic in their depot bays.
4. Rank candidates by preference for an unused vehicle, earlier first unloading, more jobs per trip, and earlier return. When Yellow is short of carts, rank standalone returns by when the cart will be available after manual delivery. The Green comparison also tests ranking by average trip turnaround per job and by the mean of the first and last unloading times.
5. Commit the trip reservations and update vehicle, job, cart, and operator states. Rebuild and check resource use from the exported visit events. Green uses 1 s ticks and Yellow uses 0.1 s ticks. Integer comparisons preserve travel times computed from decimal road lengths.

If a candidate occupies a resource during $[\alpha,\beta)$ relative to departure and an existing reservation occupies $[u,v)$, a conflict occurs when $t+\alpha<v$ and $t+\beta>u$. Shift the departure $t$ to at least $v-\alpha$ and repeat the checks. This method constructs feasible schedules by ranking candidates heuristically. The code uses the Python 3.10+ standard library, with `heapq` for shortest paths, `bisect` for reservation lookup, and `perf_counter` for wall-clock solve time. Node.js checks the replay data and interaction logic.



## 4. Results and discussion

### 4.1 Green 100-job experiment

We checked the job IDs, stations, release times, and deadlines against all 100 appendix entries. The Green case drawing shows the nine physical edges listed below. The accompanying descriptions list eight. We transcribed the 5.5 m `LoadingStation2–T4` segment as bidirectional. No tested schedule visits `T4`. The other edges comprise five one-way and three bidirectional segments. The official topology is needed to resolve the discrepancy.

| Segment in the Green case drawing | Direction | Length | Travel time |
| --- | --- | ---: | ---: |
| Start – UnloadingStation1 | → | 5 m | 10 s |
| UnloadingStation1 – T2 | → | 8.5 m | 17 s |
| T2 – T3 | → | 3.5 m | 7 s |
| T3 – LoadingStation1 | → | 2.5 m | 5 s |
| LoadingStation1 – T1 | → | 11 m | 22 s |
| T1 – Start | ↔ | 3.5 m | 7 s |
| T1 – UnloadingStation2 | ↔ | 20.5 m | 41 s |
| UnloadingStation2 – LoadingStation2 | ↔ | 13 m | 26 s |
| LoadingStation2 – T4 | ↔ | 5.5 m | 11 s |

| Depot rule | Single-job baseline | Two-job trips | Turnaround per job | Mean unloading time |
| --- | ---: | ---: | ---: | ---: |
| Shared Start reserved | 13,012 s | **8,641 s** | 9,534 s | 13,012 s |
| Start exempt | 12,924 s | **8,641 s** | 9,534 s | 12,924 s |

With shared Start reservations, pairing reduced the last unloading time by 4,371 s, or **33.59%**. With Start exempt, it fell by 33.14%. The original baseline fails the shared-junction conflict check, so the main comparison uses a baseline regenerated under the shared-junction rule. Pairing produced the shortest makespan of the tested strategies with either depot rule.

| Metric under the shared-junction rule | Single-job baseline | Two-job trips |
| --- | ---: | ---: |
| Last depot return | 13,070 s | 8,689 s |
| Total trips (two-job trips) | 100 (0) | 56 (44) |
| Cumulative driving time | 17,904 s | 13,680 s |
| Traversals of T1–UnloadingStation2 | 200 | 112 |
| Jobs completed by V01 / V02 / V03 | 50 / 49 / 1 | 49 / 48 / 3 |

Pairing reduces shared-edge crossings and trips back to the depot. The workload remains concentrated on two vehicles. A conservative lower bound is **4,469 s**. Each job requires a loaded crossing of `T1–UnloadingStation2`, with 56 loaded crossings in one direction and 44 in the other. Returning all vehicles to the depot requires at least 12 additional crossings in the opposite direction. At most one required crossing per vehicle can remain after the last unloading time, so at least 109 required crossings must occur by then. Each occupies the exclusive edge for 41 s, giving $109\times41$. This bound only captures the shared-edge bottleneck and leaves a gap to the 8,641 s schedule.

### 4.2 Yellow 100-job experiment with empty-cart returns

The Yellow case drawing shows two bidirectional access links near Start and a loop with seven one-way edges. Eight lengths are labeled. We used **41.6 m**, the length of the opposite upper segment, for the unlabeled `T1→T2` segment and exposed it as a configurable parameter. Under this assumption, both strategies complete 100 material jobs, 100 AGV cart returns, and 200 manual transfers. A confirmed length for the lower segment would allow the comparison to be rerun.

| Metric | Separate single-job trips | Paired material and return trips |
| --- | ---: | ---: |
| Last material unloading | 90,452.7 s | **89,027.9 s** |
| Last unloading across all AGV jobs | 95,903.8 s | 95,903.8 s |
| Last AGV return to depot | 95,966.2 s | 95,966.2 s |
| Last empty cart delivered to the loading station by hand | 98,303.8 s | 96,511.6 s |
| Total trips (paired trips) | 200 (0) | 107 (93) |
| Y_V01, material / return jobs | 96 / 7 | 96 / 100 |
| Y_V02, material / return jobs | 4 / 93 | 4 / 0 |

Pairing reduces material makespan by 1,424.8 s, or about **1.58%**, and saves 93 trips. The final AGV return job finishes at the same time in both schedules, consistent with the manual cart circulation rate limiting the benefit of pairing. With the specified cart and operator configuration, completing all 100 material jobs within a hard eight-hour shift is infeasible.

A material makespan lower bound for the assumed network is **88,900.1 s**. With eight initial carts and 100 loadings, at least 92 loadings depend on a returned cart. The earliest first material delivery is $13.7+196.3=210.0$ s. The 92nd required manual outbound transfer can arrive at the pickup station no earlier than $210.0+91\times960+480$ s. That cart still requires at least 173.8 s for AGV pickup, transport, and unloading, 480 s for the second manual transfer, and 196.3 s for the next material move with loading and unloading. The paired schedule is 127.8 s above this bound. The bound ignores vehicle conflicts, interactions between operator queues, and job release delays.

### 4.3 Red/Purple mechanism test and computing environment

The synthetic network reserves one intersection jointly. Red and Purple each complete four material jobs, with makespans of 300 s and 444 s, respectively. All vehicles return by 452 s. The three vehicles complete 2 / 2 / 4 jobs and use 95.6, 95.6, and 195.2 percentage points of charge cumulatively. The schedule contains five complete charges. The test rates are 1.20 percentage points/s in motion and 0.25 percentage points/s during loading or unloading. Charge durations are 90 s on Red and 60 s on Purple. These parameters are chosen to trigger the charging logic.

The computing environment was Windows 11 Build 26200, an Intel Core Ultra 5 338H processor with 12 logical processors, and Python 3.12.14. The corresponding `summary.json` records the wall-clock time for each case as a single-run measurement. Green and Yellow use unlimited battery capacity, and their route files use the appendix's default battery value of 100.

### 4.4 Verification and remaining work

Eight Green schedules, two Yellow schedules, and the Red/Purple example passed CSV read-back and constraint checks. The verifier reconstructs each vehicle's trips, movements, node and intersection occupancy, load and unload events, and time windows. Yellow checks also cover cart IDs, operator round trips, and inventory. Red/Purple checks cover battery use and charging along the route. Negative checks cover a removed job, a changed travel time, a Start conflict created by reusing the old baseline under the shared-junction rule, and a cart return labeled as material.

The full factory experiment requires all 100 Red/Purple appendix jobs, a confirmed mapping of the physical intersections and the roads subject to no overtaking, and confirmed charging rules and energy results. With a common time origin, factory material makespan is the maximum of the track-level material makespans. Fixed shortest paths, whole-trip shifts, and exclusive reservations on all one-way edges limit the scheduling choices explored by the heuristic.



## 5. Simulation demo and reproducibility

Run the following commands from the project directory. The default output paths are resolved relative to the scripts.

```powershell
python demo/run_demo.py
python demo/run_extensions.py
node demo/check_replay.cjs
```

The length of the lower segment `T1 → T2` is unspecified in the Yellow Track diagram. The demo uses **41.6 m** as an estimate, based on the labeled length of the opposite upper segment. When the Yellow road length is confirmed, rerun with `python demo/run_extensions.py --yellow-bottom-edge-m <length>`. The length is in metres and must be a positive multiple of 0.05 m. Green results are in `demo/results/`. Yellow and the Red/Purple example are in `demo/results/extensions/`.

| File | How to check it |
| --- | --- |
| `replay/EE6228_AGV_Replay.html` | Open offline in Edge or Chrome. Use **Shared-edge handoff** and **Next job on the same trip**, then check the 100-job completion and return of all AGVs. |
| `visits.csv` | Reconstruct the schedule using each vehicle's trip and visit numbers, node, action, arrival, and departure. |
| `job_schedule.csv` | Check assignments, time windows, and completion times. Yellow adds the cart ID and the job ID used in the route TXT. |
| `manual_transfers.csv` | Check departure, one-way delivery, and round-trip availability for Yellow. Operator IDs 0 and 1 represent the two manual transfer legs. |
| `agv_routes.txt` | Check the eight-field route export. The TXT combines parking-bay waits at the depot. Use the CSV for precise trip boundaries. |
| `comparison.csv`, `summary.json` | Check policies, performance metrics, solve time, and validation status. |

The Green replay uses visit events read back from the export. The script checks eight configurations, all job completion boundaries, shared-edge occupancy, playback, and switching between cases. Chrome checks cover playback, policy switching, material completion, and vehicle returns.



![](.\The demo replay's interactive interface.png)

(The demo replay's interactive interface)



## 6. References

1. Le-Anh, T., & de Koster, M. B. M. (2006). A review of design and control of automated guided vehicle systems. *European Journal of Operational Research, 171*(1), 1–23. [DOI](https://doi.org/10.1016/j.ejor.2005.01.036)
2. Kim, C. W., & Tanchoco, J. M. A. (1991). Conflict-free shortest-time bidirectional AGV routeing. *International Journal of Production Research, 29*(12), 2377–2391. [DOI](https://doi.org/10.1080/00207549108948090)
3. Zhou, Y., Du, S., Lv, J., Shen, X., Matta, A., & Wang, S. (2025). Flexible pallet automation system scheduling with limited fixture-pallets and material-pallets: A case study from an engine manufacturing enterprise. *Journal of Manufacturing Systems, 83*, 357–371. [DOI](https://doi.org/10.1016/j.jmsy.2025.09.015)
4. Singh, N., Dang, Q.-V., Akcay, A., Adan, I., & Martagan, T. (2022). A matheuristic for AGV scheduling with battery constraints. *European Journal of Operational Research, 298*(3), 855–873. [DOI](https://doi.org/10.1016/j.ejor.2021.08.008)
5. Dijkstra, E. W. (1959). A note on two problems in connexion with graphs. *Numerische Mathematik, 1*, 269–271. [DOI](https://doi.org/10.1007/BF01386390)
