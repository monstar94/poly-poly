import streamlit as st
import requests
import json
import pytz
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Polymarket Terminal Pro", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

# --- ПОЛУЧЕНИЕ СТАКАНА ---
def get_live_orderbook(token_id):
    try:
        # Прямой запрос к книге ордеров
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        resp = requests.get(url).json()
        bids = resp.get("bids", []) # Покупатели
        asks = resp.get("asks", []) # Продавцы
        
        # Расчет средней цены для ориентира
        mid_price = 0
        if bids and asks:
            mid_price = (float(bids[0]['price']) + float(asks[0]['price'])) / 2
            
        return bids[:5], asks[:5], mid_price
    except:
        return [], [], 0

# --- ГЕНЕРАТОР ---
def get_event_data(offset=0):
    tz_et = pytz.timezone('US/Eastern')
    t = datetime.now(tz_et) + timedelta(hours=offset)
    
    # Генерируем слаг события (ровно как в ссылке)
    month, day, hour, am_pm = t.strftime("%B").lower(), t.strftime("%d").lstrip('0'), t.strftime("%I").lstrip('0'), t.strftime("%p").lower()
    event_slug = f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"
    
    add_log(f"🛠️ Проверка: https://polymarket.com/event/{event_slug}")
    
    try:
        e_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
        e_resp = requests.get(e_url).json()
        
        if e_resp and len(e_resp) > 0:
            event_id = e_resp[0]['id']
            add_log(f"✅ Событие найдено! ID: {event_id}")
            
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
st.title("🎛️ Polymarket Trading Terminal")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    if st.button("🔄 Обновить данные"):
        st.rerun()

col_main, col_side = st.columns([2, 1])

with col_main:
    # 1. Поиск рынков
    c1, c2 = st.columns(2)
    if c1.button("🕒 Текущий час (ET)"):
        st.session_state.found_m = get_event_data(0)
    if c2.button("⏭️ Следующий час (ET)"):
        st.session_state.found_m = get_event_data(1)

    if "found_m" in st.session_state and st.session_state.found_m:
        # 2. Выбор конкретного страйка
        m_options = {m['name']: m['id'] for m in st.session_state.found_m}
        selected_name = st.selectbox("Выбери рынок:", list(m_options.keys()))
        token_id = m_options[selected_name]

        # 3. Визуализация стакана
        st.subheader("📊 Живой стакан ордеров")
        bids, asks, mid = get_live_orderbook(token_id)
        
        if mid > 0:
            st.metric("Средняя цена (Midpoint)", f"${mid:.4f}")
        
        ob_c1, ob_c2 = st.columns(2)
        with ob_c1:
            st.write("🟢 **Bids (Покупка)**")
            if bids: st.table(bids)
            else: st.info("Нет активных заявок на покупку")
        with ob_c2:
            st.write("🔴 **Asks (Продажа)**")
            if asks: st.table(asks)
            else: st.info("Нет активных заявок на продажу")

        # 4. Форма ордера
        st.divider()
        st.subheader("🚀 Быстрый ордер")
        f1, f2 = st.columns(2)
        order_price = f1.number_input("Твоя цена (например 0.05)", value=0.05, step=0.01)
        order_amount = f2.number_input("Кол-во акций", value=10, step=1)

        if st.button("ВЫСТАВИТЬ ЛИМИТКУ", use_container_width=True):
            if not pk: st.error("Введи ключ!")
            else:
                try:
                    add_log("🔐 Подключение...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    order = OrderArgs(token_id=token_id, price=order_price, size=order_amount, side="BUY")
                    resp = client.post_order(client.create_order(order))
                    add_log(f"📡 Ответ API: {resp}")
                    if resp.get("success"): st.balloons()
                except Exception as e:
                    add_log(f"❌ Ошибка: {e}")

with col_side:
    st.subheader("📟 Логи")
    st.code("\n".join(st.session_state.logs[::-1]))
