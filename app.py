import streamlit as st
import requests
import json
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- КОНСТАНТЫ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Event Bot", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.logs) > 20: st.session_state.logs.pop(0)

# --- ФУНКЦИЯ ПАРСИНГА EVENT ---
def get_markets_from_event(slug):
    add_log(f"🔗 Загрузка данных события: {slug}...")
    try:
        # Получаем данные о событии через Gamma API
        url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        resp = requests.get(url).json()
        
        markets_data = []
        if resp and len(resp) > 0:
            event_id = resp[0].get("id")
            # Теперь ищем все активные рынки внутри этого события
            m_url = f"https://gamma-api.polymarket.com/markets?event_id={event_id}&active=true"
            m_resp = requests.get(m_url).json()
            
            for m in m_resp:
                tokens = m.get("clobTokenIds")
                if tokens:
                    t_list = json.loads(tokens)
                    markets_data.append({
                        "name": m.get("question"),
                        "token_id": t_list[0], # YES token
                        "end": m.get("endDate")
                    })
        return markets_data
    except Exception as e:
        add_log(f"❌ Ошибка парсинга: {e}")
        return []

# --- ИНТЕРФЕЙС ---
st.title("📈 Polymarket Event Trader")

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("1. Подключение")
    pk = st.text_input("Private Key (0x...)", type="password")
    
    # Ссылка, которую ты скинул, имеет слаг 'ethereum-up-or-down-january-17-6pm-et'
    event_slug = st.text_input("Slug события (из ссылки)", value="ethereum-up-or-down-january-17-6pm-et")
    
    if st.button("🔄 Обновить список рынков"):
        st.session_state.active_markets = get_markets_from_event(event_slug)

    if "active_markets" in st.session_state and st.session_state.active_markets:
        st.subheader("2. Выбор интервала")
        options = {m['name']: m['token_id'] for m in st.session_state.active_markets}
        selected_name = st.selectbox("Выберите актуальное время:", list(options.keys()))
        token_id = options[selected_name]
        
        st.code(f"Активный Token ID: {token_id}")

        st.subheader("3. Параметры стратегии")
        c1, c2 = st.columns(2)
        price = c1.number_input("Цена (отскок)", value=0.05, step=0.01, min_value=0.01, max_value=0.99)
        amount = c2.number_input("Кол-во акций", value=10, step=1)

        if st.button("🚀 ВЫСТАВИТЬ ЛИМИТКУ", use_container_width=True):
            if not pk:
                st.error("Введите Private Key!")
            else:
                try:
                    add_log("⚙️ Авторизация...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    # Важный шаг для новых аккаунтов
                    creds = client.create_or_derive_api_creds()
                    client.set_api_creds(creds)
                    
                    add_log(f"📡 Отправка ордера на {token_id}...")
                    order = OrderArgs(token_id=token_id, price=price, size=amount, side=BUY)
                    signed = client.create_order(order)
                    resp = client.post_order(signed)
                    
                    if resp.get("success"):
                        add_log("🎯 ОРДЕР В СТАКАНЕ!")
                        st.balloons()
                    else:
                        add_log(f"⚠️ Биржа отклонила: {resp}")
                    st.json(resp)
                except Exception as e:
                    add_log(f"⛔ Ошибка: {e}")
    else:
        st.warning("Нажмите 'Обновить', чтобы увидеть доступные рынки.")

with col_right:
    st.subheader("📟 Консоль")
    log_container = st.empty()
    log_container.code("\n".join(st.session_state.logs[::-1]))
