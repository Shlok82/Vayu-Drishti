"""Pure functions for computing module-level wear from engine RUL.

The input is the per-cycle predicted RUL exactly as the Twin page plots it (from ml/replay).
C-MAPSS has no per-module labels, so module wear is allocated illustratively using fixed factors.
"""

from typing import Dict, List, Sequence, Union
import numpy as np
from ml.config import MODULE_WEAR_FACTORS, RUL_CLIP

MODULES = ["fan", "compressor", "combustor", "turbine"]


def wear_from_rul(
    rul: Union[float, int],
    rul_cap: Union[float, int] = RUL_CLIP,
) -> Dict[str, float]:
    """Calculate instantaneous module wear percentages from a single engine RUL value.

    Args:
        rul: Engine remaining useful life (RUL) in cycles.
        rul_cap: Maximum RUL threshold defining 0% baseline wear (default 125).

    Returns:
        Dict with module names ('fan', 'compressor', 'combustor', 'turbine') and wear values (0.0 to 100.0).
    """
    clipped_rul = float(np.clip(float(rul), 0.0, float(rul_cap)))
    overall = 100.0 * (1.0 - clipped_rul / float(rul_cap))
    wear: Dict[str, float] = {}
    for mod in MODULES:
        factor = MODULE_WEAR_FACTORS.get(mod, 1.0)
        wear_val = float(np.clip(overall * factor, 0.0, 100.0))
        wear[mod] = round(wear_val, 1)
    return wear


def module_wear_series(
    rul_series: Sequence[Union[float, int]],
    rul_cap: Union[float, int] = RUL_CLIP,
) -> Dict[str, List[float]]:
    """Compute monotonic cumulative module wear across a sequence of cycle RUL predictions.

    The input is the per-cycle predicted RUL exactly as the Twin page plots it (from ml/replay).
    Applies wear_from_rul per cycle, followed by a causal running maximum per module to ensure
    wear does not decrease from predictive noise, rounding each value to 1 decimal place.

    Args:
        rul_series: Sequence of per-cycle predicted RUL values.
        rul_cap: Maximum RUL threshold (default 125).

    Returns:
        Dict of four lists ('fan', 'compressor', 'combustor', 'turbine') of wear values.
    """
    out: Dict[str, List[float]] = {mod: [] for mod in MODULES}
    running_max: Dict[str, float] = {mod: 0.0 for mod in MODULES}

    for rul in rul_series:
        inst_wear = wear_from_rul(rul, rul_cap=rul_cap)
        for mod in MODULES:
            if inst_wear[mod] > running_max[mod]:
                running_max[mod] = inst_wear[mod]
            out[mod].append(round(running_max[mod], 1))

    return out
