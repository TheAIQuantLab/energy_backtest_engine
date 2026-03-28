run: streamlit run backtest_engine/app.py

# Vectorized Energy Market Backtest Engine

A high-performance, vectorized quantitative simulation platform for French power markets (EPEX SPOT, IDA1-3, MIC). This engine resolves complex chronological paradoxes (look-ahead bias) and provides a modular architecture for professional strategy development.

## Key Features

*   **Modular 4-Phase Vectorized Pipeline**: Eliminates nested loops, ensuring ultra-fast simulations across multi-year tick data.
    *   *Phase 1: Entry Resolution* (Market-specific gate closures).
    *   *Phase 2: Exit Trigger Matrices* (Intra-bar SL/TP, Custom signals).
    *   *Phase 3: First-to-Hit Resolution* (Conflict resolution between multiple exit events).
    *   *Phase 4: Ledger & Metric Attribution*.
*   **Universal Dynamic Feature Factory**: Construct complex indicators (RSI of a Spread, EMA of Volatility) on-the-fly via the UI without pre-calculation.
*   **Dual Execution Routing**: Decouple entries and exits across different market venues (e.g., Enter at SPOT auction, Exit at MIC continuous).
*   **Interactive Smooth Market Replay**: Frame-by-frame visualization of market evolution, auction publication windows, and strategy execution.
*   **Independent Feature Exploration**: Statistically correlate any dynamic indicator against realized P&L using histograms and scatter plots ($R^2$/Pearson correlation).

---

## Data Guide & Cleaning

### 1. Raw Data Structure
The engine ingests 6 distinct market categories from the French power market:
*   **SPOT**: Day-Ahead auction prices.
*   **IDA1, IDA2, IDA3**: Intraday Auction gate closures and prices.
*   **MIC**: Continuous market OHLC (15-minute resolution).
*   **SETTLEMENT**: Terminal imbalance prices (`UP` and `DOWN`).

### 2. Pre-processing (`simplify_data.py`)
To ensure high performance, raw CSVs are standardized:
*   **Timestamp Alignment**: All clocks converted to French Local Time (CET/CEST).
*   **Imbalance Mapping**: `UP/DOWN` types correctly preserved for settlement resolution.
*   **Uniform Schema**: Standardized to `tradingtime`, `deliverytime`, and `price`.

### 3. Master DataFrame Construction (`data.py`)
The engine builds a unified 15-minute timeline using MIC as the backbone. It uses `pd.merge_asof` with `direction='backward'` to strictly prevent look-ahead bias—auction prices only become available to the strategy *after* their official publication timestamp.

---

## Technical Architecture

### Vectorized Execution Logic (`strategy.py`)
The engine operates on boolean masks to determine state transitions. 
*   **Gate Closures**: Strategies entering an auction must have a valid signal *before* the auction closes.
*   **Intra-bar SL/TP**: For continuous markets (MIC), the engine checks `High/Low` bounds to simulate millisecond-level fills while gapping risk is accounted for at `Open`.

### Dynamic Indicator Factory (`features.py`)
Instead of hardcoding hundreds of columns, the system materializes features on-demand. Supported primitives include:
*   **SMA, EMA, STD, RSI, ROC**
*   **Cross-market Spreads**
*   **Time Contexts** (Minutes to delivery, Day-of-week, Hour-of-day).

---

## Installation & Usage

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Prepare Data
Ensure your raw CSVs are in the `/data` folder, then run the simplification script:
```bash
python simplify_data.py
```

### 3. Launch the Engine
```bash
cd backtest_visualization
streamlit run app.py
```

---

## Strategy Configuration
1.  **Target Delivery Hour**: Select the specific physical contract hour to backtest (e.g., Hour 12 Peak).
2.  **Execution Routing**: Choose where to enter (e.g., IDA1) and where to route the exit (e.g., Continuous MIC).
3.  **Rule Builder**: Construct "And" conditional rules using the dynamic feature builder.
4.  **Trade Management**: Set Take Profit, Stop Loss (in €), Slippage, and Commissions.

---

## Analytics
The **Quantitative Tearsheet** provides professional-grade metrics:
*   **Sharpe Ratio** (Annualized)
*   **Win Rate & Profit Factor**
*   **Expectancy & Avg Win/Loss Ratio**
*   **Max Drawdown Tracking**

Designed by **Expert Quantitative Developers**.
