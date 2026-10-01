# Vayu Drishti - Presentation Outline

## Slide 1: Problem
- **Fragmented Data:** Fleet health, maintenance records, spares, and flight schedules are often siloed.
- **Delayed Prediction:** Faults are identified too late, causing unscheduled downtime.
- **Sub-optimal Utilisation:** Aircraft are grounded while waiting for spares, reducing fleet availability.

## Slide 2: Architecture & Key Idea
- **Integrated Data Layer:** Merging sensor predictions with synthetic maintenance logs, spares stock, workshops, and flight schedules.
- **Digital Twin:** Lightweight per-aircraft health twin enabling live state monitoring and what-if analysis.
- **Mission-Aware Planner:** Recommends maintenance slots before failure that avoid assigned missions and verify spares availability.

## Slide 3: Results (To Fill)
- **Model Performance (RMSE):** [TO FILL - e.g., XX.XX]
- **Alert Lead Time:** [TO FILL - e.g., XX cycles before failure]
- **Reactive vs Predictive Policy:** [TO FILL - e.g., X% increase in fleet readiness]

## Slide 4: Limitations & Future Work
- **Limitations:** 
  - Model trained on public civil engine data (NASA C-MAPSS).
  - Spares, schedules, and maintenance records are purely synthetic.
  - Real deployment would require on-premise training on actual military health-monitoring data.
- **Future Work:**
  - Real-time telemetry ingest (MQTT/Kafka).
  - Deep Learning architectures (LSTMs/1D-CNN) on larger datasets (N-CMAPSS).
  - Expanding to other subsystems (e.g., Bearings, Batteries).
