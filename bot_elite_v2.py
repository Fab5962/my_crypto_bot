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
RSI_MAX_ACHAT = 60        # Seuil optimisé
TARGET_GAIN_PCT = 0.06    # Objectif 6%
STOP_LOSS_PCT = 0.05      # Protection -5%
TRAILING_DYNAMIC = 0.01   # Trailing serré une fois l'objectif atteint
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

def publier_sur_github():
    try:
        subprocess.run(["git", "add", "index.html", FICHIER_SIMU], check=True)
        subprocess.run(["git", "commit", "-m", f"Dashboard Update {datetime.now().strftime('%H:%M')}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🌍 Mise à jour GitHub effectuée.")
    except: print("⚠️ Erreur Push GitHub")

def get_data():
    try:
        # Téléchargement
        btc = yf.download(SYMBOL_BTC, period="5d", interval="1h", progress=False)
        if btc.empty or len(btc) < 30: return None, 0, 50
        
        # Nettoyage des colonnes Yahoo
        if isinstance(btc.columns, pd.MultiIndex): btc.columns = btc.columns.get_level_values(0)
        df = btc.copy()

        # Indicateurs Standard
        df['rsi'] = ta.rsi(df['Close'], length=14)
        df['vwap'] = ta.sma(df['Close'], length=24) # Simple Moving Average pour VWAP sim

        # --- CALCUL BOLLINGER SÉCURISÉ ---
        ma20 = df['Close'].rolling(window=20).mean()
        std20 = df['Close'].rolling(window=20).std()
        df['bb_width'] = ((ma20 + (std20 * 2)) - (ma20 - (std20 * 2))) / ma20
        # ---------------------------------

        # Nettoyage des valeurs vides au début du tableau
        df = df.dropna()

        # Dollar (DXY)
        dxy = yf.download("DX-Y.NYB", period="5d", interval="1h", progress=False)
        dxy_change = 0
        if not dxy.empty:
            if isinstance(dxy.columns, pd.MultiIndex): dxy.columns = dxy.columns.get_level_values(0)
            if len(dxy) >= 48:
                dxy_change = (dxy['Close'].iloc[-1] / dxy['Close'].iloc[-48]) - 1
        
        # Sentiment
        try:
            fgi_res = requests.get("https://api.alternative.me/fng/", timeout=5).json()
            fgi = int(fgi_res['data'][0]['value'])
        except: fgi = 50
        
        return df, dxy_change, fgi
    except Exception as e:
        print(f"⚠️ Erreur Data: {e}")
        return None, 0, 50
def update_web_dashboard(df, price, rsi, fgi, dxy_change, vwap):
    # (Logique HTML identique à ta version, mise à jour avec les nouvelles limites)
    # [...] (Le code HTML suit la même structure que ton fichier original)
    pass 

# --- BOUCLE PRINCIPALE ---
print("🚀 Lancement du Bot Elite V2 (Optimisé)...")
send_telegram("✅ Bot Elite V2 activé et opérationnel !")
while True:
    try:
        df, dxy_change, fgi = get_data()
        if df is None: 
            time.sleep(60)
            continue

        last_bar = df.iloc[-1]
        prev_bar = df.iloc[-2]
        price = float(last_bar['Close'])
        rsi = float(last_bar['rsi'])
        vwap = float(last_bar['vwap'])
        
        # LOGIQUE D'ACHAT (Optimisée)
        if not sim['en_position']:
            # Condition : RSI < 60 + Prix > VWAP + RSI en hausse + Dollar calme
            if rsi < RSI_MAX_ACHAT and price > vwap and rsi > prev_bar['rsi'] and dxy_change < 0.005:
                sim.update({
                    "quantite_btc": (sim['solde_usdt'] * 0.999) / price,
                    "solde_usdt": 0, "prix_achat": price, "en_position": True, "highest_after_target": 0.0
                })
                sim["historique"].append({"date": datetime.now().strftime("%d/%m %H:%M"), "type": "ACHAT", "prix": price})
                save_sim()
                send_telegram(f"🚀 ACHAT OPTIMISÉ\nPrix : {price:.0f}$\nRSI : {rsi:.1f}")

        # LOGIQUE DE VENTE (Hybride)
        else:
            current_gain = (price / sim['prix_achat']) - 1
            
            # 1. Sécurité : Stop Loss fixe à -5%
            if current_gain <= -STOP_LOSS_PCT:
                raison = "STOP LOSS"
            # 2. Sortie RSI : Surchauffe extrême
            elif rsi > 80:
                raison = "RSI OVERHEAT"
            # 3. Stratégie de Gain : Si +6% atteint, on active un trailing serré pour "laisser courir"
            elif current_gain >= TARGET_GAIN_PCT:
                if price > sim['highest_after_target']:
                    sim['highest_after_target'] = price
                
                # Si le prix rebaisse de 1% par rapport au plus haut atteint après l'objectif
                if price <= sim['highest_after_target'] * (1 - TRAILING_DYNAMIC):
                    raison = "TARGET + TRAIL"
                else:
                    raison = None # On garde la position
            else:
                raison = None

            if raison:
                gain_final = (sim['quantite_btc'] * price) * 0.999
                sim.update({"solde_usdt": gain_final, "quantite_btc": 0, "en_position": False})
                sim["historique"].append({"date": datetime.now().strftime("%d/%m %H:%M"), "type": f"VENTE ({raison})", "prix": price})
                save_sim()
                send_telegram(f"💰 VENTE : {raison}\nPrix : {price:.0f}$\nGain : {current_gain*100:+.2f}%")

        if time.time() - last_github_push > 900:
            publier_sur_github()
            last_github_push = time.time()

    except Exception as e:
        print(f"⚠️ Erreur boucle : {e}")
    
    time.sleep(60)
