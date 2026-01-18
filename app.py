import streamlit as st
import requests
import json
import pytz
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Link Generator", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

# --- ГЕНЕРАТОР ВИЗУАЛЬНОЙ ССЫЛКИ ---
def get_event_by_generated_link(offset_hours=0):
    # Работаем строго по времени Нью-Йорка (ET)
    tz_et = pytz.timezone('US/Eastern')
    t = datetime.now(tz_et) + timedelta(hours=offset_hours)
    
    # Собираем части ссылки
    month = t.strftime("%B").lower() # january
    day = t.strftime("%d").lstrip('0') # 17
    hour = t.strftime("%I").lstrip('0') # 9
    am_pm = t.strftime("%p").lower() # pm
    
    # Вот она - визуальная ссылка (slug)
    event_slug = f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"
    
    full_url = f"https://polymarket.com/event/{event_slug}"
    add_log(f"🔗 Сгенерирована ссылка: {full_url}")
    
    try:
        # Пытаемся зайти по этой ссылке через API
        api_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
        resp = requests.get(api_url).json()
        
        if resp and len(resp) > 0:
            event_id = resp[0]['id']
            add_log(f"✅ Успех! Рынок по этой ссылке найден и активен.")
            
            # Тянем список исходов внутри этой ссылки
            m_url = f"https://gamma-api.polymarket.com/markets?event_id={event_id}&active=true"
            m_resp = requests.get(m_url).json()
            
            markets = []
            for m in m_resp:
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                if tokens:
                    markets.append({"name": m.get("question"), "token_id": tokens[0]})
            return markets, full_url
        else:
            add_log("🔘 API говорит: такой ссылки еще не существует на сервере.")
    except Exception as e:
        add_log(f"❌ Ошибка подключения: {e}")
    
    return [], full_url

# --- ИНТЕРФЕЙС ---
st.title("🔗 Polymarket Hourly Link Generator")

with st.sidebar:
    st.header("Ключи")
    pk = st.text_input("Private Key", type="password")
    st.divider()
    st.info("Бот генерирует ссылку на основе времени ET (Нью-Йорк).")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🛠️ Генератор")
    
    c1, c2 = st.columns(2)
    if c1.button("🕒 Ссылка на ТЕКУЩИЙ час"):
        st.session_state.markets, st.session_state.url = get_event_by_generated_link(0)
    if c2.button("⏭️ Ссылка на СЛЕДУЮЩИЙ час"):
        st.session_state.markets, st.session_state.url = get_event_by_generated_link(1)

    if "url" in st.session_state:
        st.write(f"**Рабочая ссылка:** {st.session_state.url}")
        
        if "markets" in st.session_state and st.session_state.markets:
            st.success(f"Внутри найдено {len(st.session_state.markets)} активных рынков")
            
            market_options = {m['name']: m['token_id'] for m in st.session_state.markets}
            selected_name = st.selectbox("Выбери конкретный страйк:", list(market_options.keys()))
            token_id = market_options[selected_name]
            
            st.divider()
            price = st.number_input("Цена (например 0.05)", value=0.05)
            amount = st.number_input("Кол-во акций", value=10)
            
            if st.button("🚀 ВЫСТАВИТЬ ОРДЕР", use_container_width=True):
                if not pk: st.error("Вставь Private Key!")
                else:
                    try:
                        add_log("🔐 Авторизация...")
                        client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                        client.set_api_creds(client.create_or_derive_api_creds())
                        
                        order = OrderArgs(token_id=token_id, price=price, size=amount, side=BUY)
                        resp = client.post_order(client.create_order(order))
                        add_log(f"📡 Результат: {resp}")
                        if resp.get("success"): st.balloons()
                        st.json(resp)
                    except Exception as e:
                        add_log(f"❌ Ошибка: {e}")
        else:
            st.warning("Ссылка сгенерирована, но Polymarket еще не открыл торги по ней.")

with col2:
    st.subheader("📟 Логи генерации")
    st.code("\n".join(st.session_state.logs[::-1]))
