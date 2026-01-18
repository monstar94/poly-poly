import streamlit as st
import requests
import json
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Multi-Interval Bot", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

# --- ГИБКИЙ ПОИСК РЫНКОВ ---
def get_all_eth_price_markets():
    add_log("📡 Сканирование всех рынков ETH Price...")
    try:
        # Запрашиваем активные рынки без жестких фильтров по времени
        url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100"
        resp = requests.get(url).json()
        
        found = []
        for m in resp:
            title = m.get("question", "")
            # Ищем 'Ethereum' и 'Price', исключая политический мусор 2020 года
            if "Ethereum" in title and "Price" in title:
                # Фильтр по актуальному году (2026)
                if "2026" in title or "January" in title:
                    tokens = m.get("clobTokenIds")
                    if tokens:
                        t_list = json.loads(tokens)
                        found.append({
                            "name": title,
                            "token_id": t_list[0], # YES Token
                            "end": m.get("endDate")
                        })
        
        # Сортировка: самые близкие к завершению — сверху
        found.sort(key=lambda x: x['end'] if x['end'] else "")
        return found
    except Exception as e:
        add_log(f"❌ Ошибка API: {str(e)}")
        return []

# --- ИНТЕРФЕЙС ---
st.title("📊 Polymarket Strategy Bot (Universal)")

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("1. Авторизация")
    pk = st.text_input("Вставьте Private Key (0x...)", type="password")
    
    if st.button("🔄 ОБНОВИТЬ СПИСОК РЫНКОВ"):
        st.session_state.current_markets = get_all_eth_price_markets()

    if "current_markets" in st.session_state and st.session_state.current_markets:
        st.subheader("2. Доступные интервалы")
        market_map = {m['name']: m['token_id'] for m in st.session_state.current_markets}
        selected_name = st.selectbox("Выберите активный рынок:", list(market_map.keys()))
        token_id = market_map[selected_name]
        
        st.success(f"Выбран: {selected_name}")
        st.code(f"ID: {token_id}")

        st.subheader("3. Управление ордером")
        c1, c2 = st.columns(2)
        price = c1.number_input("Цена (отскок 0.05)", value=0.05, step=0.01)
        amount = c2.number_input("Кол-во акций", value=10.0, step=1.0)

        if st.button("🚀 ВЫСТАВИТЬ ЛИМИТКУ", use_container_width=True):
            if not pk:
                st.error("Введите Private Key!")
            else:
                try:
                    add_log("🔐 Подключение к Polymarket...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    add_log(f"📡 Отправка ордера на {token_id}...")
                    order = OrderArgs(token_id=token_id, price=price, size=amount, side=BUY)
                    resp = client.post_order(client.create_order(order))
                    
                    if resp.get("success"):
                        add_log("🎯 УСПЕХ: Ордер активен!")
                        st.balloons()
                    else:
                        add_log(f"⚠️ Ошибка биржи: {resp}")
                    st.json(resp)
                except Exception as e:
                    add_log(f"⛔ Критическая ошибка: {str(e)}")
    else:
        st.info("Нажмите кнопку выше для поиска рынков.")

with col_right:
    st.subheader("📟 Консоль")
    if st.button("Очистить"): st.session_state.logs = []
    log_text = "\n".join(st.session_state.logs[::-1])
    st.code(log_text if log_text else "Логи появятся здесь...")
