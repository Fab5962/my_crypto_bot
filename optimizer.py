import pandas as pd
import yfinance as yf
import numpy as np

# --- CHARGEMENT DES DONNÉES (Une seule fois pour aller vite) ---
SYMBOL = "BTC-USD"
df = yf.download(SYMBOL, period="730d", interval="1h", progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

# Calcul des indicateurs de base
delta = df['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
df['RSI'] = 100 - (100 / (1 + (gain / loss)))
df['VWAP'] = df['Close'].rolling(window=24).mean()
df['MA20'] = df['Close'].rolling(window=20).mean()
df['STD'] = df['Close'].rolling(window=20).std()
df['BB_WIDTH'] = ((df['MA20'] + (df['STD'] * 2)) - (df['MA20'] - (df['STD'] * 2))) / df['MA20']

def backtest_logic(rsi_limit, target_gain, stop_loss):
    solde = 100.0
    btc = 0
    en_position = False
    prix_achat = 0
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        prix = float(row['Close'])
        
        if not en_position:
            if row['RSI'] < rsi_limit and row['RSI'] > prev_row['RSI'] and row['BB_WIDTH'] > prev_row['BB_WIDTH'] and prix > row['VWAP']:
                btc = solde / prix
                solde = 0
                prix_achat = prix
                en_position = True
        else:
            gain_actuel = (prix - prix_achat) / prix_achat
            if row['RSI'] > 75 or gain_actuel > target_gain or gain_actuel < stop_loss:
                solde = btc * prix
                btc = 0
                en_position = False
    
    return solde if not en_position else btc * df.iloc[-1]['Close']

# --- BOUCLE D'OPTIMISATION ---
print("🔍 Recherche de la meilleure combinaison (Dichotomie)...")
resultats = []

for r in [45, 50, 55, 60]:
    for tg in [0.02, 0.04, 0.06]:
        for sl in [-0.02, -0.03, -0.05]:
            final = backtest_logic(r, tg, sl)
            resultats.append((final, r, tg, sl))

# Tri par performance
resultats.sort(reverse=True, key=lambda x: x[0])
best = resultats[0]

print("\n" + "🏆 MEILLEURE STRATÉGIE TROUVÉE 🏆")
print(f"Capital Final : {best[0]:.2f}$")
print(f"Paramètres : RSI < {best[1]} | Gain : {best[2]*100}% | Stop : {best[3]*100}%")
print("="*35)
