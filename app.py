import streamlit as st
import requests
import json
import pandas as pd
import time
import threading
import pytz
import random
from datetime import datetime
from websocket import create_connection

st.set_page_config(page_title="PRO SNIPER SANDBOX", layout="wide")

# --- ИНИЦИАЛИЗАЦИЯ ПЕСОЧНИЦЫ ---
if "balance" not in st.session_state: st.session_state.balance = 1000.0
if "shares" not in st.session_state: st.session_state.shares = 0
if "virt_orders" not in st.session_state: st.session_state.virt_orders = []
if "eth_p" not in st.session_state: st.session_state.eth_p = 0.0
if "last_liqs" not in st.session_state: st.session_state.last_liqs = []
if "history" not in st.session_state: st.session_state.history = []

# --- BINANCE WEBSOCKET (ФОНОВЫЙ ПОТОК) ---
def binance_worker():
    while True:
        try:
            ws = create_connection("wss://fstream.binance.com/ws/ethusdt@markPrice@1s/ethusdt@forceOrder")
            while True:
                data = json.loads(ws.recv())
                if data['e'] == 'markPriceUpdate':
                    st.session_state.eth_p = float(data['p'])
                elif data['e'] == 'forceOrder':
                    o = data['o']
                    val = float(o['q']) * float(o['p'])
                    if val > 10000: # Фильтр крупных ликв
                        st.session_state.last_liqs.append({"t": datetime.now().strftime("%H:%M:%S"), "v": val, "s": o['S']})
                        if len(st.session_state.last_liqs) > 10: st.session_state.last_liqs.pop(0)
        except: time.sleep(5)

if "ws_init" not in st.session_state:
    threading.Thread(target=binance_worker, daemon=True).start()
    st.session_state.ws_init = True

# --- ЛОГИКА ТОРГОВЛИ ---
def sync_sandbox(current_poly_price):
    for order in st.session_state.virt_orders[:]:
        # Если цена на Poly упала до нашей ловушки или ниже
        if current_poly_price <= order['p']:
            cost = order['p'] * order['s']
            if st.session_state.balance >= cost:
                st.session_state.balance -= cost
                st.session_state.shares += order['s']
                st.session_state.history.append(f"✅ КУПЛЕНО: {order['s']} акций по {order['p']}")
            st.session_state.virt_orders.remove(order)

# --- ИНТЕРФЕЙС ---
# 1. Хедер с метриками баланса
st.title("🏹 SNIPER SANDBOX TERMINAL")
m1, m2, m3, m4 = st.columns(4)
m1.metric("💵 Виртуальный USD", f"${st.session_state.balance:.2f}")
m2.metric("📦 Акции (UP)", f"{st.session_state.shares}")
m3.metric("💎 ETH Binance", f"${st.session_state.eth_p:.2f}")
total_val = st.session_state.balance + (st.session_state.shares * 0.5)
m4.metric("📈 Общий капитал", f"${total_val:.2f}")

st.divider()

# 2. Основная рабочая область
col_main, col_side = st.columns([3, 1])

with col_main:
    # Определение активного рынка
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    slug = f"ethereum-up-or-down-{now.strftime('%B').lower()}-{now.strftime('%d').lstrip('0')}-{now.strftime('%I').lstrip('0')}{now.strftime('%p').lower()}-et"
    
    try:
        m_res = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
        m_data = m_res[0]['markets'][0]
        tid = json.loads(m_data['clobTokenIds'])[0]
        
        # Получаем живой стакан
        book = requests.get(f"https://clob.polymarket.com/book?token_id={tid}").json()
        poly_p = float(book.get('last_price', 0.5))
        
        # Обработка песочницы
        sync_sandbox(poly_p)
        
        # Визуализация стакана
        st.write(f"### 📊 Стакан Polymarket: `{slug}`")
        st.write(f"Текущая цена: **{poly_p}**")
        
        b_df = pd.DataFrame(book.get('bids', []))
        if not b_df.empty:
            st.dataframe(b_df[['price', 'size']].head(5), use_container_width=True)
        
        # Управление ордерами
        st.subheader("⏳ Твои активные ловушки (Виртуальные)")
        if st.session_state.virt_orders:
            st.table(st.session_state.virt_orders)
        else: st.info("Ловушки не расставлены. Ждем ликвидаций или нажми кнопку ниже.")

        if st.button("🎯 РАССТАВИТЬ СЕТКУ ВРУЧНУЮ (Песочница)"):
            grid = [round(poly_p * 0.95, 3), round(poly_p * 0.88, 3)]
            for p in grid:
                st.session_state.virt_orders.append({"p": p, "s": 200})
            st.toast("Ловушки расставлены!")

    except:
        st.error("Рынок еще не создан. Подождите начала часа.")

with col_side:
    st.subheader("🔥 Ликвидации")
    if st.session_state.last_liqs:
        for l in reversed(st.session_state.last_liqs):
            color = "red" if l['s'] == "SELL" else "green"
            st.markdown(f"**{l['t']}** | <span style='color:{color}'>${l['v']:.0f}</span>", unsafe_allow_html=True)
    else: st.write("Поиск...")
    
    st.divider()
    st.subheader("📜 Журнал")
    for log in reversed(st.session_state.history):
        st.caption(log)

# 3. Кнопка выхода (Продажа фантиков)
st.divider()
if st.session_state.shares > 0:
    if st.button(f"💰 ПРОДАТЬ ВСЁ (Фиксация прибыли по {poly_p})", use_container_width=True):
        st.session_state.balance += (st.session_state.shares * poly_p)
        st.session_state.history.append(f"💰 ПРОДАНО: {st.session_state.shares} по {poly_p}")
        st.session_state.shares = 0
        st.balloons()

time.sleep(1)
st.rerun()
