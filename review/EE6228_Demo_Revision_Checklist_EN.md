# EE6228 Revision Checklist

| Review finding | Change made | Verification or remaining work |
| --- | --- | --- |
| The factory requirements and original demo scope were mixed | List requirements for all four tracks, reproducible experiment sizes, and remaining gaps. Remove the aggregate improvement rate for mixed-size cases. | The factory result requires the full Red/Purple schedule. |
| The two Green depot rules require matching baselines | Rerun the baseline with shared Start reservations. Keep the original rule for sensitivity analysis and list the road segments transcribed from the figure. | The main comparison is 13,012 s versus 8,641 s. The original baseline fails the shared Start conflict check. Confirm the official topology. |
| Yellow used only 12 jobs | Use all 100 appendix jobs, transcribe the loop, parameterize T1→T2, and record manual transfers and cart IDs. | Both cases pass read-back checks with 41.6 m assumed. Rerun when the length is confirmed. |
| Percentage improvements alone can obscure the bottleneck | Report material delivery, cart returns, and depot returns separately. Add bounds, workloads, and the computing environment. | Green material makespan fell by 33.59% and Yellow by 1.58%. The final AGV job finished at the same time in both Yellow cases. |
| Generated return jobs were hard to verify | Reconstruct expected returns from problem stations, material jobs, and manual deliveries. Add a validation check for an incorrect job type. | The verifier rejects an empty-cart return labeled as material. |
| TXT routes obscure trip boundaries at Start | Keep the eight-field export and record departure, return, trip ID, and exact times in `visits.csv`. | Eight Green cases, two Yellow cases, and the Red/Purple example pass read-back checks. |
| The Red/Purple example used accelerated charging | Label the eight-job case as a mechanism test and document inconsistent battery rates in the problem documents. | The rerun covers a shared intersection and five charges. The full instance requires confirmed topology, intersections, and charging rules. |
