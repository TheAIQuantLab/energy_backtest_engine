import pandas as pd
import numpy as np

def run_backtest(df, entry_signal_mask, exit_signal_mask=None, entry_market='MIC', exit_market='SETTLEMENT', direction=1, tp_amt=0.0, sl_amt=0.0, slippage=0.0, commission=0.0):
    """
    Vectorized Quantitative Backtesting Engine.
    Evaluates Phase 1: Entries, Phase 2: Exit Matrices, Phase 3: Resolution, Phase 4: Ledgers.
    """
    try:
        df = df.copy()
        
        if exit_signal_mask is None:
            exit_signal_mask = pd.Series(False, index=df.index)
            
        df['delivery_date'] = df['deliverytime'].dt.date
        df['raw_signal'] = entry_signal_mask
        
        # ==========================================
        # PHASE 1: ENTRY RESOLUTION
        # ==========================================
        df['execute_entry'] = False
        entry_multiplier = 1 if direction == 1 else -1
        
        if entry_market == 'MIC':
            first_signals = df[df['raw_signal']].groupby('delivery_date').head(1)
            execution_indices = first_signals.index + 1
            valid_exec = execution_indices[execution_indices < len(df)]
            # Ensure the delivery_date of the new index matches the delivery_date of the signal
            valid_exec = valid_exec[df.loc[valid_exec, 'delivery_date'].values == first_signals['delivery_date'].values[:len(valid_exec)]]
            df.loc[valid_exec, 'execute_entry'] = True
            
            df['entry_price'] = np.where(df['execute_entry'], df['open'] + (slippage * entry_multiplier), np.nan)
        
        else: # Auction (SPOT, IDA1, IDA2, IDA3)
            price_col = f"{entry_market}_price"
            if price_col not in df.columns:
                return pd.DataFrame(), {}
            
            # The valid entry row is exactly when the auction price first becomes available
            # Fix: .notna() & shift(1).isna() breaks across days due to the forward fill architecture
            # Instead, explicitly filter to the mathematically first valid moment per delivery date
            valid_price_mask = df[price_col].notna()
            first_pub_idx = df[valid_price_mask].groupby('delivery_date').head(1).index
            
            auction_publishes = pd.Series(False, index=df.index)
            auction_publishes.loc[first_pub_idx] = True
            
            # PROVIDED that raw_signal was True at any point in the 4 hours prior (16 bars of 15m)
            # Use rolling sum of boolean values to detect if there was at least 1 signal True
            # Fix: Group by delivery_date to prevent yesterday's signals from leaking into today
            signal_recently = df.groupby('delivery_date')['raw_signal'].transform(
                lambda x: x.rolling(window=16, min_periods=1).max()
            ) == 1
            
            valid_entries = auction_publishes & signal_recently
            first_signals = df[valid_entries].groupby('delivery_date').head(1)
            
            df.loc[first_signals.index, 'execute_entry'] = True
            
            # Use NumPy arrays safely aligned to filter masks to prevent broadcast logic bugs
            valid_idx = first_signals.index
            prices_arr = df.loc[valid_idx, price_col].values
            df.loc[valid_idx, 'entry_price'] = prices_arr + (slippage * entry_multiplier)
        
        # Propagate the Entry Price forward for the episode cleanly
        df['entry_price'] = df.groupby('delivery_date')['entry_price'].ffill()
        df['in_trade'] = df['entry_price'].notna()
        
        # ==========================================
        # PHASE 2: EXIT TRIGGER MATRICES
        # ==========================================
        # We only care about exit events on rows strictly after the entry row is triggered.
        df['active_holding'] = df['in_trade'] & (~df['execute_entry'])
        
        mask_custom = pd.Series(False, index=df.index)
        mask_sl_gap = pd.Series(False, index=df.index)
        mask_sl_intra = pd.Series(False, index=df.index)
        mask_tp = pd.Series(False, index=df.index)
        mask_auction = pd.Series(False, index=df.index)
        mask_settlement = pd.Series(False, index=df.index)
        
        price_custom = np.full(len(df), np.nan)
        price_sl_gap = np.full(len(df), np.nan)
        price_sl_intra = np.full(len(df), np.nan)
        price_tp = np.full(len(df), np.nan)
        price_auction = np.full(len(df), np.nan)
        price_settlement = np.full(len(df), np.nan)
        
        # --- A. Custom Exit Signal ---
        mask_custom = df['active_holding'] & exit_signal_mask.shift(1).fillna(False).astype(bool)
        if direction == 1:
            price_custom = np.where(mask_custom, df['open'] - slippage, np.nan)
        else:
            price_custom = np.where(mask_custom, df['open'] + slippage, np.nan)
            
        # --- B. TP / SL Intra-Bar Checking (MIC Continuous Tracking) ---
        if direction == 1: # LONG
            tp_target = df['entry_price'] + tp_amt if tp_amt > 0 else np.inf
            sl_target = df['entry_price'] - sl_amt if sl_amt > 0 else -np.inf
            
            mask_sl_gap = df['active_holding'] & (df['open'] <= sl_target)
            price_sl_gap = np.where(mask_sl_gap, df['open'] - slippage, np.nan)
            
            mask_sl_intra = df['active_holding'] & (~mask_sl_gap) & (df['low'] <= sl_target)
            price_sl_intra = np.where(mask_sl_intra, sl_target - slippage, np.nan)
            
            mask_tp = df['active_holding'] & (~mask_sl_gap) & (~mask_sl_intra) & (df['high'] >= tp_target)
            price_tp = np.where(mask_tp, tp_target - slippage, np.nan)
            
        else: # SHORT
            tp_target = df['entry_price'] - tp_amt if tp_amt > 0 else -np.inf
            sl_target = df['entry_price'] + sl_amt if sl_amt > 0 else np.inf
            
            mask_sl_gap = df['active_holding'] & (df['open'] >= sl_target)
            price_sl_gap = np.where(mask_sl_gap, df['open'] + slippage, np.nan)
            
            mask_sl_intra = df['active_holding'] & (~mask_sl_gap) & (df['high'] >= sl_target)
            price_sl_intra = np.where(mask_sl_intra, sl_target + slippage, np.nan)
            
            mask_tp = df['active_holding'] & (~mask_sl_gap) & (~mask_sl_intra) & (df['low'] <= tp_target)
            price_tp = np.where(mask_tp, tp_target + slippage, np.nan)

        # --- C. Designated Target Market Exit (Auction Routing) ---
        if exit_market in ['SPOT', 'IDA1', 'IDA2', 'IDA3']:
            exit_col = f"{exit_market}_price"
            if exit_col in df.columns:
                valid_price_mask_exit = df[exit_col].notna()
                first_pub_idx_exit = df[valid_price_mask_exit].groupby('delivery_date').head(1).index
                
                mask_mkt_publishes = pd.Series(False, index=df.index)
                mask_mkt_publishes.loc[first_pub_idx_exit] = True
                
                mask_auction = df['active_holding'] & mask_mkt_publishes
                if direction == 1:
                    price_auction = np.where(mask_auction, df[exit_col] - slippage, np.nan)
                else:
                    price_auction = np.where(mask_auction, df[exit_col] + slippage, np.nan)

        # --- D. Terminal Settlement Force Close ---
        is_terminal = df.groupby('delivery_date').cumcount(ascending=False) == 0
        mask_settlement = df['active_holding'] & is_terminal
        
        if direction == 1:
            price_settlement = np.where(mask_settlement, df['SETTLEMENT_DOWN'] - slippage, np.nan)
        else:
            price_settlement = np.where(mask_settlement, df['SETTLEMENT_UP'] + slippage, np.nan)
            
        # ==========================================
        # PHASE 3: EXIT RESOLUTION (FIRST TO HIT)
        # ==========================================
        df['any_exit'] = mask_sl_gap | mask_sl_intra | mask_tp | mask_custom | mask_auction | mask_settlement
        
        # We need the chronologically *first* exit row for each trade
        df_exits_all = df[df['any_exit']]
        first_exits = df_exits_all.groupby('delivery_date').head(1).copy()
        
        # Now use np.select locally on this first_exits dataframe to resolve exactly which reason hit
        conds = [
            mask_sl_gap.loc[first_exits.index].values,
            mask_sl_intra.loc[first_exits.index].values,
            mask_tp.loc[first_exits.index].values,
            mask_custom.loc[first_exits.index].values,
            mask_auction.loc[first_exits.index].values,
            mask_settlement.loc[first_exits.index].values
        ]
        
        # Ensure prices arrays map properly without Series index interference
        def extract_prices(price_arr):
            return pd.Series(price_arr, index=df.index).loc[first_exits.index].values
            
        prices = [
            extract_prices(price_sl_gap),
            extract_prices(price_sl_intra),
            extract_prices(price_tp),
            extract_prices(price_custom),
            extract_prices(price_auction),
            extract_prices(price_settlement)
        ]
        
        reasons = ['SL_GAP', 'SL_INTRA', 'TP', 'CUSTOM_SIGNAL', f'EXIT_{exit_market}', 'SETTLED']
        
        first_exits['exit_price'] = np.select(conds, prices, default=np.nan)
        first_exits['exit_reason'] = np.select(conds, reasons, default='UNKNOWN')
        
        # ==========================================
        # PHASE 4: LEDGER & METRICS
        # ==========================================
        valid_entries = df[df['execute_entry']].set_index('delivery_date')
        valid_exits = first_exits.set_index('delivery_date')
        
        daily_keys = valid_entries.index.intersection(valid_exits.index)
        
        trades = []
        cum_pnl = 0.0
        
        for d in daily_keys:
            en = valid_entries.loc[d]
            ex = valid_exits.loc[d]
            
            if pd.isna(en['entry_price']) or pd.isna(ex['exit_price']):
                continue
                
            entry_p = float(en['entry_price'])
            exit_p = float(ex['exit_price'])
            
            raw_pnl = (exit_p - entry_p) if direction == 1 else (entry_p - exit_p)
            net_pnl = raw_pnl - commission
            cum_pnl += net_pnl
            
            trades.append({
                'tradingtime': en['tradingtime'],
                'action': 'ENTRY LONG' if direction == 1 else 'ENTRY SHORT',
                'delivery_target': en['deliverytime'],
                'price': entry_p,
                'pnl_realized': 0.0,
                'cum_pnl': cum_pnl - net_pnl,
                'reason': f"SIGNAL ({entry_market})"
            })
            
            trades.append({
                'tradingtime': ex['tradingtime'],
                'action': 'EXIT',
                'delivery_target': ex['deliverytime'],
                'price': exit_p,
                'pnl_realized': net_pnl,
                'cum_pnl': cum_pnl,
                'reason': ex['exit_reason']
            })
            
        df_trades = pd.DataFrame(trades)
        
        stats = {
            'total_trades': 0, 'total_pnl': 0.0, 'win_rate': 0.0, 
            'max_dd': 0.0, 'sharpe': 0.0, 'profit_factor': 0.0,
            'avg_win': 0.0, 'avg_loss': 0.0, 'expectancy': 0.0
        }
        
        if not df_trades.empty:
            df_exits_only = df_trades[df_trades['action'] == 'EXIT'].copy()
            trades_count = len(df_exits_only)
            stats['total_trades'] = trades_count
            stats['total_pnl'] = df_exits_only['pnl_realized'].sum()
            
            wins = df_exits_only[df_exits_only['pnl_realized'] > 0]
            losses = df_exits_only[df_exits_only['pnl_realized'] <= 0]
            
            win_rate = len(wins) / trades_count if trades_count > 0 else 0
            stats['win_rate'] = win_rate * 100
            
            gross_win = wins['pnl_realized'].sum()
            gross_loss = abs(losses['pnl_realized'].sum())
            
            stats['profit_factor'] = (gross_win / gross_loss) if gross_loss > 0 else float('nan')
            stats['avg_win'] = wins['pnl_realized'].mean() if not wins.empty else 0.0
            stats['avg_loss'] = losses['pnl_realized'].mean() if not losses.empty else 0.0
            
            stats['expectancy'] = (win_rate * stats['avg_win']) - ((1 - win_rate) * abs(stats['avg_loss']))
            
            df_exits_only['peak'] = df_exits_only['cum_pnl'].cummax()
            df_exits_only['drawdown'] = df_exits_only['cum_pnl'] - df_exits_only['peak']
            stats['max_dd'] = df_exits_only['drawdown'].min()
            
            std_pnl = df_exits_only['pnl_realized'].std()
            if std_pnl > 0:
                mean_pnl = df_exits_only['pnl_realized'].mean()
                stats['sharpe'] = (mean_pnl / std_pnl) * np.sqrt(252)
                
        return df_trades, stats
        
    except Exception as e:
        import traceback
        return pd.DataFrame(), {}

