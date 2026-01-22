import pandas as pd
import pandas_ta as ta
import yfinance as yf
import requests
import time
import json
import os
import subprocess
from datetime import datetime

# --- CONFIGURATION ---
SYMBOL_BTC = "BTC-USD"
TELEGRAM_TOKEN = '8357643697:AAHbqsslAuHA5n6vdw-Bl_O9ja-fnxSJlVo'
TELEGRAM_CHAT_ID = '8353781512'

# --- PARAMÈTRES OPTIMISÉS (+29.5%) ---
RSI_MAX_ACHAT = 60        
TARGET_GAIN_PCT = 0.06    
STOP_LOSS_PCT = 0.05      
TRAILING_DYNAMIC = 0.01   
CAPITAL_INITIAL = 100.0   
FICHIER_SIMU = "bourse_virtuelle.json"

# --- INITIALISATION ---
last_github_push = 0
if os.path.exists(FICHIER_SIMU):
    with open(FICHIER_SIMU, 'r') as f:
        try: sim = json.load(f)
        except: sim = {"solde_usdt": CAPITAL_INITIAL, "quantite_btc": 0.0, "reserve_securisee": 0.0, "en_position": False, "prix_achat": 0.0, "highest_after_target": 0.0, "historique": []}
else:
    sim = {"solde_usdt": CAPITAL_INITIAL, "quantite_btc": 0.0, "reserve_securisee": 0.0, "en_position": False, "prix_achat": 0.0, "highest_after_target": 0.0, "historique": []}

def save_sim():
    with open(FICHIER_SIMU, 'w') as f: json.dump(sim, f, indent=4)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={message}"
    try: requests.get(url, timeout=5)
    except: pass

def update_web_dashboard(price, rsi, fgi, dxy_change, vwap, bb_width):
    # Calcul de la valeur actuelle du portefeuille
    valeur_actuelle = sim['solde_usdt'] if not sim['en_position'] else sim['quantite_btc'] * price
    perf = ((valeur_actuelle / CAPITAL_INITIAL) - 1) * 100
    status = "📈 EN POSITION" if sim['en_position'] else "💤 ATTENTE SIGNAL"
    color_status = "#2ecc71" if sim['en_position'] else "#f1c40f"

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="60">
        <title>Bot Elite V2 Dashboard</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #121212; color: white; text-align: center; }}
            .container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; padding: 20px; }}
            .card {{ background: #1e1e1e; padding: 20px; border-radius: 15px; min-width: 200px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); border: 1px solid #333; }}
            .value {{ font-size: 24px; font-weight: bold; color: #3498db; }}
            .label {{ font-size: 14px; color: #888; text-transform: uppercase; margin-top: 5px; }}
            .status {{ font-size: 20px; font-weight: bold; color: {color_status}; margin-top: 20px; }}
            #chart {{ width: 90%; margin: auto; background: #1e1e1e; border-radius: 15px; padding: 10px; }}
        </style>
    </head>
    <body>
        <h1>🚀 BOT ELITE V2 - MONITORING</h1>
        <div class="status">{status}</div>
        
        <div class="container">
            <div class="card"><div class="value">{price:,.0f} $</div><div class="label">Prix BTC</div></div>
            <div class="card"><div class="value" style="color:{'#e74c3c' if rsi > 70 else '#2ecc71'}">{rsi:.1f}</div><div class="label">RSI (14)</div></div>
            <div class="card"><div class="value">{perf:+.2f} %</div><div class="label">Performance</div></div>
            <div class="card"><div class="value">{fgi}</div><div class="label">Fear & Greed</div></div>
            <div class="card"><div class="value">{dxy_change*100:+.2f}%</div><div class="label">Variation DXY</div></div>
            <div class="card"><div class="value">{bb_width:.4f}</div><div class="label">Bollinger Width</div></div>
        </div>

        <div id="chart"></div>
        <script>
            var data = [{{ x: [0, 1], y: [0, 1], type: 'scatter', mode: 'lines', line: {{color: '#3498db'}} }}];
            var layout = {{ title: 'Historique Temps Réel (Simulation)', paper_bgcolor: '#1e1e1e', plot_bgcolor: '#1e1e1e', font: {{color: '#fff'}} }};
            Plotly.newPlot('chart', data, layout);
        </script>
        
        <h3>📜 DERNIERS TRADES</h3>
        <pre style="text-align:left; display:inline-block; background:#000; padding:15px; border-radius:10px;">
{json.dumps(sim['historique'][-5:], indent=2)}
        </pre>
        <p>Dernière mise à jour : {datetime.now().strftime('%H:%M:%S')}</p>
    </body>
    </html>
    """
    with open("index.html", "w") as f: f.write(html)

def publier_sur_github():
    try:
        subprocess.run(["git", "add", "index.html", FICHIER_SIMU], check=True)
        subprocess.run(["git", "commit", "-m", f"Dashboard Update {datetime.now().strftime('%H:%M')}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🌍 Mise à jour GitHub effectuée.")
    except Exception as e:
        print(f"⚠️ Erreur Push GitHub : {e}")

def get_data():
    try:
        btc = yf.download(SYMBOL_BTC, period="5d", interval="1h", progress=False)
        if btc.empty or len(btc) < 30: return None, 0, 50
        if isinstance(btc.columns, pd.MultiIndex): btc.columns = btc.columns.get_level_values(0)
        df = btc.copy()
        
        df['rsi'] = ta.rsi(df['Close'], length=14)
        df['vwap'] = ta.sma(df['Close'], length=24)
        
        ma20 = df['Close'].rolling(window=20).mean()
        std20 = df['Close'].rolling(window=20).std()
        df['bb_width'] = ((ma20 + (std20 * 2)) - (ma20 - (std20 * 2))) / ma20
        df = df.dropna()

        dxy = yf.download("DX-Y.NYB", period="5d", interval="1h", progress=False)
        dxy_change = 0
        if not dxy.empty:
            if isinstance(dxy.columns, pd.MultiIndex): dxy.columns = dxy.columns.get_level_values(0)
            if len(dxy) >= 48: dxy_change = (dxy['Close'].iloc[-1] / dxy['Close'].iloc[-48]) - 1
        
        try:
            fgi_res = requests.get("https://api.alternative.me/fng/", timeout=5).json()
            fgi = int(fgi_res['data'][0]['value'])
        except: fgi = 50
        
        return df, dxy_change, fgi
    except Exception as e:
        print(f"⚠️ Erreur Data: {e}")
        return None, 0, 50

# --- BOUCLE PRINCIPALE ---
print("🚀 Lancement du Bot Elite V2 (Optimisé)...")
send_telegram("✅ Bot Elite V2 activé et opérationnel !")

while True:
    try:
        df, dxy_change, fgi = get_data()
        if df is not None:
            last_bar = df.iloc[-1]
            prev_bar = df.iloc[-2]
            price = float(last_bar['Close'])
            rsi = float(last_bar['rsi'])
            vwap = float(last_bar['vwap'])
            bb_width = float(last_bar['bb_width'])
            
            # LOGIQUE ACHAT
            if not sim['en_position']:
                if rsi < RSI_MAX_ACHAT and price > vwap and rsi > prev_bar['rsi'] and dxy_change < 0.005:
                    sim.update({
                        "quantite_btc": (sim['solde_usdt'] * 0.999) / price,
                        "solde_usdt": 0, "prix_achat": price, "en_position": True, "highest_after_target": 0.0
                    })
                    sim["historique"].append({"date": datetime.now().strftime("%d/%m %H:%M"), "type": "ACHAT", "prix": price})
                    save_sim()
                    send_telegram(f"🚀 ACHAT\nPrix : {price:.0f}$\nRSI : {rsi:.1f}")

            # LOGIQUE VENTE
            else:
                current_gain = (price / sim['prix_achat']) - 1
                raison = None
                if current_gain <= -STOP_LOSS_PCT: raison = "STOP LOSS"
                elif rsi > 80: raison = "RSI OVERHEAT"
                elif current_gain >= TARGET_GAIN_PCT:
                    if price > sim['highest_after_target']: sim['highest_after_target'] = price
                    if price <= sim['highest_after_target'] * (1 - TRAILING_DYNAMIC): raison = "TARGET+TRAIL"

                if raison:
                    gain_final = (sim['quantite_btc'] * price) * 0.999
                    sim.update({"solde_usdt": gain_final, "quantite_btc": 0, "en_position": False})
                    sim["historique"].append({"date": datetime.now().strftime("%d/%m %H:%M"), "type": f"VENTE ({raison})", "prix": price})
                    save_sim()
                    send_telegram(f"💰 VENTE : {raison}\nGain : {current_gain*100:+.2f}%")

            update_web_dashboard(price, rsi, fgi, dxy_change, vwap, bb_width)
            
            if time.time() - last_github_push > 900:
                publier_sur_github()
                last_github_push = time.time()

    except Exception as e:
        print(f"⚠️ Erreur : {e}")
    
    time.sleep(60)
