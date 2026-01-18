import streamlit as st
import requests
import json
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Константы
BUY = "BUY"
st.set_page_config(page_title="Polymarket Pro Bot", layout="wide")

# Логирование
if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.logs) > 20: st.session_state.logs.pop(0)

# Прямое получение рынков из CLOB
def get_live_markets():
    add_log("📡 Прямое подключение к CLOB API...")
    try:
        # Получаем только активные рынки напрямую из торгового API
        # Фильтруем по ключевому слову 'Ethereum' и 'Price'
        url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100"
        resp = requests.get(url).json()
        
        live_markets = []
        for m in resp:
            q = m.get("question", "").lower()
            if "ethereum" in q and "price" in q:
                tokens = m.get("clobTokenIds")
                if tokens:
                    t_list = json.loads(tokens)
                    live_markets.append({
                        "name": m.get("question"),
                        "token_id": t_list[0], # YES Token
                        "end": m.get("endDate")
                    })
        
        # Сортировка по времени окончания (самые свежие сверху)
        live_markets.sort(key=lambda x: x['end'] if x['end'] else "")
        return live_markets
    except Exception as e:
        add_log(f"❌ Ошибка API: {e}")
        return []

# Интерфейс
st.title("⚡ Polymarket Pro: Прямое подключение")

col_left, col_right = st.columns([2, 1])

with col_left:
    pk = st.text_input("Private Key (0x...)", type="password")
    
    if st.button("🔄 ПОДКЛЮЧИТЬСЯ К ЖИВОЙ ЛЕНТЕ"):
        st.session_state.live_data = get_live_markets()

    if "live_data" in st.session_state and st.session_state.live_data:
        st.subheader("Актуальные рынки ETH")
        market_map = {m['name']: m['token_id'] for m in st.session_state.live_data}
        selected = st.selectbox("Выберите рынок:", list(market_map.keys()))
        token_id = market_map[selected]
        
        st.success(f"Выбран ID: `{token_id}`")

        # Настройки ордера
        c1, c2 = st.columns(2)
        price = c1.number_input("Цена покупки (0.01 - 0.99)", value=0.05)
        amount = c2.number_input("Кол-во акций", value=10)

        if st.button("🚀 ОТПРАВИТЬ ОРДЕР В КНИГУ"):
            if not pk:
                st.error("Введите ключ!")
            else:
                try:
                    add_log("🔐 Авторизация...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    # Инициализация API сессии
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    add_log(f"📤 Выставляю лимитку на {token_id}...")
                    order = OrderArgs(token_id=token_id, price=price, size=amount, side=BUY)
                    resp = client.post_order(client.create_order(order))
                    
                    if resp.get("success"):
                        add_log("🎯 ОРДЕР ПРИНЯТ БИРЖЕЙ")
                        st.balloons()
                    else:
                        add_log(f"⚠️ Отказ: {resp}")
                    st.json(resp)
                except Exception as e:
                    add_log(f"⛔ Ошибка: {e}")
    else:
        st.info("Нажмите кнопку подключения для поиска актуальных рынков ETH.")

with col_right:
    st.subheader("📟 Дебаг-консоль")
    log_area = st.empty()
    log_area.code("\n".join(st.session_state.logs[::-1]))
