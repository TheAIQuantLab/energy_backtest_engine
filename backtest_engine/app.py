import streamlit as st
import pandas as pd
import numpy as np
import time
import data
import features
import strategy
import charts

st.set_page_config(layout="wide", page_title="Energy Quant Engine")
st.title("Energy Market Backtester")

# Session State Initialization
if 'sim_running' not in st.session_state:
    st.session_state.sim_running = False
if 'current_clock' not in st.session_state:
    st.session_state.current_clock = None
if 'df_trades' not in st.session_state:
    st.session_state.df_trades = pd.DataFrame()
if 'df_feat' not in st.session_state:
    st.session_state.df_feat = pd.DataFrame()
if 'stats' not in st.session_state:
    st.session_state.stats = {}
if 'current_contract' not in st.session_state:
    st.session_state.current_contract = None

# Tabbed Layout
tab_backtest, tab_explore, tab_doc = st.tabs(["Backtest Engine", "Feature Exploration", "Documentation"])

with tab_backtest:
    with st.expander("Strategy Configuration", expanded=True):
        st.header("Data Configuration")
        target_hour = st.number_input("Target Delivery Hour (0-23)", 0, 23, 12, help="The specific physical delivery hour evaluated continuously across the year.")
        
        # Load Data
        df_master, min_time, max_time = data.load_and_build_master_df(target_hour)
        df_feat = features.generate_features(df_master)
        # Ensure latest features are available for the always-on replay
        st.session_state.df_feat = df_feat
        
        st.markdown("---")
        
        c_rout, c_mgmt = st.columns(2)
        
        with c_rout:
            st.subheader("Execution Routing")
            direction = st.selectbox("Direction", ["LONG", "SHORT"])
            dir_mult = 1 if direction == "LONG" else -1
            entry_market = st.selectbox("Entry Market", ["MIC", "SPOT", "IDA1", "IDA2", "IDA3"])
            exit_market = st.selectbox("Exit Market", ["SETTLEMENT", "MIC", "IDA1", "IDA2", "IDA3"])
            
        with c_mgmt:
            st.subheader("Trade Management")
            tp_amt = st.number_input("TP (€ dist, 0=off)", min_value=0.0, value=0.0, step=1.0)
            sl_amt = st.number_input("SL (€ dist, 0=off)", min_value=0.0, value=0.0, step=1.0)
            slippage = st.number_input("Slippage (€)", min_value=0.0, value=0.0, step=0.1)
            commission = st.number_input("Commission (€)", min_value=0.0, value=0.0, step=0.1)
            
        st.markdown("---")
            
        def get_allowed_prefixes(market, is_entry=True):
            if is_entry:
                if market == "SPOT": return ["GLOBAL_", "SPOT_"]
                elif market == "IDA1": return ["GLOBAL_", "SPOT_"] 
                elif market == "IDA2": return ["GLOBAL_", "SPOT_", "IDA1_"]
                elif market == "IDA3": return ["GLOBAL_", "SPOT_", "IDA1_", "IDA2_"]
                else: return ["GLOBAL_", "SPOT_", "IDA1_", "IDA2_", "IDA3_", "MIC_"]
            else:
                if market == "SPOT": return ["GLOBAL_", "SPOT_"]
                elif market == "IDA1": return ["GLOBAL_", "SPOT_", "IDA1_"]
                elif market == "IDA2": return ["GLOBAL_", "SPOT_", "IDA1_", "IDA2_"]
                elif market == "IDA3": return ["GLOBAL_", "SPOT_", "IDA1_", "IDA2_", "IDA3_"]
                else: return ["GLOBAL_", "SPOT_", "IDA1_", "IDA2_", "IDA3_", "MIC_"]

        def render_feature_builder(prefix_label, key_suffix, allowed_prefixes):
            st.markdown(f"**{prefix_label} Config**")
            ftype = st.selectbox("Type", ["Raw Price", "Technical Indicator", "Spread", "Time Context"], key=f"ftype_{key_suffix}")
            
            config = {"type": ftype}
            raw_candidates = [c for c in ["SPOT_price", "IDA1_price", "IDA2_price", "IDA3_price", "MIC_close"] if any(c.startswith(p) for p in allowed_prefixes)]
            if not raw_candidates:
                raw_candidates = ["MIC_close"] # Safe fallback
                
            if ftype == "Raw Price":
                config["market_col"] = st.selectbox("Market Data", raw_candidates, key=f"raw_{key_suffix}")
            elif ftype == "Time Context":
                time_cands = ["GLOBAL_minutes_to_delivery", "GLOBAL_hour_of_day", "GLOBAL_day_of_week"]
                config["time_col"] = st.selectbox("Time Metric", time_cands, key=f"time_{key_suffix}")
            elif ftype == "Spread":
                c1, c2 = st.columns(2)
                config["leg_a"] = c1.selectbox("Leg A", raw_candidates, key=f"sp_a_{key_suffix}")
                config["leg_b"] = c2.selectbox("Leg B", raw_candidates, key=f"sp_b_{key_suffix}")
            elif ftype == "Technical Indicator":
                config["source_col"] = st.selectbox("Source Data", raw_candidates, key=f"ti_src_{key_suffix}")
                c1, c2 = st.columns(2)
                config["indicator"] = c1.selectbox("Indicator", ["SMA", "EMA", "STD", "ROC", "RSI"], key=f"ti_ind_{key_suffix}")
                config["period"] = c2.number_input("Period", min_value=1, value=14, key=f"ti_per_{key_suffix}")
                
            return config

        def render_rule_col(col_ctx, prefix, current_df):
            with col_ctx:
                st.subheader(f"{prefix.capitalize()} Rules (AND)")
                num_rules = st.number_input(f"# Rules", 0, 5, 0 if prefix == "exit" else 1, key=f"num_{prefix}")
                
                if num_rules == 0:
                    return pd.Series(False, index=current_df.index) if prefix == "exit" else pd.Series(True, index=current_df.index)
                    
                signal_mask = pd.Series(True, index=current_df.index)
                
                selected_market = entry_market if prefix == "entry" else exit_market
                allowed_prefixes = get_allowed_prefixes(selected_market, is_entry=(prefix=="entry"))
                
                for i in range(num_rules):
                    st.markdown(f"#### Rule {i+1}")
                    
                    with st.container(border=True):
                        # LHS Config
                        lhs_config = render_feature_builder("Left-Hand Side", f"{prefix}_lhs_{i}", allowed_prefixes)
                        
                        st.markdown("---")
                        c_op, c_rh = st.columns([1, 2])
                        op = c_op.selectbox("Operator", [">", "<", ">=", "<=", "=="], key=f"{prefix}_op_{i}")
                        val_type = c_rh.selectbox("Target Type", ["Value", "Feature"], key=f"{prefix}_valtype_{i}")
                        
                        if val_type == "Value":
                            val = st.number_input(f"Target Value", value=0.0, key=f"{prefix}_val_{i}")
                            rhs_config = None
                        else:
                            st.markdown("---")
                            rhs_config = render_feature_builder("Right-Hand Side", f"{prefix}_rhs_{i}", allowed_prefixes)
                            
                        # --- INJECTION STEP ---
                        lhs_col = features.build_dynamic_feature(current_df, lhs_config)
                        
                        if val_type == "Feature":
                            rhs_col = features.build_dynamic_feature(current_df, rhs_config)
                            compare_series = current_df[rhs_col] if rhs_col is not None else 0.0
                        else:
                            compare_series = val
                            
                        if lhs_col and lhs_col in current_df.columns:
                            if op == ">": signal_mask &= (current_df[lhs_col] > compare_series)
                            elif op == "<": signal_mask &= (current_df[lhs_col] < compare_series)
                            elif op == ">=": signal_mask &= (current_df[lhs_col] >= compare_series)
                            elif op == "<=": signal_mask &= (current_df[lhs_col] <= compare_series)
                            elif op == "==": signal_mask &= (current_df[lhs_col] == compare_series)
                    
                return signal_mask

        c_entry, c_exit = st.columns(2)
        entry_mask = render_rule_col(c_entry, "entry", df_feat)
        exit_mask = render_rule_col(c_exit, "exit", df_feat)
        
        st.markdown("---")
        if st.button("Run Quantitative Backtest", type="primary"):
            with st.spinner("Executing Vectorized Engine..."):
                df_trades, stats = strategy.run_backtest(
                    df=df_feat, 
                    entry_signal_mask=entry_mask, exit_signal_mask=exit_mask,
                    entry_market=entry_market, exit_market=exit_market,
                    direction=dir_mult, 
                    tp_amt=tp_amt, sl_amt=sl_amt, slippage=slippage, commission=commission
                )
                st.session_state.df_trades = df_trades
                st.session_state.stats = stats
                st.session_state.sim_running = False

    if not st.session_state.df_trades.empty:
        st.header("Quantitative Results Summary")
        stats = st.session_state.stats
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total P&L", f"€{stats.get('total_pnl', 0):.2f}")
        m2.metric("Total Trades", stats.get('total_trades', 0))
        m3.metric("Win Rate", f"{stats.get('win_rate', 0):.1f}%")
        pf = stats.get('profit_factor', 0)
        m4.metric("Profit Factor", f"{pf:.2f}" if not np.isnan(pf) else "N/A")
        
        m5, m6, m7, m8 = st.columns(4)
        m5.metric("Max Drawdown", f"€{stats.get('max_dd', 0):.2f}")
        m6.metric("Sharpe Ratio", f"{stats.get('sharpe', 0):.2f}")
        m7.metric("Expectancy", f"€{stats.get('expectancy', 0):.2f}")
        m8.metric("Avg Win / Loss", f"€{stats.get('avg_win',0):.1f} / €{stats.get('avg_loss',0):.1f}")
        
        # --- Static Rendering Block ---
        fig_static_pnl = charts.render_tearsheet_charts(st.session_state.df_trades)
        if fig_static_pnl:
            st.plotly_chart(fig_static_pnl)
            
        st.markdown("---")
        st.subheader("Trade Return Distribution")
        fig_dist = charts.render_return_distribution(st.session_state.df_trades)
        if fig_dist:
            st.plotly_chart(fig_dist)
            
        st.subheader("Trade Ledger")
        st.dataframe(st.session_state.df_trades[['tradingtime', 'action', 'delivery_target', 'price', 'pnl_realized', 'cum_pnl', 'reason']])
    else:
        st.info("Configure rules above and click 'Run Quantitative Backtest' to see results.")

    # --- Market Replay Block (Only visible after backtest run) ---
    if not st.session_state.df_trades.empty:
        st.markdown("---")
        st.header("Interactive Smooth Market Replay")
        
        available_dates = sorted(st.session_state.df_feat['deliverytime'].dt.date.dropna().unique())
        
        col_sel, _ = st.columns([1, 3])
        selected_date = col_sel.selectbox("Select Delivery Contract Date to Replay", available_dates)
        
        df_inspect = st.session_state.df_feat[st.session_state.df_feat['deliverytime'].dt.date == selected_date]
        inspect_trades = st.session_state.df_trades[st.session_state.df_trades['delivery_target'].dt.date == selected_date] \
                         if not st.session_state.df_trades.empty else pd.DataFrame()
        
        if st.session_state.current_contract != selected_date or st.session_state.current_clock is None:
            st.session_state.current_contract = selected_date
            st.session_state.current_clock = df_inspect['tradingtime'].min()
            st.session_state.sim_running = False
        
        colp1, colp2 = st.columns(2)
        if colp1.button("Play Contract Evolution"):
            if st.session_state.current_clock >= df_inspect['tradingtime'].max():
                st.session_state.current_clock = df_inspect['tradingtime'].min()
            st.session_state.sim_running = True
            st.rerun()
        if colp2.button("Pause Evolution"):
            st.session_state.sim_running = False
            st.rerun()
            
        speed = st.slider("Animation Framerate (s/tick)", 0.01, 1.0, 0.1, 0.05)
        st.info(f"**Simulation Engine Clock: {st.session_state.current_clock.strftime('%Y-%m-%d %H:%M:%S')}**")
        
        fig_market = charts.render_market_chart(
            df_inspect, inspect_trades, 
            st.session_state.current_clock, target_hour
        )
        st.plotly_chart(fig_market)
        
        contract_start = df_inspect['tradingtime'].min()
        contract_end = df_inspect['tradingtime'].max()
        fig_pnl_live = charts.render_pnl_chart(
            inspect_trades, st.session_state.current_clock, 
            contract_start, contract_end
        )
        st.plotly_chart(fig_pnl_live)
        
        if st.session_state.sim_running:
            if st.session_state.current_clock < df_inspect['tradingtime'].max():
                time.sleep(speed)
                st.session_state.current_clock += pd.Timedelta(minutes=15)
                st.rerun()
            else:
                st.session_state.sim_running = False
                st.success("Contract Expiration Reached!")
                st.rerun()


with tab_explore:
    st.header("Feature Exploration")
    
    st.markdown("### Generate Exploratory Feature")
    # All base features technically have no timeline exclusion constraint when exploring individually
    allowed_explore_prefixes = ["GLOBAL_", "SPOT_", "IDA1_", "IDA2_", "IDA3_", "MIC_"]
    # Re-use the identical rendering block for perfect programmatic parity!
    explore_config = render_feature_builder("Exploratory", "explore", allowed_explore_prefixes)
    
    # Materialize explicitly
    df_feat_explore = df_feat.copy()
    scatter_feat = features.build_dynamic_feature(df_feat_explore, explore_config)
        
    st.markdown("---")
    
    c1_explore, c2_explore = st.columns(2)
    with c1_explore:
        if st.session_state.df_trades.empty:
            st.info("Run a Backtest in the main tab to correlate this feature against Realized P&L in a Scatter Plot.")
        else:
            fig_scatter = charts.render_feature_scatter(st.session_state.df_trades, df_feat_explore, scatter_feat)
            if fig_scatter:
                st.plotly_chart(fig_scatter)
                
    with c2_explore:
        if scatter_feat:
            fig_hist = charts.render_feature_histogram(df_feat_explore, scatter_feat)
            if fig_hist:
                st.plotly_chart(fig_hist)


with tab_doc:
    st.header("Project Documentation")
    
    doc_mode = st.radio("Select Section", ["User Guide", "Technical Architecture", "Data Guide", "Market Mechanisms"], horizontal=True)
    
    if doc_mode == "User Guide":
        st.markdown("""
        ### How to Run a Backtest
        1. **Select Target Hour**: Choose the physical delivery hour (0-23) you wish to trade. The engine will filter a year of 15-minute data for this contract.
        2. **Configure Routing**: 
            - **Entry Market**: Where the trade starts (MIC for continuous, or Auctions for fixed-price publication).
            - **Exit Market**: Where the trade settles if no SL/TP is hit.
        3. **Build Rules**: 
            - Define 'And' conditions using **Raw Prices**, **Technical Indicators**, or **Spreads**.
            - The engine strictly prevents look-ahead bias; indicators only use data available *before* the execution timestamp.
        4. **Trade Management**: Set your distance-based Take Profit and Stop Loss in Euros (€).
        
        ### How to Explore Features
        1. Navigate to the **Feature Exploration** tab.
        2. Build a dynamic indicator (e.g., RSI of a MIC-SPOT spread).
        3. View the **Distribution Histogram** to understand the feature's range.
        4. Correlate the feature against your latest backtest results in the **Scatter Plot** to identify alpha.
        """)
        
    elif doc_mode == "Technical Architecture":
        st.markdown("""
        ### Vectorized 4-Phase Engine
        The `strategy.py` engine eliminates loops for maximum performance:
        - **Phase 1: Entry**: Resolves precisely when an order hits the ledger based on gate closures.
        - **Phase 2: Exit Matrix**: Pre-computes all potential exit events (SL, TP, Custom Signals, Settlement) in parallel.
        - **Phase 3: Resolution**: Identifies the chronologically *first* exit event for each trade.
        - **Phase 4: Metrics**: Attributes slippage, commission, and calculates professional KPIs like Sharpe and Profit Factor.
        
        ### Dynamic Indicator Factory
        Instead of pre-calculating features, `features.py` materializes columns on-the-fly. This allows for:
        - RSI of any Raw Price or Spread.
        - Moving averages of time-series contexts.
        - Zero-collision column naming for complex rule combinations.
        """)
        
    elif doc_mode == "Data Guide":
        st.markdown("""
        ### Market Data Sources
        - **SPOT**: Day-ahead auction prices (fixed at 12:00 D-1).
        - **IDA1/2/3**: Intraday auctions with specific 15:00, 22:00, and 10:00 gate closures.
        - **MIC**: Continuous 15-minute OHLC ticker.
        - **SETTLEMENT**: The real-time imbalance price (UP/DOWN).
        
        ### Synchronization
        The system uses a **Master 15-minute Timeline** based on the MIC backbone. Auction prices are "snapped" to the timeline using `pd.merge_asof(direction='backward')`, ensuring a strategy can never see an auction price before its official publication time.
        """)
        
    elif doc_mode == "Market Mechanisms":
        st.info("The European power market operates on a sequence of gate closures. This engine enforces these rules strictly to ensure backtest integrity.")
        st.markdown("""
        - **Market Coupling**: Standardized price discovery through PCR (Price Coupling of Regions).
        - **Delivery Consistency**: All prices are matched to the specific delivery interval, regardless of when they were traded.
        - **Imbalance Settlement**: The final cost/revenue for deviation from nominated positions.
        """)



