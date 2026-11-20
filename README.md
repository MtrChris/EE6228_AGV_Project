# EE6228 AGV scheduling experiments

The selected schedule uses eight vehicles for the 300 material orders in Appendix 1 of Problems 1–3 and 100 Yellow empty-cart returns. All reported times are seconds from the common simulation start. Factory material delivery finishes at 89,027.9 s. The last AGV unload, depot return and manual cart delivery occur at 95,903.8, 95,966.2 and 96,511.6 s, respectively.

## Read the outputs

| File or directory | Contents |
|---|---|
| `results/factory/job_schedule.csv` | The 400 assignments. Filter `kind=material` to see the 300 appendix jobs. Compare `release_s`, `load_start_s` and `unload_end_s` to distinguish order availability from vehicle service. |
| `results/factory/agv_routes.txt` | One line for each vehicle. The eight fields per visit are vehicle, arrival time, track-prefixed node, wait time, charge time, charge level on arrival, job ID and service completion time. The 800 job-bearing records were matched to the assignment table. |
| `results/factory/summary.json` | Factory and track completion times, job counts and material workload for each vehicle. |
| `data/appendix_jobs.csv` | Source station pairs, individual release times, deadlines and dwell times for all 300 jobs. |
| `data/problem3_edges.csv` | Directed Red/Purple graph. Each row gives its length in metres, direction and the figure or geometric assumption supporting it. |
| `results/problem3/` | The six power/dispatch combinations. Each completed case has a route, visit log, schedule, crossing log and summary. Cases with charging have a charging log. The incomplete per-second, single-job case records its stopping reason. |
| `results/length_sensitivity/comparison.csv` | Yellow results for lower road lengths of 33.6, 41.6 and 49.6 m. |
| `results/upstream/demo/results/` | The eight original Green configurations and the original extensions. The extensions include both Yellow schedules, their manual transfers and the separate eight-job Red/Purple mechanism example. |
| `results/upstream/replay/EE6228_AGV_Replay.html` | The offline interactive Green replay. Open it in a web browser to inspect the eight Green configurations. |

Global IDs 1–100 refer to Green, 101–200 to Yellow, 201–250 to Red and 251–300 to Purple. Their order within a track follows the printed appendix. Generated Yellow returns use 301–400. Their source material jobs and physical cart IDs appear separately in the factory CSV. The individual scenario directories retain their own job IDs. Travel and service use track-prefixed station names. At the Red/Purple crossings, the track-local waypoint names share resources X1 (A) and X2 (B).

## Reproduce the report

Use Python 3.10 or newer and the following revision of the base project. The scheduling scripts use the Python standard library. Install Node.js if you want the Green replay checker to run as well. From this extracted directory run the following commands.

```sh
git clone https://github.com/MtrChris/EE6228_AGV_Project.git
git -C EE6228_AGV_Project checkout 5d0ec287ad7a9682363f5dcb63975bacd235df21
python reproduce.py --project EE6228_AGV_Project --out rebuilt_results
```

Use `python3` or `py` in place of `python` where that is your Python 3 command. To reproduce only the selected Red/Purple schedule, run the following command from the same directory.

```sh
python run_problem3.py --project EE6228_AGV_Project --power per_second --policy paired --out rebuilt_problem3
```

The wrapper runs the base Green and Yellow models, the Yellow road-length sensitivity cases, all six Red/Purple cases and the combined TXT/CSV check. It records the Python version, Git revision, CPU and replay-check result in `environment.json`. Schedule values can be compared with the supplied outputs. Computation times depend on the machine.

## Interpretation

The selected schedule assumes a 41.6 m Yellow lower road. The Red/Purple model uses two point crossings with two-second headways and the track directions in the supplied edge list. The main battery case interprets the Problem 3 motion/wait rates as 0.02/0.01 percentage points per second, including time parked at the depot until each vehicle's final return. Red charges for eight hours and Purple for three. Charging can start before the 10% threshold to protect the reserve and keep the charger reachable. The two comparison cases calibrate consumption to eight hours of continuous motion or disable energy constraints. These are software schedules. Validation includes input matching and route replay. The course Unity testbed has not been run.
