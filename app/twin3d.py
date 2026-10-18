"""3D Digital Twin payload construction and telemetry packaging.

Builds JSON-serializable payloads combining replay telemetry, debounced state,
and module wear distributions for the 3D twin visualization.
"""

from typing import Any, Dict, List, Sequence, Union
import numpy as np
import pandas as pd
from ml.module_wear import module_wear_series, wear_from_rul

TWIN_DISCLAIMER = (
    "Illustrative module wear: engine-level predicted RUL allocated to modules "
    "with fixed factors. C-MAPSS has no per-module labels. Synthetic demo, not real fleet data."
)


def build_twin_payload(
    aircraft_id: str,
    engine_id: Union[int, str],
    replay_df: pd.DataFrame,
    debounced_status: Sequence[str],
    debounced_risk: Sequence[str],
    dates: Sequence[Any],
    engine2_rul: Union[float, int],
    engine2_risk: str,
) -> Dict[str, Any]:
    """Construct JSON-serializable payload for the 3D digital twin visualization.

    Does NOT import any Streamlit app pages. Caller supplies debounced status,
    risk, and cycle dates calculated from fleet/aircraft metadata.

    Args:
        aircraft_id: Aircraft identifier (e.g. 'AF-1001').
        engine_id: Primary engine identifier (e.g. 71).
        replay_df: DataFrame containing engine_1 replay cycles and predicted_rul.
        debounced_status: Sequence of debounced spares status strings per cycle.
        debounced_risk: Sequence of debounced risk level strings per cycle.
        dates: Sequence of cycle timestamp/date strings from the twin page logic.
        engine2_rul: Static predicted RUL cycles for engine_2.
        engine2_risk: Static risk level string for engine_2.

    Returns:
        JSON-serializable dict conforming to the twin payload schema.
    """
    cycles_list = [int(c) for c in replay_df["cycle"]]
    rul_list = [round(float(r), 1) for r in replay_df["predicted_rul"]]
    dates_list = [str(d) for d in dates]
    status_list = [str(s) for s in debounced_status]
    risk_list = [str(r) for r in debounced_risk]

    e1_wear = module_wear_series(rul_list)
    e2_wear = wear_from_rul(float(engine2_rul))

    payload: Dict[str, Any] = {
        "version": 1,
        "disclaimer": TWIN_DISCLAIMER,
        "aircraft_id": str(aircraft_id),
        "engine1": {
            "engine_id": int(engine_id),
            "cycles": cycles_list,
            "dates": dates_list,
            "rul": rul_list,
            "risk": risk_list,
            "status": status_list,
            "wear": {
                "fan": e1_wear["fan"],
                "compressor": e1_wear["compressor"],
                "combustor": e1_wear["combustor"],
                "turbine": e1_wear["turbine"],
            },
        },
        "engine2": {
            "static": True,
            "rul": round(float(engine2_rul), 1),
            "risk": str(engine2_risk),
            "wear": {
                "fan": round(float(e2_wear["fan"]), 1),
                "compressor": round(float(e2_wear["compressor"]), 1),
                "combustor": round(float(e2_wear["combustor"]), 1),
                "turbine": round(float(e2_wear["turbine"]), 1),
            },
            "note": "Static: engine 2 has no replay; value comes from predictions.csv.",
        },
    }

    return payload
