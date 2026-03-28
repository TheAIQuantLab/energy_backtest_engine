import pandas as pd
import numpy as np

def generate_features(df):
    """
    Applies vectorized pre-calculation ONLY for strict time contexts and base market aliases.
    All spreads and technical indicators are computed exclusively on-the-fly dynamically.
    """
    df = df.copy()
    orig_cols = set(df.columns)
    
    # --- Time Contexts ---
    df['GLOBAL_minutes_to_delivery'] = (df['deliverytime'] - df['tradingtime']).dt.total_seconds() / 60.0
    df['GLOBAL_hour_of_day'] = df['tradingtime'].dt.hour
    df['GLOBAL_day_of_week'] = df['tradingtime'].dt.dayofweek
    
    # --- Base Explicit Price Aliases for UI Purity ---
    if 'close' in df.columns:
        df['MIC_close'] = df['close'] 
    
    # --- Defensive Null/Inf Handling ---
    new_cols = list(set(df.columns) - orig_cols)
    if new_cols:
        df[new_cols] = df[new_cols].replace([np.inf, -np.inf], np.nan)
        df[new_cols] = df[new_cols].fillna(0)
    
    return df

def build_dynamic_feature(df, config):
    """
    Universal factory that parses a UI feature configuration dictionary, computes the feature 
    on the fly if it doesn't already exist, adds it to the DataFrame, and returns its column name.
    """
    ftype = config.get("type")
    
    if ftype == "Raw Price":
        col_name = config.get("market_col")
        # Ensure it exists (like SPOT_price or MIC_close) cleanly. Fallback to 0.0
        if col_name not in df.columns:
            df[col_name] = 0.0 
        return col_name
        
    elif ftype == "Time Context":
        col_name = config.get("time_col")
        if col_name not in df.columns:
            df[col_name] = 0.0
        return col_name
        
    elif ftype == "Spread":
        leg_a = config.get("leg_a")
        leg_b = config.get("leg_b")
        col_name = f"SPREAD_{leg_a}_minus_{leg_b}"
        if col_name not in df.columns:
            val_a = df[leg_a] if leg_a in df.columns else pd.Series(0.0, index=df.index)
            val_b = df[leg_b] if leg_b in df.columns else pd.Series(0.0, index=df.index)
            df[col_name] = val_a - val_b
        return col_name
        
    elif ftype == "Technical Indicator":
        source_col = config.get("source_col")
        indicator = config.get("indicator")
        period = int(config.get("period", 14))
        
        col_name = f"{source_col}_{indicator}_{period}"
        if col_name in df.columns:
            return col_name
            
        if source_col not in df.columns:
            df[col_name] = 0.0
            return col_name
            
        series = df[source_col]
        delivery_dates = df['deliverytime'].dt.date
        
        try:
            if indicator == 'SMA':
                res = df.groupby(delivery_dates)[source_col].transform(lambda x: x.rolling(window=period, min_periods=1).mean())
            elif indicator == 'EMA':
                res = df.groupby(delivery_dates)[source_col].transform(lambda x: x.ewm(span=period, adjust=False, min_periods=1).mean())
            elif indicator == 'STD':
                res = df.groupby(delivery_dates)[source_col].transform(lambda x: x.rolling(window=period, min_periods=1).std())
            elif indicator == 'ROC':
                res = df.groupby(delivery_dates)[source_col].transform(lambda x: x.pct_change(periods=period) * 100)
            elif indicator == 'RSI':
                def calc_rsi(s):
                    delta = s.diff()
                    up = delta.clip(lower=0)
                    down = -1 * delta.clip(upper=0)
                    roll_up = up.ewm(span=period, adjust=False).mean()
                    roll_down = down.ewm(span=period, adjust=False).mean()
                    rs = np.where(roll_down == 0, np.nan, roll_up / roll_down)
                    return 100.0 - (100.0 / (1.0 + rs))
                
                res = df.groupby(delivery_dates)[source_col].transform(calc_rsi)
            else:
                res = series
                
            res = res.replace([np.inf, -np.inf], np.nan).fillna(0)
            df[col_name] = res
        except Exception:
            df[col_name] = 0.0
            
        return col_name
        
    return None
