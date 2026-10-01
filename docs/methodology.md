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

## Real-World Deployment
A real deployment would train on the service's own health-monitoring data, strictly on-premise and offline, using actual SAP/ERP integration for spares and work orders.
