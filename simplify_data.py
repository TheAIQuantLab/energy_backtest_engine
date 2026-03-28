import pandas as pd
import os
from datetime import datetime, timedelta
import pytz

# Configuration
DATA_DIR = 'data'
OUTPUT_DIR = 'data_simplified'
FILTER_DATE = '2025-01-01 00:00:00'
TZ_LOCAL = 'Europe/Paris'

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def convert_to_local(df, col='utcdatetime'):
    """Convert UTC column to French local time."""
    df[col] = pd.to_datetime(df[col])
    # Localize to UTC and then convert to Europe/Paris
    df[col] = df[col].dt.tz_localize('UTC').dt.tz_convert(TZ_LOCAL)
    # Remove timezone info for easier CSV handling (keep local time values)
    df[col] = df[col].dt.tz_localize(None)
    return df

def get_market_trading_time(delivery_time, market_type):
    """Calculate trading time based on market rules."""
    # Assuming delivery_time is already in local French time
    date_only = delivery_time.normalize()
    if market_type == 'SPOT':
        return date_only - pd.Timedelta(days=1) + pd.Timedelta(hours=12)
    elif market_type == 'IDA1':
        return date_only - pd.Timedelta(days=1) + pd.Timedelta(hours=15)
    elif market_type == 'IDA2':
        return date_only - pd.Timedelta(days=1) + pd.Timedelta(hours=22)
    elif market_type == 'IDA3':
        return date_only + pd.Timedelta(hours=10)
    return None

print("Starting data simplification process...")

# 1. SPOT Market
print("Processing SPOT...")
df_spot = pd.read_csv(os.path.join(DATA_DIR, 'spot_price_FR_2024_2025.csv'))
df_spot = df_spot[df_spot['utcdatetime'] >= FILTER_DATE]
df_spot = convert_to_local(df_spot)
df_spot['deliverytime'] = df_spot['utcdatetime']
df_spot['tradingtime'] = df_spot['deliverytime'].apply(lambda x: get_market_trading_time(x, 'SPOT'))
df_spot = df_spot[['tradingtime', 'deliverytime', 'price']].sort_values(['tradingtime', 'deliverytime'])
df_spot.to_csv(os.path.join(OUTPUT_DIR, 'SPOT.csv'), index=False)

# 2. IDA Markets (IDA1, IDA2, IDA3)
print("Processing IDAs...")
df_ida = pd.read_csv(os.path.join(DATA_DIR, 'intraday_session_FR_2024_2025.csv'))
df_ida = df_ida[df_ida['utcdatetime'] >= FILTER_DATE]
df_ida = convert_to_local(df_ida)

for session in ['IDA1', 'IDA2', 'IDA3']:
    df_s = df_ida[df_ida['session'] == session].copy()
    if df_s.empty:
        continue
    
    # Standardize to hourly (mean factor)
    df_s['deliverytime_h'] = df_s['utcdatetime'].dt.floor('h')
    df_s_h = df_s.groupby('deliverytime_h')['price'].mean().reset_index()
    df_s_h.rename(columns={'deliverytime_h': 'deliverytime'}, inplace=True)
    
    # Calculate trading time
    df_s_h['tradingtime'] = df_s_h['deliverytime'].apply(lambda x: get_market_trading_time(x, session))
    
    # Reorder and save
    df_s_h = df_s_h[['tradingtime', 'deliverytime', 'price']].sort_values(['tradingtime', 'deliverytime'])
    df_s_h.to_csv(os.path.join(OUTPUT_DIR, f'{session}.csv'), index=False)

# 3. MIC Market
print("Processing MIC...")
df_mic = pd.read_csv(os.path.join(DATA_DIR, 'mic_trades_FR_2024_2025.csv'))
df_mic = df_mic[df_mic['delivery_date'] >= '2025-01-01']

# Fix product codes (e.g., '9-10_XB' -> '09-10_XB')
df_mic['product'] = df_mic['product'].astype(str).apply(lambda x: '0' + x if x.startswith('9-') else x)

# Convert utcdatetime to local
df_mic = convert_to_local(df_mic)

# Determine delivery time from delivery_date and product
def parse_mic_delivery(row):
    start_hour = int(row['product'].split('-')[0])
    return pd.to_datetime(row['delivery_date']) + pd.Timedelta(hours=start_hour)

df_mic['deliverytime'] = df_mic.apply(parse_mic_delivery, axis=1)

# MIC natively runs on 15m intervals. Keep exactly the 15m intervals and OHLC columns.
df_mic['tradingtime'] = df_mic['utcdatetime']
df_mic_15m = df_mic[['tradingtime', 'deliverytime', 'open', 'high', 'low', 'close']].sort_values(['tradingtime', 'deliverytime'])
df_mic_15m.to_csv(os.path.join(OUTPUT_DIR, 'MIC.csv'), index=False)

# 4. SETTLEMENT Market (Imbalance)
print("Processing SETTLEMENT...")
df_imb = pd.read_csv(os.path.join(DATA_DIR, 'imbalance_FR_2025.csv'))
df_imb = df_imb[df_imb['utcdatetime'] >= FILTER_DATE]
df_imb = convert_to_local(df_imb)

# Separate UP and DOWN prices without averaging them together
df_imb['deliverytime_h'] = df_imb['utcdatetime'].dt.floor('h')
df_imb_h = df_imb.pivot_table(index='deliverytime_h', columns='type', values='imbalance_price', aggfunc='mean').reset_index()

# Rename columns to provide distinction
df_imb_h.rename(columns={'deliverytime_h': 'deliverytime', 'DOWN': 'price_down', 'UP': 'price_up'}, inplace=True)

# For SETTLEMENT, trading time is essentially the delivery time (when the data finalizes)
df_imb_h['tradingtime'] = df_imb_h['deliverytime']

# Filter columns and save
df_imb_h = df_imb_h[['tradingtime', 'deliverytime', 'price_down', 'price_up']].sort_values(['tradingtime', 'deliverytime'])
df_imb_h.to_csv(os.path.join(OUTPUT_DIR, 'SETTLEMENT.csv'), index=False)

print("Done! Simplified files are in 'data_simplified/'.")
