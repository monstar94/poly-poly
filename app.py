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

# --- ПРОВЕРКА ПОДКЛЮЧЕНИЯ К CLOB API ---
def get_live_orderbook(token_id):
    try:
        # Прямое обращение к API стакана
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        resp = requests.get(url, timeout=5).json()
        bids = resp.get("bids", [])
        asks = resp.get("asks", [])
        
        mid_price = 0
        if bids and asks:
            mid_price = (float(bids[0]['price']) + float(asks[0]['price'])) / 2
        return bids[:5], asks[:5], mid_price
    except Exception as e:
        add_log(f"❌ Ошибка CLOB API: {e}")
        return [], [], 0

# --- ГЕНЕРАТОР ССЫЛКИ И ПОИСК СОБЫТИЯ ---
def get_event_data(offset=0):
    tz_et = pytz.timezone('US/Eastern')
    t = datetime.now(tz_et) + timedelta(hours=offset)
    
    # Генерация слага по твоей схеме
    month = t.strftime("%B").lower()
    day = t.strftime("%d").lstrip('0')
    hour = t.strftime("%I").lstrip('0')
    am_pm = t.strftime("%p").lower()
    
    event_slug = f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"
    add_log(f"🔎 Запрос к Gamma API: {event_slug}")
    
    try:
        # Поиск события через Gamma API
        e_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
        e_resp = requests.get(e_url, timeout=5).json()
        
        if e_resp and len(e_resp) > 0:
            event_id = e_resp[0]['id']
            add_log(f"✅ Event найден (ID: {event_id})")
            
            # Получение рынков внутри события
            m_url = f"https://gamma-api.polymarket.com/markets?event_id={event_id}&active=true"
            m_resp = requests.get(m_url).json()
            
            valid = []
            for m in m_resp:
                if "Ethereum" in m.get("question", ""):
                    tokens = json.loads(m.get("clobTokenIds", "[]"))
                    if tokens:
                        valid.append({"name": m.get("question"), "id": tokens[0]})
            return valid
        else:
            add_log(f"🔘 Событие {event_slug} пока не создано.")
    except Exception as e:
        add_log(f"❌ Ошибка Gamma API: {e}")
    return []

# --- ИНТЕРФЕЙС ---
st.title("🎛️ Polymarket Live Terminal")

with st.sidebar:
    st.header("🔑 Доступ")
    pk = st.text_input("Private Key", type="password")
    auto_refresh = st.checkbox("Авто-обновление стакана", value=True)
    st.divider()
    st.info("Бот подключается к Gamma API (поиск) и CLOB API (торговля).")

col_main, col_side = st.columns([2, 1])

with col_main:
    c1, c2 = st.columns(2)
    if c1.button("🕒 ТЕКУЩИЙ ЧАС", use_container_width=True):
        st.session_state.found_m = get_event_data(0)
    if c2.button("⏭️ СЛЕДУЮЩИЙ ЧАС", use_container_width=True):
        st.session_state.found_m = get_event_data(1)

    if st.session_state.found_m:
        m_options = {m['name']: m['id'] for m in st.session_state.found_m}
        selected_name = st.selectbox("🎯 Выбери конкретный рынок:", list(m_options.keys()))
        token_id = m_options[selected_name]

        # ОТОБРАЖЕНИЕ ОРДЕРБУКА
        st.subheader("📊 Живой стакан (CLOB API)")
        bids, asks, mid = get_live_orderbook(token_id)
        
        if mid > 0:
            st.metric("Средняя цена (Midpoint)", f"{mid:.4f}")
        
        o_c1, o_c2 = st.columns(2)
        with o_c1:
            st.write("🟢 **Bids (Покупка)**")
            if bids: st.dataframe(bids, use_container_width=True)
            else: st.info("Нет активных заявок")
        with o_c2:
            st.write("🔴 **Asks (Продажа)**")
            if asks: st.dataframe(asks, use_container_width=True)
            else: st.info("Нет активных заявок")

        st.divider()
        st.subheader("🚀 Торговля")
        f1, f2 = st.columns(2)
        order_price = f1.number_input("Лимитная цена", value=0.05, format="%.2f")
        order_amount = f2.number_input("Кол-во акций", value=10)

        if st.button("ОТПРАВИТЬ ОРДЕР", use_container_width=True):
            if not pk: st.error("Введи ключ!")
            else:
                try:
                    add_log("🔐 Подключение к торговой сессии...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    order = OrderArgs(token_id=token_id, price=order_price, size=order_amount, side="BUY")
                    resp = client.post_order(client.create_order(order))
                    add_log(f"📡 Ответ: {resp}")
                    if resp.get("success"): st.balloons()
                except Exception as e:
                    add_log(f"❌ Ошибка ордера: {e}")
    else:
        st.info("Нажми кнопку часа, чтобы загрузить рынки из API.")

with col_side:
    st.subheader("📟 Дебаг-логи")
    if st.button("Очистить"): st.session_state.logs = []
    st.code("\n".join(st.session_state.logs[::-1]))
    
    if auto_refresh and st.session_state.found_m:
        time.sleep(5)
        st.rerun()
