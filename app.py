import streamlit as st
import requests
import json
import time
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Конфигурация страницы
st.set_page_config(page_title="Polymarket High-Speed Terminal", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 10: st.session_state.logs.pop(0)

# --- ПОЛУЧЕНИЕ ДАННЫХ РЫНКА (GAMMA API) ---
def get_market_data(url):
    try:
        slug = url.strip().split('/')[-1]
        response = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
        if response and len(response) > 0:
            markets = response[0].get("markets", [])
            return [{
                "question": m.get("question"),
                "yes_token": json.loads(m.get("clobTokenIds", "[]"))[0],
                "no_token": json.loads(m.get("clobTokenIds", "[]"))[1]
            } for m in markets if m.get("clobTokenIds")]
        return None
    except:
        return None

# --- ПОЛУЧЕНИЕ ЦЕНЫ И СТАКАНА (CLOB API) ---
def get_order_book_and_price(token_id):
    try:
        # Запрос стакана
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        data = requests.get(url, timeout=2).json()
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        
        # Расчет текущей цены (midpoint)
        last_price = 0
        if bids and asks:
            last_price = (float(bids[0]['price']) + float(asks[0]['price'])) / 2
        elif bids:
            last_price = float(bids[0]['price'])
        elif asks:
            last_price = float(asks[0]['price'])
            
        return bids[:5], asks[:5], last_price
    except:
        return [], [], 0

# --- ИНТЕРФЕЙС ---
st.title("⚡ Polymarket 1s Terminal")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    refresh_rate = st.slider("Обновление (сек)", 1, 5, 1) # Установлено 1 сек по умолчанию
    st.divider()
    if st.button("Очистить логи"): st.session_state.logs = []

event_url = st.text_input("Ссылка на Event:", "https://polymarket.com/event/ethereum-up-or-down-january-17-9pm-et")

if event_url:
    markets = get_market_data(event_url)
    if markets:
        # Выбор рынка и стороны
        selected_q = st.selectbox("Выбери рынок:", [m["question"] for m in markets])
        current_m = next(m for m in markets if m["question"] == selected_q)
        
        col_t1, col_t2 = st.columns(2)
        side = col_t1.radio("Исход:", ["YES (UP)", "NO (DOWN)"], horizontal=True)
        target_token = current_m["yes_token"] if "YES" in side else current_m["no_token"]

        # Получение данных
        bids, asks, last_price = get_order_book_and_price(target_token)

        # --- ТЕКУЩАЯ ЦЕНА (Крупно) ---
        st.divider()
        c_price, c_status = st.columns([1, 2])
        c_price.metric(label=f"ТЕКУЩАЯ ЦЕНА {side}", value=f"{last_price:.4f}", delta_color="normal")
        c_status.info(f"ID токена: {target_token}")

        # --- СТАКАН ---
        o_col1, o_col2 = st.columns(2)
        with o_col1:
            st.write("🟢 **Bids (Покупка)**")
            st.dataframe(bids, use_container_width=True)
        with o_col2:
            st.write("🔴 **Asks (Продажа)**")
            st.dataframe(asks, use_container_width=True)

        # --- ТОРГОВЛЯ ---
        st.divider()
        f1, f2, f3 = st.columns([1, 1, 2])
        price_input = f1.number_input("Цена", value=last_price if last_price > 0 else 0.05, step=0.01, format="%.4f")
        amount_input = f2.number_input("Кол-во", value=10, step=1)
        
        if f3.button("🚀 ОТПРАВИТЬ ОРДЕР", use_container_width=True):
            if not pk: st.error("Нет ключа!")
            else:
                try:
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    order_args = OrderArgs(token_id=target_token, price=price_input, size=amount_input, side="BUY")
                    resp = client.post_order(client.create_order(order_args))
                    add_log(f"📡 Ответ: {resp}")
                    if resp.get("success"): st.balloons()
                except Exception as e:
                    add_log(f"❌ Ошибка: {e}")

    else:
        st.warning("Данные не найдены. Проверь ссылку.")

# Логи
st.code("\n".join(st.session_state.logs[::-1]))

# Авто-обновление 1 сек
time.sleep(refresh_rate)
st.rerun()
