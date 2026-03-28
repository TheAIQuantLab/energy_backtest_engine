import streamlit as st
import pandas as pd
import os

@st.cache_data(show_spinner=False)
def load_and_build_master_df(target_hour, data_dir=None):
    """
    Builds the Master 15m DataFrame pre-filtered for a specific target delivery hour 
    by snapping the auction publications synchronously onto the continuous MIC 15m timeframe.
    """
    if data_dir is None:
        # Default to 'data_simplified' in the project root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, 'data_simplified')
    
    markets = ['SPOT', 'IDA1', 'IDA2', 'IDA3', 'MIC', 'SETTLEMENT']
    dfs = {}
    
    for m in markets:
        path = os.path.join(data_dir, f"{m}.csv")
        if not os.path.exists(path):
            st.error(f"Missing {m}.csv in {data_dir}. Run simplify_data.py.")
            st.stop()
        df = pd.read_csv(path)
        df['tradingtime'] = pd.to_datetime(df['tradingtime'])
        df['deliverytime'] = pd.to_datetime(df['deliverytime'])
        
        # Pre-filter by user's targeted Delivery Hour
        df = df[df['deliverytime'].dt.hour == target_hour].copy()
        df = df.sort_values('tradingtime')
        dfs[m] = df

    # Extract MIC as the timeline backbone
    df_mic = dfs['MIC'].copy()
    if df_mic.empty:
        st.error(f"No MIC data found for Target Hour {target_hour}:00.")
        st.stop()
        
    # Generate full 15m timeline
    min_time = df_mic['tradingtime'].min()
    max_time = df_mic['tradingtime'].max()
    timeline = pd.date_range(start=min_time, end=max_time, freq='15min')
    df_master = pd.DataFrame({'tradingtime': timeline})
    
    # 1. Merge MIC OHLC (Left Join on Exact Timeline) 
    df_master = pd.merge(df_master, df_mic[['tradingtime', 'deliverytime', 'open', 'high', 'low', 'close']], 
                         on='tradingtime', how='left')
    
    # Forward fill liquidity gaps in MIC (flattening the bar)
    df_master['close'] = df_master['close'].ffill().bfill()
    df_master['open'] = df_master['open'].fillna(df_master['close'])
    df_master['high'] = df_master['high'].fillna(df_master['close'])
    df_master['low'] = df_master['low'].fillna(df_master['close'])
    df_master['deliverytime'] = df_master['deliverytime'].ffill().bfill()

    # 2. As-Of Merge Auctions & Settlement to completely prevent lookahead
    for m in ['SPOT', 'IDA1', 'IDA2', 'IDA3']:
        df_auction = dfs[m][['tradingtime', 'price']].rename(columns={'price': f"{m}_price"})
        # Fills forward chronologically *only* when the master tradingtime >= auction publish tradingtime
        df_master = pd.merge_asof(df_master, df_auction, on='tradingtime', direction='backward')

    # Settlement Prices
    df_set = dfs['SETTLEMENT'][['tradingtime', 'price_down', 'price_up']].rename(
        columns={'price_down': 'SETTLEMENT_DOWN', 'price_up': 'SETTLEMENT_UP'}
    )
    df_master = pd.merge_asof(df_master, df_set, on='tradingtime', direction='backward')
    
    return df_master, min_time, max_time

