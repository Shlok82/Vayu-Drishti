# Project 26249: Air Power, Predictive Maintenance and Fleet Availability

**Deadline:** 20 October 2026
**Team:** Solo Developer (ML, Data, Dashboard and Integration)
**Status key:** `[ ]` to do, `[x]` done
**Version:** v3 (consolidated; includes login, 3D twin, live deployment)

---

## 0. Requirement traceability (does the plan cover the problem statement?)

| Problem statement says | What we build | Where it shows in the demo |
|---|---|---|
| Fragmented data: health monitoring, technical records, spares, maintenance agencies | One integrated data layer joining sensor predictions, maintenance logs, spares stock, workshops, flight schedule | Aircraft detail page, spares check |
| Delayed fault prediction | RUL model (XGBoost on C-MAPSS FD001) with risk level and predicted failure date | Fleet dashboard, risk turning amber then red |
| Avoidable aircraft downtime | Spares-aware alerts plus a maintenance recommender that plans slots before failure | Alerts panel, planner |
| Sub-optimal utilisation of critical assets | Mission-aware scheduling: maintenance slots avoid assigned missions where possible; availability forecast | Planner, forecast chart |
| AI/ML predictive maintenance | RUL regression, reported RMSE and alert lead time | Results page |
| IoT / aircraft health monitoring | Simulated sensor stream (replay of engine rows) through an ingest module that could be swapped for MQTT | Digital Twin "Play simulation" button |
| Digital twins | Lightweight per-aircraft health twin: live state from the stream, what-if (extra flight hours), interactive 3D view | Aircraft detail page, Digital Twin page |
| Integrated maintenance analytics platform | Streamlit app, single codebase, runs from `requirements.txt` | Whole demo |
| **Proof that it helps (goal is availability)** | Reactive vs predictive policy simulation on the synthetic fleet | Results page |

---

## 1. Scope

| Original idea | Now |
|---|---|
| PostgreSQL + TimescaleDB | **SQLite or plain CSV files** (done) |
| FastAPI + React + Tailwind | **Streamlit** (one Python app, done) |
| MQTT / Kafka live feed | **Simulated feed:** replay rows with a button or timer (done) |
| LSTM / 1D-CNN | **Not implemented** (moved to future work) |
| N-CMAPSS | **Not implemented** (moved to future work) |
| Docker | **Not implemented** (moved to future work) |
| Role-based login | **Implemented** as a demo access-control layer with viewer, maintainer and admin roles |
| Bearings / Battery datasets | **Not implemented** (moved to future work) |

**Must-have (the project is submittable with just this):**
1. RUL model on C-MAPSS FD001 with reported RMSE (evaluated the standard way, see section 6) [x]
2. Synthetic maintenance logs, spares, workshops, flight schedule linked to aircraft [x]
3. Dashboard: fleet status, risk, predicted failure date [x]
4. Spares-aware alert plus a maintenance recommendation that respects the flight schedule [x]
5. Availability forecast (next 30 days) [x]
6. **Reactive vs predictive comparison** (the proof that the platform raises availability) [x]
7. **Digital twin view** per aircraft (sensor replay plus health state and 3D airframe view) [x]
8. Deployed link [x], README [x], pitch slides and backup demo video (moved to Remaining before submission)

**Should-have:**
- What-if panel (predicted RUL after extra flight hours) [x]
- SHAP top reasons column: moved to future work

**Nice-to-have:**
- Anomaly detector, LSTM, second component from Bearings data: moved to future work

---

## Implemented beyond the original plan

- [x] Reproducible build pipeline (`ml/build_all.py`, producing identical model and dataset artifacts across runs)
- [x] Mission-aware maintenance planner with earliest-feasible-finish scheduling and high-priority mission conflict flags (`ml/planner.py`, `app/pages/3_Planner.py`)
- [x] Spares-aware alerts linking component failure dates, depot inventory levels, and supplier lead times (`ml/alerts.py`)
- [x] 30-day fleet availability forecasting engine (`ml/forecast.py`, `data/forecast_30d.csv`)
- [x] Monte Carlo reactive-vs-predictive policy simulation across 200 runs x 90 days with sensitivity sweeps and dedicated UI (`ml/simulate_policies.py`, `app/pages/4_Results.py`)
- [x] Transparent Methodology page explaining simulation boundaries, assumptions, and formulas (`app/pages/5_Method.py`, `docs/methodology.md`)
- [x] Interactive what-if flight hours stress slider on Aircraft Detail (`ml/whatif.py`, `app/pages/1_Aircraft_Detail.py`)
- [x] Multi-sensor z-score deviation chart on Aircraft Detail (`app/pages/1_Aircraft_Detail.py`)
- [x] Digital twin live sensor replay with debounced temporal state transitions (`ml/debounce.py`, `app/pages/2_Digital_Twin.py`)
- [x] Role-based authentication and page-level access control across viewer, maintainer, and admin tiers (`app/auth.py`, `docs/DEMO_ACCESS.md`)
- [x] Illustrative per-module wear degradation model and JSON payload generator (`ml/module_wear.py`, `app/twin3d.py`)
- [x] Interactive 3D digital twin (Three.js and OrbitControls via CDN) embedded in the Digital Twin page (`app/twin3d.py`, `app/pages/2_Digital_Twin.py`)
- [x] Comprehensive self-check verification suites (97 tests: 22 Day 1, 16 Day 2, 59 Day 3 in `ml/check_day*.py`)
- [x] Clean virtual environment deployment verification check (`ml/deploy_check.py`)
- [x] Split dependency specifications (`requirements.txt` for runtime, `requirements-dev.txt` for developer tooling)
- [x] Production deployment documentation (`docs/DEPLOY.md`)
- [x] Live public cloud deployment on Streamlit Community Cloud (https://vayu-drishti.streamlit.app/)
- [x] Comprehensive documentation and README with live demo link and test credentials

---

## Not implemented (future work)

- Docker Compose container packaging
- SHAP feature attribution top_reasons column (top_reasons column in predictions.csv remains empty)
- Anomaly detector baseline (isolation forest or autoencoder)
- Deep learning sequence models (LSTM or 1D-CNN)
- Bearings dataset secondary rotating component model
- N-CMAPSS multi-operating condition dataset integration
- Battery dataset auxiliary power degradation model

---

## 2. Data inventory

| File downloaded | Size | Use | Action |
|---|---|---|---|
| `6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip` | 11.9 MB | **Main dataset.** Use FD001 | [x] Downloaded. Unzipped, kept `train_FD001.txt`, `test_FD001.txt`, `RUL_FD001.txt` |
| `CMAPSSData.zip` | 11.9 MB | Same data from a mirror (same size) | [x] Duplicate. Verified identical and removed |
| `4.+Bearings.zip` | 1.0 GB | Not needed for must-haves | Kept outside repo. Moved to future work |
| `5.+Battery+Data+Set.zip` | 200 MB | Not needed | Kept outside repo. Moved to future work |

**What the real data does not contain:** spares, workshops, technical/maintenance records, flight schedules, tail numbers. No public military dataset has these, so they are **synthetic**. This is expected, and the README and slides say so plainly.

**Honest framing (use in README and pitch):** C-MAPSS is a public NASA civil turbofan simulation, not data from any real air force fleet. We use it to show the method. A real deployment would train on the service's own health-monitoring data, on-premise and offline.

---

## 3. Project Responsibilities and Architecture

| Role | Responsibilities |
|---|---|
| **Solo Developer** | Data, models, predictions, synthetic tables, simulation logic, Streamlit App, planner, alerts, forecast chart, deployment, README, and pitch slides |

### 3.1 `predictions.csv` (real values from first row of data/predictions.csv)

| Column | Example |
|---|---|
| `aircraft_id` | `AF-1001` |
| `component` | `engine_1` |
| `predicted_rul_cycles` | `111.1` |
| `predicted_failure_date` | `2027-02-16` |
| `risk_level` | `green` |
| `health_score` | `88.9` |
| `generated_at` | `2026-10-20 09:00` |
| `top_reasons` (optional) | *(blank)* |

Risk thresholds: red below 30 cycles, amber 30 to 80, green above 80.

**Cycles to dates:** one cycle = one flight. `predicted_failure_date = generated_at + predicted_rul_cycles / flights_per_day`, where `flights_per_day` comes from each aircraft's row in `aircraft_master` (about 0.8 to 2). Fixed demo as-of date is 20 October 2026.

### 3.2 Synthetic tables (generated for app consumption)

| Table | Key columns |
|---|---|
| `aircraft_master` | `aircraft_id`, `type` (generic label, no real type claimed), `base`, `flights_per_day`, `total_flight_hours`, `engine_ids` |
| `maintenance_logs` | `log_id`, `aircraft_id`, `component`, `date`, `kind` (scheduled/unscheduled), `action`, `downtime_days` |
| `parts_catalog` | `component`, `part_no`, `lead_time_days` |
| `spares_inventory` | `part_no`, `depot`, `qty_on_hand`, `reorder_level` |
| `workshops` | `workshop_id`, `location`, `capacity_slots`, `turnaround_days`, `specialisation` |
| `flight_schedule` | `date`, `aircraft_id`, `mission_id`, `priority` |

**Fleet design:** 24 aircraft, 2 engines each (48 engines drawn from the 100 FD001 test engines). Picked engines so the fleet starts roughly 65% green, 25% amber, 10% red. Aircraft risk equals the worst engine. Non-engine components, if shown, are rule-based and labelled **simulated** on screen.

---

## 4. Day-by-day plan

### Day 1: foundations

- [x] Download datasets (C-MAPSS, Bearings, Battery)
- [x] Unzip item 6, confirm the three FD001 files; delete the duplicate zip
- [x] Load FD001, name columns, compute RUL (`max_cycle - cycle`, clipped at 125)
- [x] Drop constant columns (check by std; operating setting 3 and sensors 1, 5, 10, 16, 18, 19 in FD001); no feature scaling (XGBoost is scale-invariant)
- [x] **Split train engines by engine ID** (hold out 20 engines for validation and demo replay). Never split by row.
- [x] Add rolling features (rolling mean and slope over the last 10 cycles) and train the XGBoost baseline
- [x] Compute RMSE on the FD001 test set (last cycle per engine vs `RUL_FD001.txt`)
- [x] Start the synthetic generator (aircraft master first)
- [x] Create repo structure; Streamlit skeleton; `.gitignore` (exclude zips and raw data)
- [x] Check submission portal requirements (repo link, deployed link, slides, video)
- [x] Make dummy `predictions.csv` (correct columns) so UI can be built concurrently
- [x] Fleet overview page on dummy data: cards and table coloured green/amber/red
- [x] Draft slide outline and README skeleton (include traceability table from section 0)

### Day 2: real predictions and core screens

- [x] Finish synthetic generator (all six tables); map engines to tail numbers; save CSVs to `/data`
- [x] Generate real `predictions.csv` for the 24-aircraft fleet
- [x] Record metrics: RMSE, predicted vs true RUL, **alert lead time** (cycles between first red alert and failure on held-out engines)
- [x] Write replay function (steps through held-out engine rows and returns updated prediction per step)
- [x] Aircraft detail page: sensor trend chart, predicted failure date, maintenance history
- [x] Load synthetic CSVs into the app (using `@st.cache_data`)
- [x] Swap dummy predictions for real `predictions.csv` file
- [x] Spares check: join failing component to `parts_catalog` and `spares_inventory`, compare lead time with days to failure

### Day 3: planner, forecast, proof, demo story

- [x] Availability forecast logic (aircraft ready over next 30 days given predicted failures, workshop turnaround and spares lead time)
- [x] **Reactive vs predictive simulation:** 200 Monte Carlo runs over 90 days with sensitivity analysis
- [x] What-if function (predicted RUL after extra flight hours)
- [x] Write methodology section (public NASA data plus synthetic logs, honest limits)
- [x] Maintenance recommender: rank jobs by risk, suggest slot and workshop, avoid assigned missions in `flight_schedule`, show missions affected
- [x] Spares-aware alerts ("part fails in 12 days, stock is zero, lead time 20 days, order now")
- [x] Availability forecast chart ("next 30 days: 18 of 24 ready")
- [x] **Digital twin panel** on detail page: live health state, sensor replay, predicted failure date updating as stream advances
- [x] "Play simulation" button wired to replay function
- [x] Results panel: reactive vs predictive readiness chart
- [x] First deploy to Streamlit Community Cloud (pinned `requirements.txt`, relative paths; live at https://vayu-drishti.streamlit.app/)

### Day 4: freeze features, package and rehearse

- [x] Fix bugs from full run-through (verified across 97 self-checks in `ml/check_day*.py`)
- [x] README: problem, architecture, setup steps, data sources, synthetic-data disclosure, assumptions, limitations, future work, note that real deployment is on-premise/offline
- [x] Test from a fresh install (`ml/deploy_check.py` clean virtualenv test with `requirements.txt`)
- [x] Redeploy and open the link once to verify live status (HTTP 200 confirmed)

### Day 5: submit

See Remaining before submission.

---

## Remaining before submission

- [ ] Pitch slides (3 to 5 slides)
- [ ] Record backup demo video (screen recording)
- [ ] Rehearse demo with a timer (5 minutes)
- [ ] Re-check portal requirements against final package
- [ ] Open deployed link a few minutes before submitting (free apps can be asleep)
- [ ] Zip or push final submission package
- [ ] Submit in portal buffer window

---

## 5. Demo story (5 minutes)

1. **Login Gate:** Enter demo credentials (e.g. maintainer user `maintainer` with password `vd_maintainer_2026`).
2. **Fleet Overview:** Review fleet readiness cockpit (24 aircraft, 48 engines; green/amber/red distribution; quick filter by risk).
3. **Aircraft Detail:** Drill down into critical aircraft AF-1002 (engine_1 red risk); observe sensor trends, maintenance history, and test the what-if flight hours stress slider.
4. **Digital Twin Replay and 3D View:** On AF-1001, click "Play simulation" to stream held-out sensor cycles; observe debounced status transitions (OK -> WATCH -> ORDER NOW), live RUL updates, and inspect the interactive 3D twin airframe view.
5. **Planner:** Review the 30-day proactive maintenance schedule; verify recommended slots, workshop capacity allocation, and deconfliction against assigned missions in `flight_schedule`.
6. **Results:** Examine the Monte Carlo policy simulation results (86.4% reactive to 92.1% predictive availability, +5.7 percentage points lift, 58% reduction in unscheduled downtime), along with sensitivity sweeps.
7. **Methodology:** Review transparent methodology disclosures regarding synthetic logistics data, NASA C-MAPSS civil engine simulation, and offline air-gapped deployment pathways.

---

## 6. Evaluation and honest claims

- **RMSE:** compute on the FD001 test set using the last observed cycle of each test engine vs `RUL_FD001.txt`. Reported RMSE is 19.35 raw and 18.27 clipped at 125 cycles.
- **Alert lead time:** on held-out engines, cycles between the first red alert and failure. Mean debounced lead time is 24.4 cycles (approx. 16.2 days), providing maintainers adequate runway.
- **Reactive vs predictive:** the result comes from simulation parameters we chose, not from real fleet evidence. Transparently documented in `ml/sim_config.py` with sensitivity ranges on lead times and false alarms.
- **Never claim** the data is from real military aircraft, or that the model is validated on a real fleet.

---

## 7. Working agreements

- One repo, `main` always runs. Small, verified commits.
- Folders: `/data` (small CSVs and precomputed artifacts only), `/ml`, `/app`, `/docs`.
- Do not commit raw datasets or zip archives.
- Train offline; the app only loads precomputed models and cached simulation results.
- If a task takes more than half a day, simplify or cut it.

---

## 8. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Model not ready in time | Keep working on dummy data for UI; ship XGBoost baseline only |
| Accuracy looks weak | Report honest RMSE; focus on integrated platform and availability gains |
| Streamlit Community Cloud fails or runs out of memory | Local presentation copy plus backup video |
| App asleep or Wi-Fi fails at demo | Run local Streamlit instance, then fall back to backup video |
| Day 3 overloaded | Cut what-if and SHAP; prioritize core spares-check and alert rules |
| Ran out of time | Cut optional features; must-have scope forms a complete submittable system |
| Submission format unclear | Verify submission portal guidelines early |

---

## Known limitations

- **Synthetic data:** Flight schedules, spares inventory, workshop capacities, and maintenance records are purely synthetic simulations.
- **Civil turbofan simulation:** Predictive model is trained on NASA C-MAPSS FD001 civil engine simulation data, not real military flight telemetry.
- **Illustrative module wear:** Per-module wear percentages (fan, compressor, combustor, turbine) are calculated from an illustrative allocation model; NASA C-MAPSS lacks per-module wear annotations.
- **CDN dependency of 3D view:** The 3D view dynamically loads Three.js and OrbitControls from jsDelivr; an air-gapped military environment requires bundling these libraries locally.
- **Demo-only security:** Authentication and role-based access control are demonstrative and not intended for production security; real deployments require enterprise SSO/PKI.
- **Free cloud hosting:** The Streamlit Community Cloud deployment may sleep after a period of inactivity; a wake-up button click is required to re-initialize the instance.

---

## 9. Progress log

| Stage | Done | Blockers |
|---|---|---|
| Day 1: foundations | Repository setup, XGBoost RUL baseline trained, data ingestion and feature engineering, dummy predictions, initial Fleet Overview view | None |
| Day 2: core screens | Synthetic generator (6 tables), real predictions, held-out telemetry replay, Aircraft Detail view, spares inventory checking | None |
| Day 3: planner and results | Availability forecast logic, 200-run Monte Carlo policy simulation, proactive mission-aware planner, digital twin live replay, Methodology page | None |
| Day 4: hardening and packaging | Comprehensive test suites (Day 1, 2, 3 passing 97 tests), clean virtualenv deployment verification script, dependency split, deployment docs | None |
| Stages L1 and L2: access control | SHA-256 demo user authentication, constant-time hash verification, session state login gate, page-level role-based authorization | None |
| Stages T1 to T3: 3D digital twin | Illustrative module wear model, twin JSON payload builder, Three.js 3D jet viewer, debounced replay synchronization | None |
| Stage Docs and Deploy: live release | Live Streamlit Community Cloud deployment, DEPLOY.md, DEMO_ACCESS.md, architecture flowcharts, README update | None |
