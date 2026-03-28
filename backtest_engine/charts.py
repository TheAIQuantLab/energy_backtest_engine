import plotly.graph_objects as go
import pandas as pd
import numpy as np
from plotly.subplots import make_subplots

def render_market_chart(df, df_trades, current_clock, target_hour):
    fig = go.Figure()
    
    if df.empty:
        return fig
        
    contract_start = df['tradingtime'].min()
    delivery_time = df['deliverytime'].dropna().iloc[-1] if not df['deliverytime'].dropna().empty else df['tradingtime'].max()
    contract_end = max(df['tradingtime'].max(), delivery_time)
    
    df_live = df[df['tradingtime'] <= current_clock].copy()
    df_mic_plot = df_live[df_live['close'].notna()]
    
    fig.add_trace(go.Candlestick(
        x=df_mic_plot['tradingtime'],
        open=df_mic_plot['open'], high=df_mic_plot['high'], low=df_mic_plot['low'], close=df_mic_plot['close'],
        name='MIC',
        increasing_line_color='#00ffcc', decreasing_line_color='#ff3333'
    ))
    
    # Auctions as thin horizontal segments terminating at Delivery Maturity
    colors = {'SPOT': '#ff9900', 'IDA1': '#33ccff', 'IDA2': '#cc66ff', 'IDA3': '#ff3399'}
    for m in ['SPOT', 'IDA1', 'IDA2', 'IDA3']:
        col = f"{m}_price"
        if col in df_live.columns:
            df_m = df_live.dropna(subset=[col])
            if not df_m.empty:
                val = df_m[col].iloc[-1]
                
                # Securely anchor the line start exactly at the publication boundary
                mkt_publishes = df_live[col].notna() & df_live[col].shift(1).isna()
                if mkt_publishes.any():
                    start_x = df_live.loc[mkt_publishes, 'tradingtime'].min()
                else:
                    start_x = df_m['tradingtime'].min()
                    
                # Line finishes precisely at delivery hour, or current clock if it hasn't reached it yet
                end_x = min(current_clock, delivery_time)
                
                fig.add_trace(go.Scatter(
                    x=[start_x, end_x], y=[val, val], 
                    mode='lines', line=dict(width=1.5, color=colors[m]), name=m
                ))
                
    if not df_trades.empty:
        df_trades_live = df_trades[df_trades['tradingtime'] <= current_clock]
        entries = df_trades_live[df_trades_live['action'].str.contains('ENTRY')]
        exits = df_trades_live[df_trades_live['action'] == 'EXIT']
        
        for _, row in entries.iterrows():
            color = 'lime' if 'LONG' in row['action'] else 'magenta'
            symbol = 'triangle-up' if 'LONG' in row['action'] else 'triangle-down'
            fig.add_trace(go.Scatter(
                x=[row['tradingtime']], y=[row['price']],
                mode='markers', marker=dict(color=color, size=14, symbol=symbol, line=dict(width=1, color='white')), 
                name=row['action']
            ))
            
        for _, row in exits.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['tradingtime']], y=[row['price']],
                mode='markers', marker=dict(color='yellow', size=11, symbol='x', line=dict(width=2, color='white')), 
                name=f"EXIT ({row['reason']})"
            ))

    fig.add_vline(x=current_clock.timestamp() * 1000, 
                  line_width=1, line_dash="dot", line_color="rgba(255, 255, 255, 0.4)", 
                  annotation_text=" NOW", annotation_position="top left")
                  
    fig.add_vline(x=delivery_time.timestamp() * 1000, 
                  line_width=2, line_dash="dash", line_color="white", 
                  annotation_text=" Maturity", annotation_position="top right")

    fig.update_layout(
        title=f"Contract Evolution: {delivery_time.strftime('%Y-%m-%d')} Hour {target_hour}:00",
        xaxis_title="", yaxis_title="Price (€/MWh)",
        xaxis=dict(range=[contract_start, contract_end + pd.Timedelta(hours=2)], showgrid=True, gridcolor='#222222'),
        yaxis=dict(showgrid=True, gridcolor='#333333'),
        template="plotly_dark", height=450, margin=dict(l=20, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        plot_bgcolor='#111111', paper_bgcolor='#111111'
    )
    return fig

def render_tearsheet_charts(df_trades):
    if df_trades.empty:
        return None
        
    df_exits = df_trades[df_trades['action'] == 'EXIT'].copy()
    if df_exits.empty:
        return None
        
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1, subplot_titles=("Equity Curve", "Underwater (Drawdown)"))
    
    fig.add_trace(go.Scatter(
        x=df_exits['tradingtime'], y=df_exits['cum_pnl'],
        mode='lines', line=dict(color='#00ffcc', width=2, shape='hv'), name="Cumulative P&L",
        fill='tozeroy'
    ), row=1, col=1)
    
    df_exits['peak'] = df_exits['cum_pnl'].cummax()
    df_exits['drawdown'] = df_exits['cum_pnl'] - df_exits['peak']
    
    fig.add_trace(go.Scatter(
        x=df_exits['tradingtime'], y=df_exits['drawdown'],
        mode='lines', line=dict(color='#ff3333', width=2, shape='hv'), name="Drawdown",
        fill='tozeroy'
    ), row=2, col=1)
    
    fig.update_layout(height=450, template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20),
                      plot_bgcolor='#111111', paper_bgcolor='#111111')
    return fig

def render_pnl_chart(df_trades, current_clock, contract_start, contract_end):
    fig = go.Figure()
    if not df_trades.empty:
        df_exits = df_trades[df_trades['action'] == 'EXIT'].copy()
        if not df_exits.empty:
            df_plot = df_exits[df_exits['tradingtime'] <= current_clock].copy()
            start_pad = pd.DataFrame([{'tradingtime': contract_start, 'cum_pnl': 0.0}])
            df_plot = pd.concat([start_pad, df_plot], ignore_index=True)
            
            fig.add_trace(go.Scatter(
                x=df_plot['tradingtime'], y=df_plot['cum_pnl'],
                mode='lines', line=dict(color='#00ffcc', width=3, shape='hv'), name="Cumulative P&L",
                fill='tozeroy'
            ))

    fig.update_layout(
        title="", xaxis_title="Timeline", yaxis_title="Net Contract P&L (€)",
        xaxis=dict(range=[contract_start, contract_end + pd.Timedelta(hours=2)], showgrid=True, gridcolor='#222222'),
        yaxis=dict(showgrid=True, gridcolor='#333333'),
        template="plotly_dark", height=250, margin=dict(l=20, r=20, t=20, b=20),
        plot_bgcolor='#111111', paper_bgcolor='#111111'
    )
    return fig

def render_feature_scatter(df_trades, df_feat, feature_col):
    if df_trades.empty or df_feat.empty or feature_col not in df_feat.columns:
        return None
        
    df_entries = df_trades[df_trades['action'].str.contains('ENTRY')].copy()
    df_exits = df_trades[df_trades['action'] == 'EXIT'].copy()
    
    if df_entries.empty or len(df_entries) != len(df_exits):
        return None
        
    # Map feature values exactly at entry time
    feat_map = dict(zip(df_feat['tradingtime'], df_feat[feature_col]))
    x_vals = df_entries['tradingtime'].map(feat_map)
    y_vals = df_exits['pnl_realized'].values
    
    x_arr = np.array(x_vals.values, dtype=float)
    y_arr = np.array(y_vals, dtype=float)
    
    # Safe numerical exclusion
    valid_mask = ~np.isnan(x_arr) & ~np.isnan(y_arr) & np.isfinite(x_arr) & np.isfinite(y_arr)
    x_valid = x_arr[valid_mask]
    y_valid = y_arr[valid_mask]
    
    if len(x_valid) < 2:
        return go.Figure().update_layout(title="Not enough data points for Scatter", template="plotly_dark")
        
    # Standard Pearson r
    if np.std(x_valid) == 0 or np.std(y_valid) == 0:
        r_squared = 0.0
    else:
        corr = np.corrcoef(x_valid, y_valid)[0, 1]
        r_squared = corr**2 if not np.isnan(corr) else 0.0
    
    fig = go.Figure(go.Scatter(
        x=x_valid, y=y_valid,
        mode='markers', marker=dict(size=8, color=y_valid, colorscale='RdYlGn', showscale=True),
        name="Trades"
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
    
    fig.update_layout(
        title=f"Feature '{feature_col}' vs. Entry Profitability (R²: {r_squared:.2f})",
        xaxis_title=feature_col, yaxis_title="Realized P&L (€)",
        template="plotly_dark", height=400, margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='#111111', paper_bgcolor='#111111'
    )
    return fig

def render_return_distribution(df_trades):
    if df_trades.empty:
        return None
        
    df_exits = df_trades[df_trades['action'] == 'EXIT']
    if df_exits.empty:
        return None
        
    fig = go.Figure(go.Histogram(
        x=df_exits['pnl_realized'],
        nbinsx=40,
        marker_color='#33ccff',
        opacity=0.75
    ))
    
    fig.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.8)
    
    fig.update_layout(
        title="Trade Return Distribution",
        xaxis_title="Net Realized P&L (€)", yaxis_title="Frequency",
        template="plotly_dark", height=400, margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='#111111', paper_bgcolor='#111111'
    )
    return fig
def render_feature_histogram(df_feat, feature_col):
    if df_feat.empty or feature_col not in df_feat.columns:
        return go.Figure().update_layout(title="Invalid Data for Histogram", template="plotly_dark")
        
    fig = go.Figure(go.Histogram(
        x=df_feat[feature_col].dropna(),
        nbinsx=50,
        marker_color='#ff9900',
        opacity=0.75
    ))
    
    fig.update_layout(
        title=f"Overall Distribution: {feature_col}",
        xaxis_title=feature_col, yaxis_title="Frequency",
        template="plotly_dark", height=400, margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='#111111', paper_bgcolor='#111111'
    )
    return fig
