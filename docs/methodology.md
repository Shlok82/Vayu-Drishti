# Methodology

## Data Sources
- **Sensor Data:** NASA C-MAPSS (Commercial Modular Aero-Propulsion System Simulation) FD001 dataset. 
- **Disclaimer:** This is a public civil turbofan simulation. It is NOT data from any real military fleet.

## Synthetic Data
Since public military datasets do not contain spares, workshops, maintenance records, flight schedules, or tail numbers, these are purely **synthetic simulations**. The UI and outputs label them as such.

## Model
- **Algorithm:** XGBoost Regressor predicting Remaining Useful Life (RUL).
- **Features:** 10-cycle rolling means and 9-cycle rolling slopes of sensor readings.
- **Rules:** RUL is capped at 125 cycles (healthy). Predictions are evaluated causally.

## Evaluation
- **Test RMSE:** Evaluated on the last cycle of each test engine compared to the NASA-provided ground truth.
- **Alert Lead Time:** The number of cycles between the first time a component's predicted RUL falls below the red threshold (< 30) and actual failure, evaluated on held-out training engines.

## Assumptions & Limitations
- One cycle = one flight.
- **Limitation:** The model is trained on a civil engine simulation.
- **Limitation:** The reactive vs. predictive readiness metrics rely on chosen simulation parameters (turnaround days, diagnosis delay), not empirical fleet evidence.

## Digital Twin & Simulation Details
- **Demo Aircraft & Replay:** The Digital Twin replays held-out NASA C-MAPSS engine unit 71 assigned to demo aircraft `AF-1001` (Generic Fighter Trainer, Base Charlie, 0.93 flights/day).
- **Simulation Horizon:** The Monte Carlo policy simulation runs over a 90-day horizon (`SIMULATION['days'] = 90`) across 200 iterations comparing reactive vs. predictive maintenance.

## Maintenance Scheduling & Conflict Logic
The planner prioritizes earliest feasible maintenance completion so that jobs finish before predicted failure dates. Mission conflicts are only a tie-break among equally early slots, and high-priority conflicts are flagged (`HIGH_PRIORITY_CONFLICT`).

## Real-World Deployment
A real deployment would train on the service's own health-monitoring data, strictly on-premise and offline, using actual SAP/ERP integration for spares and work orders.
- **Demo Access Control:** Authentication and role-based access control are demonstrative and not intended for production security; real deployments use enterprise SSO and encrypted stores.

## 3D Digital Twin Architecture
- **Telemetry & State Integration:** The 3D twin visualization receives predicted RUL, risk levels, and spares status directly from the machine learning model and the page's debounced temporal logic.
- **Illustrative Module Wear:** Module-level wear (fan, compressor, combustor, turbine) is calculated illustratively by applying fixed allocation factors to the engine-level predicted RUL. NASA C-MAPSS FD001 provides engine-level run-to-failure records without per-module degradation labels.
- **Engine Configuration:** The airframe model features dual engines; engine 1 displays dynamic per-cycle telemetry from the replayed engine, whereas engine 2 is shown static with values sourced from `data/predictions.csv`.
- **Client-Side Rendering & Offline Deployment:** The 3D view renders in client-side WebGL via Three.js and OrbitControls loaded from the jsDelivr CDN, requiring no frame-by-frame server roundtrips. An offline or air-gapped deployment would require these static JavaScript libraries to be bundled locally within the application package.

