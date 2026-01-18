import streamlit as st
import requests
import json
import pytz
import time
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- ИНИЦИАЛИЗАЦИЯ ---
st.set_page_config(page_title="Polymarket Terminal", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []
if "found_m" not in st.session_state:
    st.session_state.found_m = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 10: st.session_state.logs.pop(0)

# --- ФУНКЦИЯ ПОЛУЧЕНИЯ СТАКАНА ---
def get_live_orderbook(token_id):
    try:
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        resp = requests.get(url).json()
        bids = resp.get("bids", [])
        asks = resp.get("asks", [])
        
        mid_price = 0
        if bids and asks:
            mid_price = (float(bids[0]['price']) + float(asks[0]['price'])) / 2
        return bids[:5], asks[:5], mid_price
    except Exception as e:
        return [], [], 0

# --- ГЕНЕРАТОР ССЫЛКИ СОБЫТИЯ ---
def get_event_data(offset=0):
    tz_et = pytz.timezone('US/Eastern')
    t = datetime.now(tz_et) + timedelta(hours=offset)
    
    # Генерируем слаг события (ровно как в ссылке)
    month = t.strftime("%B").lower()
    day = t.strftime("%d").lstrip('0')
    hour = t.strftime("%I").lstrip('0')
    am_pm = t.strftime("%p").lower()
    
    event_slug = f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"
    add_log(f"🔎 Проверка Event: {event_slug}")
    
    try:
        e_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
        e_resp = requests.get(e_url).json()
        
        if e_resp and len(e_resp) > 0:
            event_id = e_resp[0]['id']
            add_log(f"✅ Event найден! ID: {event_id}")
            
            m_url = f"https://gamma-api.polymarket.com/markets?event_id={event_id}&active=true"
            m_resp = requests.get(m_url).json()
            
            valid = []
            for m in m_resp:
                if "Ethereum" in m.get("question", ""):
                    tokens = json.loads(m.get("clobTokenIds", "[]"))
                    if tokens:
                        valid.append({"name": m.get("question"), "id": tokens[0]})
            return valid
    except Exception as e:
        add_log(f"❌ Ошибка: {e}")
    return []

# --- ИНТЕРФЕЙС ---
st.title("🎛️ Polymarket Live Terminal")

with st.sidebar:
    st.header("🔑 Настройки")
    pk = st.text_input("Private Key", type="password")
    st.divider()
    auto_refresh = st.checkbox("Авто-обновление стакана", value=True)
    st.info("Бот работает по времени Нью-Йорка (ET)")

col_main, col_side = st.columns([2, 1])

with col_main:
    # 1. Выбор часа
    c1, c2 = st.columns(2)
    if c1.button("🕒 Текущий час (ET)", use_container_width=True):
        st.session_state.found_m = get_event_data(0)
    if c2.button("⏭️ Следующий час (ET)", use_container_width=True):
        st.session_state.found_m = get_event_data(1)

    if st.session_state.found_m:
        # 2. Выбор рынка
        m_options = {m['name']: m['id'] for m in st.session_state.found_m}
        selected_name = st.selectbox("Выбери конкретный рынок (Strike):", list(m_options.keys()))
        token_id = m_options[selected_name]

        # 3. Визуализация стакана
        st.subheader("📊 Живой стакан (Order Book)")
        bids, asks, mid = get_live_orderbook(token_id)
        
        if mid > 0:
            st.metric("Средняя цена (Midpoint)", f"${mid:.4f}")
        
        o_c1, o_c2 = st.columns(2)
        with o_c1:
            st.write("🟢 **Покупатели (Bids)**")
            if bids: st.dataframe(bids, use_container_width=True)
            else: st.info("Нет заявок")
        with o_c2:
            st.write("🔴 **Продавцы (Asks)**")
            if asks: st.dataframe(asks, use_container_width=True)
            else: st.info("Нет заявок")

        # 4. Форма сделки
        st.divider()
        st.subheader("🚀 Выставить ордер")
        f1, f2 = st.columns(2)
        order_price = f1.number_input("Цена (лимитка)", value=0.05, step=0.01)
        order_amount = f2.number_input("Количество акций", value=10, step=1)

        if st.button("ОТПРАВИТЬ ОРДЕР В СТАКАН", use_container_width=True):
            if not pk: st.error("Введи ключ в боковой панели!")
            else:
                try:
                    add_log("🔐 Авторизация в CLOB...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    order = OrderArgs(token_id=token_id, price=order_price, size=order_amount, side="BUY")
                    resp = client.post_order(client.create_order(order))
                    add_log(f"📡 Ответ API: {resp}")
                    if resp.get("success"): st.balloons()
                    st.json(resp)
                except Exception as e:
                    add_log(f"❌ Ошибка ордера: {e}")
    else:
        st.info("Нажми кнопку часа, чтобы бот сгенерировал ссылку на Event.")

with col_side:
    st.subheader("📟 Логи работы")
    if st.button("Очистить"): st.session_state.logs = []
    st.code("\n".join(st.session_state.logs[::-1]))
    
    # Авто-обновление стакана через JavaScript (Streamlit rerun)
    if auto_refresh and "found_m" in st.session_state and st.session_state.found_m:
        time.sleep(5)
        st.rerun()
