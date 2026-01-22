import pandas as pd
import yfinance as yf
import numpy as np

# --- CONFIGURATION ---
SYMBOL = "BTC-USD"
CAPITAL_DEPART = 100.0

print(f"📥 Récupération des données pour l'analyse d'expert...")
df = yf.download(SYMBOL, period="730d", interval="1h", progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

# --- CALCUL DES INDICATEURS EXPERTS ---
# 1. RSI
delta = df['Close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df['RSI'] = 100 - (100 / (1 + rs))

# 2. VWAP (Moyenne 24h)
df['VWAP'] = df['Close'].rolling(window=24).mean()

# 3. Bandes de Bollinger & Squeeze
df['MA20'] = df['Close'].rolling(window=20).mean()
df['STD'] = df['Close'].rolling(window=20).std()
df['BB_UPPER'] = df['MA20'] + (df['STD'] * 2)
df['BB_LOWER'] = df['MA20'] - (df['STD'] * 2)
df['BB_WIDTH'] = (df['BB_UPPER'] - df['BB_LOWER']) / df['MA20']

# --- SIMULATION ---
solde = CAPITAL_DEPART
btc = 0
en_position = False
prix_achat = 0
nb_trades = 0

for i in range(1, len(df)):
    row = df.iloc[i]
    prev_row = df.iloc[i-1]
    prix = float(row['Close'])
    
    if not en_position:
        # LA STRATÉGIE "ULTIME"
        cond_rsi = row['RSI'] < 55 and row['RSI'] > prev_row['RSI'] # Bas mais remonte
        cond_volatilite = row['BB_WIDTH'] > prev_row['BB_WIDTH']    # Sortie de squeeze
        cond_tendance = prix > row['VWAP']                          # Force du marché
        
        if cond_rsi and cond_volatilite and cond_tendance:
            btc = solde / prix
            solde = 0
            prix_achat = prix
            en_position = True
            nb_trades += 1
    else:
        # SORTIE EXPERTE : Trailing Stop ou RSI saturé
        gain_actuel = (prix - prix_achat) / prix_achat
        if row['RSI'] > 75 or gain_actuel > 0.05 or gain_actuel < -0.03:
            solde = btc * prix
            btc = 0
            en_position = False

capital_final = solde if not en_position else btc * df.iloc[-1]['Close']

print("\n" + "⭐" * 15)
print(f" RÉSULTAT STRATÉGIE EXPERTE ")
print(f"Capital final  : {capital_final:.2f}$")
print(f"Performance    : {((capital_final/CAPITAL_DEPART)-1)*100:+.2f}%")
print(f"Nombre de trades: {nb_trades}")
print("⭐" * 15)
