import streamlit as st
import requests
import json
import time
import random # Для обхода кэша
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

st.set_page_config(page_title="Polymarket Ultra-Fast", layout="wide")

if "logs" not in st.session_state: st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 10: st.session_state.logs.pop(0)

# --- GAMMA API (ИНФО О РЫНКЕ) ---
def get_market_data(url):
    try:
        slug = url.strip().split('/')[-1]
        # Добавляем случайное число к запросу, чтобы API не выдавало старый ответ
        response = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}&_cb={random.random()}", timeout=5).json()
        if response and len(response) > 0:
            markets = response[0].get("markets", [])
            return [{
                "question": m.get("question"),
                "yes_token": json.loads(m.get("clobTokenIds", "[]"))[0],
                "no_token": json.loads(m.get("clobTokenIds", "[]"))[1]
            } for m in markets if m.get("clobTokenIds")]
        return None
    except: return None

# --- CLOB API (ЖИВОЙ СТАКАН И ЦЕНА) ---
def get_order_book_and_price(token_id):
    try:
        # Прямой запрос к CLOB с защитой от кэширования
        url = f"https://clob.polymarket.com/book?token_id={token_id}&_ts={int(time.time())}"
        data = requests.get(url, timeout=2).json()
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        
        # Расчет Midpoint
        if bids and asks:
            current_price = (float(bids[0]['price']) + float(asks[0]['price'])) / 2
        elif bids: current_price = float(bids[0]['price'])
        elif asks: current_price = float(asks[0]['price'])
        else: current_price = 0.0 # Если стакан пуст, ставим 0, а не 0.5
            
        return bids[:5], asks[:5], current_price
    except: return [], [], 0

# --- ИНТЕРФЕЙС ---
st.title("⚡ Polymarket Real-Time 1s")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    # Принудительное обновление страницы каждую секунду
    st.write("Обновление: **1 секунда**")

event_url = st.text_input("Ссылка на Event:", "https://polymarket.com/event/ethereum-up-or-down-january-18-4am-et")

if event_url:
    markets = get_market_data(event_url)
    if markets:
        selected_q = st.selectbox("Рынок:", [m["question"] for m in markets])
        current_m = next(m for m in markets if m["question"] == selected_q)
        
        col_t1, col_t2 = st.columns(2)
        side = col_t1.radio("Исход:", ["YES (UP)", "NO (DOWN)"], horizontal=True)
        target_token = current_m["yes_token"] if "YES" in side else current_m["no_token"]

        # Получаем живые данные
        bids, asks, current_price = get_order_book_and_price(target_token)

        # --- ВИЗУАЛИЗАЦИЯ ЦЕНЫ ---
        st.divider()
        c_price, c_info = st.columns([1, 2])
        
        if current_price > 0:
            # Metric показывает изменение цены в реальном времени
            c_price.metric(label=f"ЦЕНА {side}", value=f"{current_price:.4f}")
        else:
            c_price.error("НЕТ ЖИВЫХ КОТИРОВОК")
            st.info("В стакане отсутствуют лимитные ордера. Попробуйте другой страйк или подождите начала торгов.")

        # --- СТАКАН ---
        o_col1, o_col2 = st.columns(2)
        with o_col1:
            st.write("🟢 **Bids (Buy Orders)**")
            st.dataframe(bids, use_container_width=True)
        with o_col2:
            st.write("🔴 **Asks (Sell Orders)**")
            st.dataframe(asks, use_container_width=True)

        # --- ТОРГОВЛЯ ---
        st.divider()
        f1, f2, f3 = st.columns([1, 1, 2])
        # Авто-подстановка цены из лучшего бида/аска
        price_to_set = current_price if current_price > 0 else 0.05
        order_price = f1.number_input("Цена ордера", value=float(price_to_set), step=0.001, format="%.4f")
        order_amount = f2.number_input("Кол-во акций", value=10, step=1)
        
        if f3.button("🚀 ОТПРАВИТЬ ОРДЕР", use_container_width=True):
            if not pk: st.error("Введите Private Key!")
            else:
                try:
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    order_args = OrderArgs(token_id=target_token, price=order_price, size=order_amount, side="BUY")
                    resp = client.post_order(client.create_order(order_args))
                    add_log(f"📡 API Response: {resp}")
                    if resp.get("success"): st.balloons()
                except Exception as e: add_log(f"❌ Error: {e}")

    else: st.warning("Рынки не найдены. Возможно, время истекло.")

st.code("\n".join(st.session_state.logs[::-1]))

# Цикл обновления 1 секунда
time.sleep(1)
st.rerun()
