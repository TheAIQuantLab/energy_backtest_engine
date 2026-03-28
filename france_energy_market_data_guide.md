# French Energy Market Data Analysis Guide

This document provides a technical guide to the datasets available for the French energy market, explaining the market mechanisms, timing of price settlements, and delivery resolutions.

## 1. Overview of Markets
The French energy market is divided into several stages of settlement, from day-ahead to real-time balancing.

| Market Stage | Dataset Example | Settlement Timing | Delivery Resolution |
| :--- | :--- | :--- | :--- |
| **Day-Ahead (SPOT)** | `spot_price_FR_2024_2025.csv` | D-1 at 12:00 PM CET | Hourly (60 min) |
| **Intraday Auctions (IDA)** | `intraday_session_FR_2024_2025.csv` | Specific Auction Times | Half-Hourly (30 min) |
| **Intraday Continuous (MIC)** | `mic_trades_FR_2024_2025.csv` | Continuous up to real-time | Product-based (Hourly XB) |
| **Imbalance (Settlement)** | `imbalance_FR_2025.csv` | Ex-post (Real-time deviation) | 15-minute intervals |

---

## 2. Market Details & Data Structure

### A. SPOT Market (Day-Ahead)
The **Day-Ahead Market (DAM)** is the primary auction for electricity delivery for the next day.
- **Timing:** Auctions occur at 12:00 PM (noon) on day D-1.
- **Delivery:** Fixed 24-hour blocks for day D.
- **Resolution:** 60 minutes.
- **Dataset (`spot_price_FR_2024_2025.csv`):**
    - `utcdatetime`: The start of the delivery hour.
    - `price`: Market Clearing Price (MCP) in €/MWh.

### B. Intraday Auctions (IDA1, IDA2, IDA3)
Intraday Auctions allow participants to adjust their day-ahead positions as forecasts improve.
- **IDAs Timings (as of June 2024):**
    - **IDA1:** Gate closure 15:00 D-1 (Delivery: all hours of D).
    - **IDA2:** Gate closure 22:00 D-1 (Delivery: all hours of D).
    - **IDA3:** Gate closure 10:00 D (Delivery: 12:00 to 24:00 of D).
- **Resolution:** 30 minutes.
- **Dataset (`intraday_session_FR_2024_2025.csv`):**
    - `session`: Identifies if the price belongs to IDA1, IDA2, or IDA3.
    - `price`: Resulting auction price for the specific 30-min block.

### C. Merchant Intraday Continuous (MIC / Trades)
Continuous trading allows for bilateral trades and price discovery up to real-time.
- **Timing:** Opens after the Day-Ahead results and runs until lead-time.
    - **Local products:** Typically 5 minutes before delivery.
    - **Cross-border (XB) products:** Gate closure is typically 60 minutes before delivery.
    - **Data Observation:** In the provided `mic_trades_FR_2024_2025.csv`, trade summaries (OHLC) are recorded up to **15 minutes before the LOCAL delivery start** (since the product column is specified in local French time).
- **Dataset (`mic_trades_FR_2024_2025.csv`):**

    - `utcdatetime`: Timestamp when the summary (OHLC) was recorded (every 15 mins).
    - `product`: The delivery window (e.g., `00-01_XB` represents delivery between 00:00 and 01:00).
    - `open, high, low, close`: The price range of trades executed during the lookback period.

### D. Imbalance Price (Settlement)
This is the final balancing price calculated by the TSO (Transmission System Operator) to penalize or reward market participants who deviate from their scheduled positions.
- **Timing:** Imbalance applies directly to the specific delivery interval where the deviation occurred. The final realization (and thus `tradingtime` from a modeling perspective) equals the `deliverytime`, even though the exact price publication time by the TSO may occur later.
- **Dataset (`imbalance_FR_2025.csv`):**
    - `type`: `UP` (System short, price to increase production) or `DOWN` (System long, price to decrease production).
    - `imbalance_price`: The price applied to the volume deviation.
    - `publication_date`: When the price was finalized by RTE.

---

## 3. Key Temporal Relationships
When analyzing this data for trading or forecasting, remember the following sequence:
1.  **D-1 12:00:** SPOT price is fixed.
2.  **D-1 15:00:** IDA1 price is fixed.
3.  **D-1 22:00:** IDA2 price is fixed.
4.  **D 10:00:** IDA3 price is fixed.
5.  **D (Real-time):** MIC prices fluctuate continuously.
6.  **D+1 (Post-event):** Imbalance prices are published.

## 4. Usage for Agentic Workflows
- **Filtering:** For 2025 analysis, use `utcdatetime` and convert to French local time (CET/CEST) to align with market auction rules.
- **Aggregation:** When comparing SPOT (hourly) with Imbalance (15-min), downsample or average prices accordingly.
