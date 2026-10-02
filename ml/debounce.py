import pandas as pd

def debounce_series(series, threshold=3):
    if len(series) == 0:
        return series.copy()
        
    out = []
    current_state = series.iloc[0]
    candidate_state = current_state
    count = 0
    
    for val in series:
        if val == current_state:
            candidate_state = current_state
            count = 0
        else:
            if val == candidate_state:
                count += 1
            else:
                candidate_state = val
                count = 1
                
            if count >= threshold:
                current_state = candidate_state
                count = 0
                
        out.append(current_state)
        
    return pd.Series(out, index=series.index)
