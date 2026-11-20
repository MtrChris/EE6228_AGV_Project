# EE6228 Five-Member Work Division



## Work Division

| Member | Name | Matriculation Number | Primary responsibility | Concrete deliverable | Report and presentation |
| --- | --- | --- | --- | --- | --- |
| 1 | WANG MINGQIAN | G2609368J | Requirements, mathematical model, and report integration | Trace the assignment requirements to model constraints. Maintain the common notation, scope, and assumptions, then assemble the final report. | Lead Sections 1–2 and consolidate Section 6. |
| 2 | SU YIHENG | G2609392A | Core solver and Green experiments | Own shortest paths, resource reservations, candidate ranking, the fair baseline, and all eight Green comparisons. Supply a reproducible results table and the shared-edge lower bound. | Lead Section 3 and Section 4.1. |
| 3 | WANG XIN | G2601742D | Yellow cart circulation and analysis | Check all 100 jobs, model the eight carts and two operators, verify the transfer chain, and document the assumed segment length and labor bottleneck. | Write Sections 2.3 and 4.2. |
| 4 | QIN ZHAOYI | G2601122G | Red/Purple intersection and battery model | Check the shared-resource mapping, verify the eight-job charging example, and document the topology and battery inputs required for the full instance. Calculate a factory makespan only if a complete schedule becomes available. | Write Sections 2.4 and 4.3. |
| 5 |  |  | Independent verification and optional replay | Reproduce all cases from a clean project copy, compare CSV and TXT outputs, and prepare the submission package. | Lead Sections 4.4 and 5. |



## Handoffs and review

1. **Agree on the model.** Members 1–4 sign off on inputs and assumptions. Member 5 records the reproducibility checklist and the expected outputs.
2. **Run the experiments.** Members 2–4 provide code, inputs, assumptions, and run outputs to Member 5. Member 2 reviews Yellow model integration, Member 3 checks the interpretation of Red/Purple results, and Member 4 reviews the Green reservation rules.
3. **Reproduce and submit.** Member 5 runs the clean-package checks. Member 1 reconciles report numbers with the verified outputs. All five approve the scope, claims, references, and one shared final report.



## Project schedule and meeting log

**Project window:** 06 October–18 November 2026.

### Milestones

| Gate | Milestone                         | Lead    | Meeting | Acceptance check                                             |
| ---- | --------------------------------- | ------- | ------- | ------------------------------------------------------------ |
| K01  | Kickoff                           | M1      | MT01    | Agree scope, roles, shared IDs and time units.               |
| K02  | Inputs frozen for the experiments | M2–M4   | MT02    | Check task lists and topology assumptions. Publish the reproduction checklist. |
| K03  | Model review                      | M1      | MT03    | Review objectives, depot rules, resource constraints, cart circulation and battery assumptions. |
| K04  | Track models integrated           | M2–M4   | MT04    | Run the core solver, Yellow cart loop and Red/Purple mechanism example using common exports. |
| K05  | Experiment results review         | M2–M4   | MT05    | Deliver eight Green cases, two Yellow cases and one Red/Purple mechanism case for independent checks. |
| K06  | English report draft review       | M1      | MT06    | Review one integrated draft with matching scenario scopes, tables and references. |
| K07  | Release review                    | M5      | MT07    | Reproduce results from a clean copy, check the English replay and resolve discrepancies. |
| K08  | Final handoff                     | M1 / M5 | MT08    | Approve the report and package. Record delivery evidence for the group. |



### Deliverables by member

Each member has four planned items. After delivery, update the log status.

#### M1 · Requirements, model and report integration

| ID   | Deliverable and acceptance check                             | Reviewer | Meeting | Log status |
| ---- | ------------------------------------------------------------ | -------- | ------- | ---------- |
| D1.1 | Requirements and scope matrix. Identify each scenario, report sections and optional simulation. | M4       | MT01    | Open       |
| D1.2 | Common mathematical model. Record the objective, job rules, reservations and assumptions in Sections 1–2. | M2       | MT03    | Open       |
| D1.3 | Integrated English draft. Align results tables with report claims and reconcile all references. | M5       | MT06    | Open       |
| D1.4 | Final English report. Incorporate peer comments and check claims against the clean rerun. | M5       | MT08    | Open       |

#### M2 · Core solver and Green Track

| ID   | Deliverable and acceptance check                             | Reviewer | Meeting | Log status |
| ---- | ------------------------------------------------------------ | -------- | ------- | ---------- |
| D2.1 | Green inputs. Check all 100 jobs, the road transcription and the two Start rules. | M4       | MT02    | Open       |
| D2.2 | Core solver. Implement shortest paths, candidate ranking, reservations and common exports. | M4       | MT04    | Open       |
| D2.3 | Green result bundle. Rerun two depot rules × four policies and check 13,012 s versus 8,641 s under the shared rule. | M5       | MT05    | Open       |
| D2.4 | Finish Sections 3 and 4.1 with the bottleneck analysis. Review the Yellow solver integration. | M1       | MT06    | Open       |

#### M3 · Yellow Track and empty-cart circulation

| ID   | Deliverable and acceptance check                             | Reviewer | Meeting | Log status |
| ---- | ------------------------------------------------------------ | -------- | ------- | ---------- |
| D3.1 | Yellow inputs. Check all 100 jobs, eight initial carts, two operators and the 41.6 m road assumption. | M2       | MT02    | Open       |
| D3.2 | Cart circulation implementation. Check inventory, cart IDs, and the 480 s / 960 s manual timing. | M2       | MT04    | Open       |
| D3.3 | Yellow result bundle. Compare two policies with 100 material jobs, 100 cart returns and 200 manual transfers per case. | M5       | MT05    | Open       |
| D3.4 | Finish Sections 2.3 and 4.2. Explain material completion versus cleanup and check Red/Purple interpretation. | M1       | MT06    | Open       |

#### M4 · Red/Purple intersections and energy

| ID   | Deliverable and acceptance check                             | Reviewer | Meeting | Log status |
| ---- | ------------------------------------------------------------ | -------- | ------- | ---------- |
| D4.1 | Red/Purple input review. Check appendix job counts and document topology and battery ambiguities. | M1       | MT02    | Open       |
| D4.2 | Intersection and charging logic. Reserve a shared crossing and check the 10% reserve in the synthetic setup. | M3       | MT04    | Open       |
| D4.3 | Mechanism result bundle. Verify eight synthetic jobs, one shared intersection and five full charges. | M5       | MT05    | Open       |
| D4.4 | Finish Sections 2.4 and 4.3. State full-instance gaps and review the Green reservation rules. | M1       | MT06    | Open       |

#### M5 · Independent verification and optional demo

| ID   | Deliverable and acceptance check                             | Reviewer | Meeting | Log status |
| ---- | ------------------------------------------------------------ | -------- | ------- | ---------- |
| D5.1 | Reproduction checklist. Define the clean run commands, expected CSV/TXT files and verification criteria. | M1       | MT02    | Open       |
| D5.2 | Verification report. Run read-back and constraint checks on all 11 cases and compare route exports. | M2       | MT05    | Open       |
| D5.3 | Clean-package and Chrome check. Verify the English replay, release candidate and Sections 4.4–5. | M1       | MT07    | Open       |
| D5.4 | Final package. Match it to the approved report and archive the handoff evidence. | M1       | MT08    | Open       |
