# EE6228 AGV Scheduling

Start with the [project report](EE6228_Report_Materials_EN.md). The [revision checklist](review/EE6228_Demo_Revision_Checklist_EN.md) records the changes and their verification. The [annotated draft](review/EE6228_Report_Annotated_EN.md) documents the original review. The [five-member work plan](EE6228_Team_Work_Plan_EN.md) assigns ownership and review.

| Scenario | Data | Main result |
| --- | --- | --- |
| Green | 100 appendix jobs and nine edges transcribed from the problem figure | Pairing reduces the last unloading time from 13,012 s to 8,641 s with shared Start reservations. |
| Yellow | 100 appendix material jobs, 100 generated cart returns, and two operators | With T1→T2 set to 41.6 m, pairing reduces the last material unloading time from 90,452.7 s to 89,027.9 s. |
| Red/Purple | Eight synthetic jobs | Three vehicles share one physical intersection and perform five charges. |

## Reproduction

```powershell
python demo/run_demo.py
python demo/run_extensions.py
node demo/check_replay.cjs
```

The scheduler uses the Python 3.10+ standard library. Node.js checks the Green replay. To rerun Yellow with another length, pass `--yellow-bottom-edge-m <length>` to `demo/run_extensions.py`. Use metres in positive multiples of 0.05 m.

- Green comparisons are in `demo/results/comparison.csv`. Each policy directory has a job schedule, visit log, TXT routes, and metrics.
- Yellow and the Red/Purple example are in `demo/results/extensions/`. Yellow adds cart IDs, TXT job ID mappings, and `manual_transfers.csv`.
- Open `replay/EE6228_AGV_Replay.html` in a browser to view the offline demo. The initial view uses shared Start reservations and two-job trips. Use the trip IDs in `visits.csv` to distinguish departure, return, and mid-trip passage through Start.

## Topology and output conventions

The Green text describes eight edges, while the figure shows nine segments. The report lists each segment and direction. The schedules do not traverse `LoadingStation2–T4`. Green and Yellow model parking waits in separate bays and reserve 2 s for shared Start access. The eight-field TXT route export combines parking-bay waits. Full Red/Purple scheduling requires the official topology, intersection mapping, and a consistent battery model.
