import streamlit as st
import requests
import json
import pandas as pd
import time
import threading
import random
import pytz
from datetime import datetime
from websocket import create_connection
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

st.set_page_config(page_title="AGGRESSIVE SNIPER V2", layout="wide")

# --- СОСТОЯНИЕ ---
if "trades" not in st.session_state: st.session_state.trades = []
if "eth_price" not in st.session_state: st.session_state.eth_price = 0.0
if "liq_alert" not in st.session_state: st.session_state.liq_alert = False

# --- BINANCE WS WORKER ---
def binance_watcher():
    while True:
        try:
            ws = create_connection("wss://fstream.binance.com/ws/ethusdt@markPrice@1s/ethusdt@forceOrder")
            while True:
                data = json.loads(ws.recv())
                if data['e'] == 'markPriceUpdate':
                    st.session_state.eth_price = float(data['p'])
                elif data['e'] == 'forceOrder':
                    # Если ликвидация > $100k - это сигнал к агрессии
                    vol = float(data['o']['q']) * float(data['o']['p'])
                    if vol > 100000:
                        st.session_state.liq_alert = True
        except: time.sleep(5)

if "ws_init" not in st.session_state:
    threading.Thread(target=binance_watcher, daemon=True).start()
    st.session_state.ws_init = True

# --- АГРЕССИВНАЯ ТОРГОВАЯ ЛОГИКА ---
def execute_aggressive_strategy(client, tid, poly_p, size, mode):
    results = []
    # Агрессивная сетка: -5%, -12%, -20% (ближе к рынку для частого исполнения)
    offsets = [0.95, 0.88, 0.80] if mode == "UP" else [1.05, 1.12, 1.20]
    
    for factor in offsets:
        target_p = round(poly_p * factor, 3)
        try:
            order = OrderArgs(token_id=tid, price=target_p, size=size, side="BUY")
            resp = client.post_order(client.create_order(order))
            if resp.get("success"):
                results.append(f"🎯 Ловушка установлена: {target_p}")
                # Тут же планируем Тейк-Профит (в логах)
                st.session_state.trades.append({"p": target_p, "status": "WAITING"})
        except: pass
    return results

# --- ИНТЕРФЕЙС ---
st.title("🚀 AGGRESSIVE LIQUIDATION SNIPER")

with st.sidebar:
    st.header("⚙️ Настройки Бота")
    pk = st.text_input("Private Key", type="password")
    aggression = st.slider("Агрессивность (частота входов)", 1, 10, 7)
    bet_size = st.number_input("Акций за раз", value=200)
    st.divider()
    auto_pilot = st.toggle("🤖 ВКЛЮЧИТЬ АВТОПИЛОТ", value=False)

# Данные рынка
tz = pytz.timezone('US/Eastern')
now = datetime.now(tz)
slug = f"ethereum-up-or-down-{now.strftime('%B').lower()}-{now.strftime('%d').lstrip('0')}-{now.strftime('%I').lstrip('0')}{now.strftime('%p').lower()}-et"

r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()

if r and pk:
    m = r[0]['markets'][0]
    ids = json.loads(m['clobTokenIds'])
    
    # Мониторинг стакана
    tid_yes = ids[0]
    book = requests.get(f"https://clob.polymarket.com/book?token_id={tid_yes}").json()
    poly_p = float(book.get('last_price', 0.5))

    # ПАНЕЛЬ СОСТОЯНИЯ
    c1, c2, c3 = st.columns(3)
    c1.metric("ETH PRICE", f"${st.session_state.eth_price:.2f}")
    c2.metric("POLY UP", f"{poly_p:.4f}")
    c3.metric("LIQ ALERT", "🔥 YES" if st.session_state.liq_alert else "🧊 NO")

    # ЛОГИКА АВТОПИЛОТА
    if auto_pilot:
        # Если видим ликвидации ИЛИ цена ETH резко дернулась (на 0.5% за сек)
        if st.session_state.liq_alert:
            st.toast("🚨 ОБНАРУЖЕНА ЛИКВИДАЦИЯ! Атакую стакан...")
            client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
            client.set_api_creds(client.create_or_derive_api_creds())
            
            res = execute_aggressive_strategy(client, tid_yes, poly_p, bet_size, "UP")
            for r_text in res: st.write(r_text)
            
            st.session_state.liq_alert = False # Сброс триггера
            time.sleep(5) # Защита от спама

    # ТАБЛИЦА АКТИВНОСТИ
    st.divider()
    st.subheader("📝 Журнал действий")
    st.write(st.session_state.trades[::-1])

else:
    st.warning("Бот спит. Введите ключ и дождитесь активного рынка.")

time.sleep(1)
st.rerun()
