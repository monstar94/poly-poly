import streamlit as st
import requests
import json
import pytz
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Pro Auto", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

# --- ПОЛУЧЕНИЕ СТАКАНА (ORDERBOOK) ---
def get_orderbook(token_id):
    try:
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        resp = requests.get(url).json()
        bids = resp.get("bids", [])[:3] # Топ-3 покупки
        asks = resp.get("asks", [])[:3] # Топ-3 продажи
        return bids, asks
    except:
        return [], []

# --- УЛУЧШЕННЫЙ ГЕНЕРАТОР ---
def get_auto_market(offset_hours=0):
    tz_et = pytz.timezone('US/Eastern')
    target_time = datetime.now(tz_et) + timedelta(hours=offset_hours)
    
    month = target_time.strftime("%B").lower()
    day = target_time.strftime("%d").lstrip('0')
    year = target_time.strftime("%Y")
    hour = target_time.strftime("%I").lstrip('0')
    am_pm = target_time.strftime("%p").lower()
    
    slug = f"ethereum-price-at-{month}-{day}-{year}-{hour}{am_pm}-et"
    add_log(f"🔎 Проверка ссылки: {slug}")
    
    try:
        # Пробуем через основной API
        api_url = f"https://gamma-api.polymarket.com/markets?slug={slug}"
        resp = requests.get(api_url).json()
        
        if resp and isinstance(resp, list) and len(resp) > 0:
            m = resp[0]
            tokens = json.loads(m.get("clobTokenIds"))
            add_log("✅ Рынок найден успешно!")
            return {
                "name": m.get("question"),
                "token_id": tokens[0],
                "slug": slug
            }
        else:
            add_log(f"🔘 API ответило: рынок '{slug}' пока не создан.")
    except Exception as e:
        add_log(f"❌ Ошибка запроса: {e}")
    return None

# --- ИНТЕРФЕЙС ---
st.title("🛡️ Polymarket Smart Terminal")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    st.divider()
    if st.button("🔄 Сбросить всё"):
        st.session_state.clear()
        st.rerun()

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📡 Поиск активного часа")
    c1, c2 = st.columns(2)
    if c1.button("🕒 Текущий час (ET)", use_container_width=True):
        st.session_state.m_data = get_auto_market(0)
    if c2.button("⏭️ Следующий час (ET)", use_container_width=True):
        st.session_state.m_data = get_auto_market(1)

    if "m_data" in st.session_state and st.session_state.m_data:
        m = st.session_state.m_data
        st.info(f"**Рынок:** {m['name']}")
        
        # Блок Стакана
        st.subheader("📊 Текущий стакан (Ордербук)")
        bids, asks = get_orderbook(m['token_id'])
        
        o1, o2 = st.columns(2)
        with o1:
            st.write("🟢 Покупатели (Bids)")
            if bids: st.table(bids)
            else: st.write("Нет заявок")
        with o2:
            st.write("🔴 Продавцы (Asks)")
            if asks: st.table(asks)
            else: st.write("Нет заявок")

        st.divider()
        st.subheader("⚡ Выставить лимитку по 0.05")
        price = st.number_input("Цена", value=0.05, step=0.01)
        amount = st.number_input("Количество", value=10, step=1)
        
        if st.button("🚀 ОТПРАВИТЬ ОРДЕР", use_container_width=True):
            if not pk: st.error("Введите ключ!")
            else:
                try:
                    add_log("🔐 Авторизация...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    order = OrderArgs(token_id=m['token_id'], price=price, size=amount, side=BUY)
                    resp = client.post_order(client.create_order(order))
                    add_log(f"📡 Ответ биржи: {resp}")
                    if resp.get("success"): st.balloons()
                    st.json(resp)
                except Exception as e:
                    add_log(f"⛔ Ошибка: {e}")
    else:
        st.warning("Нажмите кнопку поиска. Если рынок не найден, значит Polymarket еще не создал лот на это время.")

with col2:
    st.subheader("📟 Дебаг-консоль")
    st.code("\n".join(st.session_state.logs[::-1]))
