import streamlit as st
import requests
import json
import time
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Конфигурация страницы
st.set_page_config(page_title="Polymarket CLOB Terminal", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

# --- 1. GAMMA API: ПОЛУЧЕНИЕ ДАННЫХ РЫНКА ---
def get_market_data(url):
    try:
        slug = url.strip().split('/')[-1]
        # Запрашиваем информацию о событии через Gamma API
        response = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=10).json()
        
        if response and len(response) > 0:
            event = response[0]
            # Вытаскиваем все рынки внутри этого события
            markets = event.get("markets", [])
            market_list = []
            for m in markets:
                clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                if clob_ids:
                    market_list.append({
                        "question": m.get("question"),
                        "yes_token": clob_ids[0],
                        "no_token": clob_ids[1]
                    })
            return market_list
        return None
    except Exception as e:
        add_log(f"❌ Ошибка Gamma API: {e}")
        return None

# --- 2. CLOB API: ПОЛУЧЕНИЕ СТАКАНА ---
def get_order_book(token_id):
    try:
        # Прямой запрос к книге ордеров CLOB
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        data = requests.get(url, timeout=10).json()
        return data.get("bids", []), data.get("asks", [])
    except Exception as e:
        add_log(f"❌ Ошибка CLOB API: {e}")
        return [], []

# --- ИНТЕРФЕЙС ---
st.title("🚀 Polymarket CLOB Terminal")

with st.sidebar:
    st.header("Настройки")
    pk = st.text_input("Private Key (Ethereum)", type="password", help="Ключ для подписи ордеров")
    st.divider()
    auto_refresh = st.checkbox("Авто-обновление стакана (5с)", value=True)

# Ввод ссылки
event_url = st.text_input(
    "Введите ссылку на Event (Up/Down):", 
    value="https://polymarket.com/event/ethereum-up-or-down-january-17-9pm-et"
)

if event_url:
    markets = get_market_data(event_url)
    
    if markets:
        # Выбор конкретного интервала/вопроса
        st.subheader("🎯 Доступные рынки")
        selected_q = st.selectbox("Выберите рынок из события:", [m["question"] for m in markets])
        current_m = next(m for m in markets if m["question"] == selected_q)
        
        # Выбор стороны
        side_choice = st.radio("Ваш прогноз:", ["YES (Рост)", "NO (Падение)"], horizontal=True)
        target_token = current_m["yes_token"] if "YES" in side_choice else current_m["no_token"]

        # --- ОТОБРАЖЕНИЕ ОРДЕРБУКА ---
        st.divider()
        st.subheader(f"📊 Стакан ордеров: {side_choice}")
        bids, asks = get_order_book(target_token)
        
        col_bids, col_asks = st.columns(2)
        with col_bids:
            st.write("🟢 **Bids (Покупка)**")
            if bids: st.table(bids[:5])
            else: st.info("Нет заявок")
            
        with col_asks:
            st.write("🔴 **Asks (Продажа)**")
            if asks: st.table(asks[:5])
            else: st.info("Нет заявок")

        # --- ТОРГОВЫЙ МОДУЛЬ ---
        st.divider()
        st.subheader("⌨️ Выставление ордера")
        c1, c2 = st.columns(2)
        price = c1.number_input("Цена (от 0.01 до 0.99)", value=0.05, step=0.01)
        amount = c2.number_input("Количество акций", value=10, step=1)

        if st.button("🚀 ОТПРАВИТЬ ЛИМИТНЫЙ ОРДЕР", use_container_width=True):
            if not pk:
                st.error("Ошибка: Введите Private Key в боковом меню!")
            else:
                try:
                    add_log("🔐 Инициализация клиента...")
                    # Создание клиента согласно Quickstart
                    host = "https://clob.polymarket.com"
                    client = ClobClient(host, key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    # Создание ордера
                    order_args = OrderArgs(
                        token_id=target_token,
                        price=price,
                        size=amount,
                        side="BUY"
                    )
                    signed_order = client.create_order(order_args)
                    resp = client.post_order(signed_order) # Отправка в CLOB
                    
                    add_log(f"📡 Ответ биржи: {resp}")
                    if resp.get("success"):
                        st.balloons()
                except Exception as e:
                    add_log(f"⛔ Ошибка транзакции: {e}")

    else:
        st.warning("Не удалось загрузить данные. Проверьте ссылку.")

with st.expander("📟 Логи терминала", expanded=True):
    st.code("\n".join(st.session_state.logs[::-1]))

if auto_refresh and event_url:
    time.sleep(5)
    st.rerun()
