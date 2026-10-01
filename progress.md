# Project 26249: Air Power, Predictive Maintenance & Fleet Availability

**Deadline:** 5 October 2026 (submit in the morning, do not plan to build on the 5th)
**Team:** Solo Developer (ML, Data, Dashboard & Integration)
**Status key:** `[ ]` to do, `[~]` in progress, `[x]` done
**Version:** v2.1 (revised 1 Oct 2026; consolidated for single-agent execution; adds digital twin, reactive-vs-predictive metric, mission-aware planning, deployment, and fixes found in review)

---

## 0. Requirement traceability (does the plan cover the problem statement?)

| Problem statement says | What we build | Where it shows in the demo |
|---|---|---|
| Fragmented data: health monitoring, technical records, spares, maintenance agencies | One integrated data layer joining sensor predictions, maintenance logs, spares stock, workshops, flight schedule | Aircraft detail page, spares check |
| Delayed fault prediction | RUL model (XGBoost on C-MAPSS FD001) with risk level and predicted failure date | Fleet dashboard, risk turning amber then red |
| Avoidable aircraft downtime | Spares-aware alerts plus a maintenance recommender that plans slots before failure | Alerts panel, planner |
| Sub-optimal utilisation of critical assets | Mission-aware scheduling: maintenance slots avoid assigned missions where possible; availability forecast | Planner, forecast chart |
| AI/ML predictive maintenance | RUL regression, reported RMSE and alert lead time | Metrics slide |
| IoT / aircraft health monitoring | Simulated sensor stream (replay of engine rows) through an ingest module that could be swapped for MQTT | "Play simulation" button |
| Digital twins | Lightweight per-aircraft health twin: live state from the stream, what-if (extra flight hours) | Aircraft detail page, what-if panel |
| Integrated maintenance analytics platform | Streamlit app, single codebase, runs from `requirements.txt` | Whole demo |
| **Proof that it helps (goal is availability)** | Reactive vs predictive policy simulation on the synthetic fleet | Results slide |

---

## 1. Scope

| Original idea | Now |
|---|---|
| PostgreSQL + TimescaleDB | **SQLite or plain CSV files** |
| FastAPI + React + Tailwind | **Streamlit** (one Python app) |
| MQTT / Kafka live feed | **Simulated feed:** replay rows with a button or timer |
| LSTM / 1D-CNN | **XGBoost first.** LSTM only if everything else is done |
| N-CMAPSS | **Skip.** Future work |
| Docker | **Optional**, Day 4 only if time remains |
| Role-based login | **Skip.** Future work |
| Bearings / Battery datasets | **Skip for the build** (downloaded already; see section 2) |

**Must-have (the project is submittable with just this):**
1. RUL model on C-MAPSS FD001 with reported RMSE (evaluated the standard way, see section 6)
2. Synthetic maintenance logs, spares, workshops, flight schedule linked to aircraft
3. Dashboard: fleet status, risk, predicted failure date
4. Spares-aware alert plus a maintenance recommendation that respects the flight schedule
5. Availability forecast (next 30 days)
6. **Reactive vs predictive comparison** (the proof that the platform raises availability)
7. **Digital twin view** per aircraft (sensor replay plus health state)
8. Deployed link, README, pitch slides, backup demo video

**Should-have (only after the Day 3 checkpoint is green):** what-if panel (RUL after +50 flight hours), SHAP "top reasons" column.

**Nice-to-have:** anomaly detector, LSTM, a second component from the Bearings data.

---

## 2. Data inventory

| File downloaded | Size | Use | Action |
|---|---|---|---|
| `6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip` | 11.9 MB | **Main dataset.** Use FD001 | [x] Downloaded. Unzip, keep `train_FD001.txt`, `test_FD001.txt`, `RUL_FD001.txt` |
| `CMAPSSData.zip` | 11.9 MB | Same data from a mirror (same size) | Duplicate. Compare checksums, then delete one |
| `4.+Bearings.zip` | 1.0 GB | Not needed for must-haves | Keep **outside the repo**. Optional second-component stretch only |
| `5.+Battery+Data+Set.zip` | 200 MB | Not needed | Keep **outside the repo**. Future work |

**What the real data does not contain:** spares, workshops, technical/maintenance records, flight schedules, tail numbers. No public military dataset has these, so they are **synthetic**. This is expected, and the README and slides must say so plainly.

**Honest framing (use in README and pitch):** C-MAPSS is a public NASA *civil turbofan simulation*, not data from any real air force fleet. We use it to show the method. A real deployment would train on the service's own health-monitoring data, on-prem and offline.

---

## 3. Project Responsibilities & Architecture

| Role | Responsibilities |
|---|---|
| **Solo Developer** | Data, models, predictions, synthetic tables, simulation logic, Streamlit App, planner, alerts, forecast chart, deployment, README, and pitch slides |

### 3.1 `predictions.csv` (define immediately to build UI concurrently)

| Column | Example |
|---|---|
| `aircraft_id` | `AF-1042` |
| `component` | `engine` |
| `predicted_rul_cycles` | `38.5` |
| `predicted_failure_date` | `2026-11-14` |
| `risk_level` | `amber` |
| `health_score` | `62.0` |
| `generated_at` | `2026-10-01 10:30` |
| `top_reasons` (optional) | `sensor_11, sensor_4` |

Risk thresholds: red below 30 cycles, amber 30 to 80, green above 80.

**Cycles to dates:** one cycle = one flight. `predicted_failure_date = generated_at + predicted_rul_cycles / flights_per_day`, where `flights_per_day` comes from each aircraft's row in `aircraft_master` (about 0.8 to 2). Write this assumption in the README.

### 3.2 Synthetic tables (generate early for app consumption)

| Table | Key columns |
|---|---|
| `aircraft_master` | `aircraft_id`, `type` (generic label, no real type claimed), `base`, `flights_per_day`, `total_flight_hours`, `engine_ids` |
| `maintenance_logs` | `log_id`, `aircraft_id`, `component`, `date`, `kind` (scheduled/unscheduled), `action`, `downtime_days` |
| `parts_catalog` | `component`, `part_no`, `lead_time_days` |
| `spares_inventory` | `part_no`, `depot`, `qty_on_hand`, `reorder_level` |
| `workshops` | `workshop_id`, `location`, `capacity_slots`, `turnaround_days`, `specialisation` |
| `flight_schedule` | `date`, `aircraft_id`, `mission_id`, `priority` |

**Fleet design:** 24 aircraft, 2 engines each (48 engines drawn from the 100 FD001 test engines). Pick engines so the fleet starts roughly 65% green, 25% amber, 10% red. Aircraft risk equals the worst engine. Non-engine components, if shown, are rule-based and labelled **simulated** on screen.

---

## 4. Day-by-day plan

### Day 1: Thursday 1 Oct (today): foundations

- [x] Download datasets (C-MAPSS, Bearings, Battery)
- [x] Unzip item 6, confirm the three FD001 files; delete the duplicate zip
- [x] Load FD001, name columns, compute RUL (`max_cycle - cycle`, clipped at about 125)
- [x] Drop constant columns (check by std; typically operating setting 3 and sensors 1, 5, 10, 16, 18, 19 in FD001), scale using train statistics only
- [x] **Split train engines by engine ID** (hold out about 20 engines for validation and for the demo replay). Never split by row, which leaks.
- [x] Add simple rolling features (rolling mean and slope over the last 5 to 10 cycles) and train the XGBoost baseline
- [x] Compute RMSE on the FD001 test set (last cycle per engine vs `RUL_FD001.txt`)
- [x] Start the synthetic generator (aircraft master first)
- [x] Create the repo and folders; Streamlit skeleton; `.gitignore` (exclude zips and raw data)
- [x] **Check what the submission portal requires today** (format, size, links, video, deck) - portal lists no requirements; plan for repo link + deployed link + slides + video
- [x] Make **dummy** `predictions.csv` (correct columns) so the UI can be built now
- [x] Fleet overview page on dummy data: cards or table coloured green/amber/red
- [x] Draft slide outline and README skeleton (include the traceability table from section 0)

**End of day checkpoint:** baseline RMSE exists, dummy dashboard runs, portal requirements known.

---

### Day 2: Friday 2 Oct: real predictions and core screens

- [x] Finish the synthetic generator (all six tables); map engines to tail numbers; save CSVs to `/data`
- [x] Generate real `predictions.csv` for the 24-aircraft fleet
- [x] Record metrics: RMSE, predicted vs true RUL plot, **alert lead time** (cycles between the first red alert and failure, on held-out engines)
- [x] Write the replay function (steps through a held-out engine's rows and returns the updated prediction per step)
- [x] Aircraft detail page: sensor trend chart, predicted failure date, maintenance history
- [x] Load synthetic CSVs into the app (use `@st.cache_data`)
- [x] Swap dummy predictions for the real `predictions.csv` file
- [x] Spares check: join failing component to `parts_catalog` and `spares_inventory`, compare lead time with days to failure

**End of day checkpoint:** dashboard shows real predictions with detail pages.

---

### Day 3: Saturday 3 Oct: planner, forecast, proof, demo story

- [x] Availability forecast logic (aircraft ready over the next 30 days given predicted failures, workshop turnaround and spares lead time). Define "ready" = not in a workshop and no red-risk component.
- [x] **Reactive vs predictive simulation:** run about 200 Monte Carlo runs over 90 days. Reactive = fix after failure (diagnosis delay plus part lead time if out of stock plus repair). Predictive = planned slot, part ordered ahead. Keep all downtime parameters in one config file and report a sensitivity range.
- [x] Should-have: what-if function (predicted RUL after +50 flight hours, converted to cycles)
- [x] Write the methodology section (public NASA data plus synthetic logs, honest limits)
- [x] Maintenance recommender: rank jobs by risk, suggest slot and workshop, **avoid assigned missions in `flight_schedule` where possible** and show "missions affected"
- [x] Spares-aware alerts ("part fails in 12 days, stock is zero, lead time 20 days, order now")
- [x] Availability forecast chart ("next 30 days: 18 of 24 ready")
- [x] **Digital twin panel** on the detail page: live health state, sensor replay, predicted failure date updating as the stream advances
- [x] "Play simulation" button wired to the replay function
- [x] Results panel: reactive vs predictive readiness chart
- [ ] **First deploy to Streamlit Community Cloud** (pinned `requirements.txt`, relative paths, small files only)

**End of day checkpoint (most important):** full demo story runs end to end once, locally and on the deployed link, with no crashes.

---

### Day 4: Sunday 4 Oct: freeze features, package and rehearse

**No new features after midday**
- [ ] Fix bugs from a full run-through
- [ ] README: problem, architecture, setup steps, data sources, synthetic-data disclosure, assumptions, limitations, future work, note that real deployment is on-prem/offline
- [ ] Pitch slides (3 to 5): problem, architecture, key idea (integration plus digital twin), results (RMSE, alert lead time, reactive vs predictive), limitations and future work
- [ ] **Record the backup demo video** (screen recording)
- [ ] Rehearse the demo twice with a timer (5 minutes)
- [ ] Test from a fresh clone (`pip install -r requirements.txt`, run command works)
- [ ] Redeploy and open the link once to wake it
- [ ] Optional: Docker Compose if everything else is done
- [ ] Zip or push everything: code, README, slides, video, metrics

**End of day checkpoint:** submission package complete.

---

### Day 5: Monday 5 Oct: submit

- [ ] Re-check portal requirements against the package
- [ ] Open the deployed link a few minutes before submitting (free apps can be asleep)
- [ ] **Submit in the morning**, leaving buffer for upload problems
- [ ] No last-minute code changes

---

## 5. Demo story (5 minutes)

1. Fleet dashboard, mostly green; one line on integrated data (sensors, records, spares, workshops, schedule)
2. Press "Play simulation": one aircraft's digital twin starts receiving degrading sensor data
3. Risk turns amber then red; predicted failure date appears
4. Spares check shows the part is out of stock, so an order alert is raised
5. Planner suggests a slot and workshop that avoids that aircraft's missions
6. Availability forecast recovers after the fix
7. Results: reactive vs predictive readiness, RMSE, alert lead time
8. Limitations slide: public civil-engine data, synthetic records, on-prem path

---

## 6. Evaluation and honest claims

- **RMSE:** compute on the FD001 test set using the last observed cycle of each test engine vs `RUL_FD001.txt`. Report the number you actually get; published baselines are commonly in the mid-teens to about 20, so do not promise a figure in advance.
- **Alert lead time:** on held-out engines, how many cycles before failure the first red alert fires. This is the metric a maintainer cares about.
- **Reactive vs predictive:** the result comes from simulation parameters we chose, not from real fleet evidence. Say so, show the config, and show a sensitivity range.
- **Never claim** the data is from real military aircraft, or that the model is validated on a real fleet.

---

## 7. Working agreements

- One repo, `main` always runs. Commit small and often; push before sleeping.
- Folders: `/data` (small files only), `/ml`, `/app`, `/docs`.
- Do not commit raw datasets or zips. Commit only small CSVs, the saved model file (joblib or JSON) and `predictions.csv`.
- Train offline; the app only loads the saved model.
- If a task takes more than half a day, cut it or simplify it.

---

## 8. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Model not ready in time | Keep working on dummy data for the UI; ship XGBoost only |
| Accuracy looks weak | Report honest RMSE; focus on the platform and the availability result |
| Streamlit Community Cloud fails or runs out of memory | Hugging Face Spaces or Render; always keep the local copy |
| App asleep or Wi-Fi fails at demo | Local copy, then the backup video |
| Day 3 overloaded | Cut what-if and SHAP; prioritize core spares-check and alert rules |
| Ran out of time | Cut should-haves; the must-have list is a complete project |
| Submission format unclear | Checked on Day 1; recheck on Day 5 |

---

## 9. Progress log

| Date | Done | Blockers |
|---|---|---|
| 1 Oct | Folders setup, files organized. RUL baseline XGBoost trained. Synthetic generator and predictions created. Dashboard skeleton built. Day 1 cleanup pass completed and verified. | Portal check and duplicate zip pending (owner: me) |
| 2 Oct | Synthetic tables complete. Core metrics added to evaluate.py. Replay function implemented. Aircraft detail and Digital Twin UI built. Spares checking logical rules implemented. (Done on 1 Oct, logged as Day 2 in progress) | |
| 3 Oct | | |
| 4 Oct | | |