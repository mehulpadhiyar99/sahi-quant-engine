from flask import Flask, request, render_template_string, Response
import numpy as np
import pandas as pd
import os

app = Flask(__name__)

# Global variable to store last generated trades for CSV export
last_df = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sahi Institutional Quant Terminal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            background-color: #0b0e14;
            color: #e0e0e0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 12px;
        }
        .card {
            background: #131722;
            border: 1px solid #2a2e39;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        h2 { color: #29b6f6; font-size: 18px; margin-top: 0; }
        label { font-size: 11px; color: #848e9c; display: block; margin-bottom: 4px; margin-top: 8px; }
        input, select {
            width: 100%;
            background: #1e222d;
            border: 1px solid #2a2e39;
            color: #fff;
            padding: 10px;
            border-radius: 8px;
            font-size: 14px;
            box-sizing: border-box;
        }
        .row { display: flex; gap: 10px; }
        .col { flex: 1; }
        .btn-blue {
            background: #2962FF;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 8px;
            font-weight: bold;
            width: 100%;
            margin-top: 15px;
            font-size: 14px;
            cursor: pointer;
        }
        .btn-green {
            background: #00E676;
            color: #0b0e14;
            border: none;
            padding: 10px;
            border-radius: 8px;
            font-weight: bold;
            width: 100%;
            margin-top: 10px;
            font-size: 13px;
            text-decoration: none;
            display: block;
            text-align: center;
        }
        .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }
        .metric-box { background: #1e222d; padding: 10px; border-radius: 8px; text-align: center; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; text-align: left; }
        th { background: #1e222d; color: #848e9c; padding: 8px; }
        td { padding: 8px; border-bottom: 1px solid #222; }
    </style>
</head>
<body>
    <div class="card">
        <h2>⚡ Sahi Quant Terminal</h2>
        <form method="POST">
            <label>Select Index (Institutional Filter)</label>
            <select name="index_name">
                <option value="NIFTY 50" {% if index_name == "NIFTY 50" %}selected{% endif %}>NIFTY 50 (Lot: 65)</option>
                <option value="BANKNIFTY" {% if index_name == "BANKNIFTY" %}selected{% endif %}>BANKNIFTY (Lot: 30)</option>
                <option value="FINNIFTY" {% if index_name == "FINNIFTY" %}selected{% endif %}>FINNIFTY (Lot: 40)</option>
                <option value="SENSEX" {% if index_name == "SENSEX" %}selected{% endif %}>SENSEX (Lot: 20)</option>
            </select>

            <div class="row">
                <div class="col">
                    <label>Total Capital (₹)</label>
                    <input type="number" name="capital" value="{{ capital }}">
                </div>
                <div class="col">
                    <label>Risk Per Trade (%)</label>
                    <input type="number" step="0.1" name="risk" value="{{ risk }}">
                </div>
            </div>

            <div class="row">
                <div class="col">
                    <label>Option Stoploss (%)</label>
                    <input type="number" name="sl" value="{{ sl }}">
                </div>
                <div class="col">
                    <label>Option Target (%)</label>
                    <input type="number" name="tp" value="{{ tp }}">
                </div>
            </div>

            <button type="submit" class="btn-blue">📊 Run Quant Backtest</button>
        </form>
    </div>

    <div class="card">
        <div style="font-size: 11px; color: #848e9c;">PERFORMANCE METRICS ({{ index_name }})</div>
        <div style="font-size: 22px; font-weight: bold; color: {{ net_color }}; margin-top: 4px;">
            ₹{{ final_capital_str }} <span style="font-size:12px; color:#848e9c;">(P&L: ₹{{ total_pnl_str }})</span>
        </div>
        
        <div class="metric-grid">
            <div class="metric-box">
                <div style="font-size: 10px; color: #848e9c;">Win Rate</div>
                <div style="font-size: 13px; font-weight: bold; color: #fff; margin-top: 2px;">{{ win_rate_str }}% ({{ win_trades }}/{{ total_trades }})</div>
            </div>
            <div class="metric-box">
                <div style="font-size: 10px; color: #848e9c;">Sharpe Ratio</div>
                <div style="font-size: 13px; font-weight: bold; color: #29b6f6; margin-top: 2px;">{{ sharpe_ratio }}</div>
            </div>
            <div class="metric-box">
                <div style="font-size: 10px; color: #848e9c;">Max Drawdown</div>
                <div style="font-size: 13px; font-weight: bold; color: #FF5252; margin-top: 2px;">₹{{ max_dd }} ({{ max_dd_pct }}%)</div>
            </div>
            <div class="metric-box">
                <div style="font-size: 10px; color: #848e9c;">Profit Factor / Expectancy</div>
                <div style="font-size: 12px; font-weight: bold; color: #00E676; margin-top: 2px;">PF: {{ profit_factor }} | Exp: ₹{{ expectancy }}</div>
            </div>
        </div>

        <a href="/export-csv" class="btn-green">📥 Export Trades History (CSV)</a>
    </div>

    <div class="card">
        <div style="font-size: 12px; font-weight: bold; color: #fff; margin-bottom: 5px;">📜 Quant Simulated Trades (2021-2026)</div>
        <div style="overflow-x: auto;">
            <table>
                <tr>
                    <th>Date</th>
                    <th>Strike</th>
                    <th>Lots</th>
                    <th>Entry/Exit</th>
                    <th>P&L (₹)</th>
                </tr>
                {{ trades_html | safe }}
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    global last_df
    capital = 50000.0
    risk = 2.0
    sl = 12
    tp = 36
    index_name = "NIFTY 50"
    base_lot = 65
    
    lot_sizes_map = {
        "NIFTY 50": 65,
        "BANKNIFTY": 30,
        "FINNIFTY": 40,
        "SENSEX": 20
    }
    
    if request.method == 'POST':
        try:
            cap_val = request.form.get('capital', '')
            if cap_val.strip(): capital = float(cap_val)
            
            risk_val = request.form.get('risk', '')
            if risk_val.strip(): risk = float(risk_val)
            
            sl_val = request.form.get('sl', '')
            if sl_val.strip(): sl = int(float(sl_val))
            
            tp_val = request.form.get('tp', '')
            if tp_val.strip(): tp = int(float(tp_val))
            
            selected_idx = request.form.get('index_name', "NIFTY 50")
            if selected_idx in lot_sizes_map:
                index_name = selected_idx
                base_lot = lot_sizes_map[selected_idx]
        except Exception as e:
            print("Form parse error:", e)

    # --- INSTITUTIONAL ENGINE & QUANT METRICS SIMULATION ---
    np.random.seed(2026)
    total_days = 1500
    dates_full = pd.date_range(start='2021-01-01', end='2026-11-13', periods=total_days)
    
    price_base = 18000 if "NIFTY" in index_name else (42000 if "BANK" in index_name else 65000)
    returns = np.random.normal(0.0004, 0.012, total_days)
    price_series = price_base * np.cumprod(1 + returns)
    
    df_sim = pd.DataFrame({'date': dates_full, 'price': price_series})
    df_sim['ma_fast'] = df_sim['price'].rolling(window=10).mean()
    df_sim['ma_slow'] = df_sim['price'].rolling(window=30).mean()
    df_sim['volatility'] = df_sim['price'].rolling(window=10).std()
    vol_threshold = df_sim['volatility'].quantile(0.60)
    
    df_sim['signal'] = np.where((df_sim['ma_fast'] > df_sim['ma_slow']) & (df_sim['volatility'] > vol_threshold), 1, 0)
    signal_indices = df_sim[(df_sim['signal'] == 1) & (df_sim['price'].diff() > 0)].index
    
    if len(signal_indices) > 40:
        chosen_indices = np.random.choice(signal_indices, size=40, replace=False)
        chosen_indices.sort()
    else:
        chosen_indices = signal_indices

    trade_dates = df_sim.loc[chosen_indices, 'date'].dt.strftime('%d %b %Y').values
    num_trades = len(trade_dates)
    
    if num_trades == 0:
        trade_dates = ['15 Jan 2021', '18 Mar 2021', '12 Jun 2021']
        num_trades = 3

    strikes = np.random.choice(['21500 CE', '22500 CE', '23500 CE', '24500 CE', '22000 PE', '23000 PE'], size=num_trades)
    entry_prices = np.random.uniform(75, 135, size=num_trades).round(2)
    
    sl_prices = (entry_prices * (1 - sl / 100.0)).round(2)
    tp_prices = (entry_prices * (1 + tp / 100.0)).round(2)
    
    outcome_bias = np.random.choice([1, 1, 1, -1], size=num_trades)
    raw_exits = entry_prices + (outcome_bias * np.random.uniform(10, 55, size=num_trades))
    
    exit_prices = []
    trade_status = []
    for entry, s_p, t_p, ext in zip(entry_prices, sl_prices, tp_prices, raw_exits):
        if ext <= s_p:
            exit_prices.append(s_p)
            trade_status.append('SL Hit')
        elif ext >= t_p:
            exit_prices.append(t_p)
            trade_status.append('Target Hit')
        else:
            exit_prices.append(round(ext, 2))
            trade_status.append('Momentum Exit')
            
    df = pd.DataFrame({
        'date': trade_dates,
        'strike': strikes,
        'entry': entry_prices,
        'exit': exit_prices,
        'status': trade_status
    })
    
    # Dynamic Position Sizing
    allowed_risk_rupees = capital * (risk / 100.0)
    risk_per_lot = df['entry'] * (sl / 100.0) * base_lot
    df['lots'] = np.maximum(1, np.floor(allowed_risk_rupees / risk_per_lot)).astype(int)
    
    df['pnl'] = ((df['exit'] - df['entry']) * base_lot * df['lots']).round(2)
    last_df = df.copy()  # Save for CSV export
    
    # --- QUANTITATIVE PERFORMANCE METRICS ---
    total_pnl = df['pnl'].sum()
    final_capital = capital + total_pnl
    win_trades_df = df[df['pnl'] > 0]
    loss_trades_df = df[df['pnl'] < 0]
    
    win_trades = len(win_trades_df)
    total_trades = len(df)
    win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
    
    # Profit Factor
    gross_profit = win_trades_df['pnl'].sum()
    gross_loss = abs(loss_trades_df['pnl'].sum())
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99.0
    
    # Max Drawdown
    cum_pnl = df['pnl'].cumsum()
    peak = cum_pnl.cummax()
    drawdown = cum_pnl - peak
    max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
    max_dd_pct = round((max_dd / capital) * 100, 2)
    
    # Sharpe Ratio (Annualized approximation)
    trade_returns = df['pnl'] / capital
    sharpe_ratio = round((trade_returns.mean() / (trade_returns.std() + 1e-6)) * np.sqrt(252), 2)
    
    # Expectancy
    win_prob = win_rate / 100
    loss_prob = 1 - win_prob
    avg_win = gross_profit / win_trades if win_trades > 0 else 0
    avg_loss = gross_loss / len(loss_trades_df) if len(loss_trades_df) > 0 else 0
    expectancy = round((win_prob * avg_win) - (loss_prob * avg_loss), 2)

    net_color = '#00E676' if total_pnl > 0 else '#FF5252'
    final_capital_str = f"{final_capital:,.2f}"
    total_pnl_str = f"{total_pnl:+,.2f}"
    win_rate_str = f"{win_rate:.0f}"
    max_dd_str = f"{max_dd:,.2f}"
    
    trades_html = ""
    for idx, row in df.iterrows():
        is_profit = row['pnl'] > 0
        color = '#00E676' if is_profit else '#FF5252'
        bg_row = 'rgba(0, 230, 118, 0.05)' if is_profit else 'rgba(255, 82, 82, 0.05)'
        trades_html += f"""
        <tr style="background: {bg_row};">
            <td style="color: #848e9c; font-size: 11px; white-space: nowrap;">{row['date']}</td>
            <td style="font-weight: bold; color: #fff;">{row['strike']}</td>
            <td style="color: #29b6f6; font-weight: bold;">{row['lots']} Lot</td>
            <td style="color: #b0bec5;">₹{row['entry']:.2f} → ₹{row['exit']:.2f}<br><span style="font-size:9px; color:#aaa;">({row['status']})</span></td>
            <td style="color: {color}; font-weight: bold;">₹{row['pnl']:.2f}</td>
        </tr>
        """

    return render_template_string(
        HTML_TEMPLATE,
        capital=capital,
        risk=risk,
        sl=sl,
        tp=tp,
        index_name=index_name,
        final_capital_str=final_capital_str,
        total_pnl_str=total_pnl_str,
        win_rate_str=win_rate_str,
        win_trades=win_trades,
        total_trades=total_trades,
        net_color=net_color,
        sharpe_ratio=sharpe_ratio,
        max_dd=max_dd_str,
        max_dd_pct=max_dd_pct,
        profit_factor=profit_factor,
        expectancy=expectancy,
        trades_html=trades_html
    )

@app.route('/export-csv')
def export_csv():
    global last_df
    if last_df is not None:
        csv_data = last_df.to_csv(index=False)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=sahi_quant_trades_history.csv"}
        )
    return "No backtest data available. Run backtest first!", 400

if __name__ == '__main__':
    # Cloud-Ready Port configuration for Render / PythonAnywhere
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
    