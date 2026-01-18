import streamlit as st
import requests
import json
import pandas as pd
import time
import threading
import pytz
from datetime import datetime
from websocket import create_connection

st.set_page_config(page_title="SNIPER SANDBOX", layout="wide")

# --- СОСТОЯНИЕ ПЕСОЧНИЦЫ ---
if "balance_usd" not in st.session_state: st.session_state.balance_usd = 1000.0
if "portfolio_shares" not in st.session_state: st.session_state.portfolio_shares = 0
if "virtual_orders" not in st.session_state: st.session_state.virtual_orders = []
if "eth_price" not in st.session_state: st.session_state.eth_price = 0.0
if "liq_trigger" not in st.session_state: st.session_state.liq_trigger = False

# --- ВОРКЕР BINANCE (ЦЕНА И ЛИКВИДАЦИИ) ---
def binance_sniffer():
    while True:
        try:
            ws = create_connection("wss://fstream.binance.com/ws/ethusdt@markPrice@1s/ethusdt@forceOrder")
            while True:
                data = json.loads(ws.recv())
                if data['e'] == 'markPriceUpdate':
                    st.session_state.eth_price = float(data['p'])
                elif data['e'] == 'forceOrder':
                    if float(data['o']['q']) * float(data['o']['p']) > 50000:
                        st.session_state.liq_trigger = True
        except: time.sleep(5)

if "sniffer_active" not in st.session_state:
    threading.Thread(target=binance_sniffer, daemon=True).start()
    st.session_state.sniffer_active = True

# --- ЛОГИКА ТОРГОВЛИ ФАНТИКАМИ ---
def process_paper_trading(current_poly_price):
    # Проверяем, сработали ли наши "ловушки"
    for order in st.session_state.virtual_orders[:]:
        if order['side'] == 'BUY' and current_poly_price <= order['price']:
            # Исполняем покупку
            cost = order['price'] * order['size']
            if st.session_state.balance_usd >= cost:
                st.session_state.balance_usd -= cost
                st.session_state.portfolio_shares += order['size']
                st.toast(f"✅ Исполнен вирт. ордер: BUY {order['size']} по {order['price']}")
            st.session_state.virtual_orders.remove(order)

# --- ИНТЕРФЕЙС ПЕСОЧНИЦЫ ---
st.title("🎮 SNIPER SANDBOX (Виртуальная торговля)")

# Панель баланса
stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
stat_col1.metric("Виртуальный баланс", f"${st.session_state.balance_usd:.2f}")
stat_col2.metric("Акции в портфеле", f"{st.session_state.portfolio_shares}")
stat_col3.metric("ETH Price", f"${st.session_state.eth_price:.2f}")
# Оценка портфеля (Shares * Price)
current_value = st.session_state.balance_usd + (st.session_state.portfolio_shares * 0.5) # грубая оценка
stat_col4.metric("Total Equity", f"${current_value:.2f}")

with st.sidebar:
    st.header("Настройки песочницы")
    bet_size = st.number_input("Shares per sniper shot", value=100)
    if st.button("🔄 Сбросить баланс до $1000"):
        st.session_state.balance_usd = 1000.0
        st.session_state.portfolio_shares = 0
        st.session_state.virtual_orders = []

# Данные Polymarket
tz = pytz.timezone('US/Eastern')
slug = f"ethereum-up-or-down-{datetime.now(tz).strftime('%B').lower()}-{datetime.now(tz).strftime('%d').lstrip('0')}-{datetime.now(tz).strftime('%I').lstrip('0')}{datetime.now(tz).strftime('%p').lower()}-et"
m_res = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()

if m_res:
    m_data = m_res[0]['markets'][0]
    tid_yes = json.loads(m_data['clobTokenIds'])[0]
    
    # Получаем реальную цену для проверки исполнения
    resp = requests.get(f"https://clob.polymarket.com/book?token_id={tid_yes}").json()
    real_poly_p = float(resp.get('last_price', 0.5))
    
    # Обработка "фантиков"
    process_paper_trading(real_poly_p)

    # АВТО-СНАЙПЕР (ВИРТУАЛЬНЫЙ)
    if st.session_state.liq_trigger:
        # Ставим сетку фантиками
        prices = [round(real_poly_p * 0.92, 3), round(real_poly_p * 0.85, 3)]
        for p in prices:
            st.session_state.virtual_orders.append({"price": p, "size": bet_size, "side": "BUY"})
        st.session_state.liq_trigger = False
        st.sidebar.success(f"🏹 Снайпер выстрелил по ценам {prices}")

    # ОТОБРАЖЕНИЕ ОРДЕРОВ
    st.divider()
    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("⏳ Активные ловушки (Вирт)")
        if st.session_state.virtual_orders:
            st.table(pd.DataFrame(st.session_state.virtual_orders))
        else: st.write("Нет активных ордеров")
    
    with c_right:
        st.subheader("📊 Реальный стакан Polymarket")
        st.write(f"Текущая цена: **{real_poly_p}**")
        st.dataframe(pd.DataFrame(resp.get('bids', [])).head(5))

    # КНОПКА ПРОДАЖИ (ФАНТИКИ)
    st.divider()
    if st.session_state.portfolio_shares > 0:
        if st.button(f"💰 ПРОДАТЬ ВСЁ по {real_poly_p}"):
            gain = st.session_state.portfolio_shares * real_poly_p
            st.session_state.balance_usd += gain
            st.session_state.portfolio_shares = 0
            st.balloons()
            st.success(f"Продано! Получено ${gain:.2f}")

else:
    st.warning("Рынок не найден. Проверьте время.")

time.sleep(1)
st.rerun()
