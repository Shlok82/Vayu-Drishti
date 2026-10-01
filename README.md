# Vayu Drishti

> Predictive maintenance for higher fleet availability

## Problem
Fragmented data, delayed fault prediction, avoidable aircraft downtime, and sub-optimal utilisation of critical assets plague fleet maintenance, reducing overall availability. "Vayu Drishti" aims to solve this by providing an integrated view of aircraft health, anticipating failures before they occur, and prescribing maintenance intelligently.

## Architecture

```text
[ Sensor Stream / Logs ] ---> [ Data Layer ] ---> [ XGBoost Model ]
                                      |                   |
[ Spares & Workshops ]  --------------+                   v
                                                [ Streamlit Dashboard ]
                                                (Fleet Digital Twin & Planner)
```
- **Data Layer:** Merges synthetic maintenance logs, spares stock, workshops, and flight schedules.
- **Model:** XGBoost RUL (Remaining Useful Life) regression based on NASA's C-MAPSS dataset.
- **App:** Streamlit UI providing a fleet digital twin, alerts, and mission-aware planner.

## Setup
1. Clone this repository.
2. Create and activate a virtual environment:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install dependencies: 
   ```cmd
   pip install -r requirements.txt
   ```
4. Run the ML pipeline:
   ```cmd
   python ml\train_baseline.py
   python ml\make_synthetic.py
   python ml\make_predictions.py
   ```
5. Run the application: 
   ```cmd
   streamlit run app\main.py
   ```

## Data Sources
- **Sensor Data:** [NASA C-MAPSS (Commercial Modular Aero-Propulsion System Simulation)](https://ti.arc.nasa.gov/tech/dash/groups/pcoe/prognostic-data-repository/) FD001 dataset.
- **Citation:** Saxena et al. 2008, "Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation".

## Synthetic-Data Disclosure
C-MAPSS is a public NASA *civil turbofan simulation*, not data from any real air force fleet. We use it to show the method. What the real data does not contain: spares, workshops, technical/maintenance records, flight schedules, and tail numbers. No public military dataset has these, so they are **purely synthetic**. 

## Assumptions
- One cycle in the dataset corresponds to one flight.
- **Cycles-to-date rule:** `predicted_failure_date = AS_OF + predicted_rul_cycles / flights_per_day` (where `flights_per_day` comes from each aircraft's row).
- **RUL is clipped at 125 cycles:** Predictions above this are considered healthy (green).
- **No feature scaling:** We do not scale features because tree-based models like XGBoost are scale-invariant.
- **Engine-ID Split:** We strictly split train/validation data by engine ID, never by row, to prevent data leakage.

## Model Performance
- **Environment:** Python 3.13.5 | XGBoost 3.4.1
- **Validation RMSE:** 16.24 (on 20 held-out engines)
- **Test RMSE (Raw):** 19.35 (Evaluated on the last cycle of each test engine vs `RUL_FD001.txt` as provided)
- **Test RMSE (Clipped):** 18.27 (Evaluated on the last cycle, with true RUL capped at 125 cycles)

## Traceability

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

## Limitations & Real-world Deployment
- The model is trained on public civil engine data, not a real military fleet.
- Maintenance records, schedules, and spares data are purely synthetic simulations.
- **Deployment Note:** A real deployment would train on the service's own health-monitoring data, strictly on-premise and offline.

## Future Work
- Full digital twin implementation using MQTT/Kafka for real-time telemetry instead of simulated data feed.
- Extending predictive models to include more complex architectures like LSTMs or 1D-CNNs on the larger N-CMAPSS dataset.
- Adding more components (like Bearings and Battery modules).
