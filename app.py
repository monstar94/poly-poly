import streamlit as st
import requests
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- КОНСТАНТЫ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Manual Search Bot", layout="wide")

# --- СИСТЕМА ЛОГОВ ---
if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

# --- УЛУЧШЕННЫЙ ПОИСК ---
def search_polymarket(query):
    add_log(f"🔎 Ищу рынки по запросу: '{query}'...")
    try:
        # Используем эндпоинт поиска Gamma API
        url = f"https://gamma-api.polymarket.com/public-search?q={query}"
        resp = requests.get(url).json()
        
        results = []
        # API возвращает события (events), в каждом из которых есть рынки (markets)
        if "events" in resp:
            for event in resp["events"]:
                for market in event.get("markets", []):
                    # Берем только активные рынки
                    if market.get("active") and not market.get("closed"):
                        tokens = market.get("clobTokenIds")
                        if tokens:
                            # Парсим ID токена (обычно первый - это YES)
                            import json
                            token_list = json.loads(tokens)
                            results.append({
                                "name": market["question"],
                                "id": token_list[0],
                                "ends": market.get("endDate")
                            })
        return results
    except Exception as e:
        add_log(f"❌ Ошибка поиска: {e}")
        return []

# --- ИНТЕРФЕЙС ---
st.title("🎛️ Polymarket: Ручной поиск и Торговля")

col_left, col_right = st.columns([2, 1])

with col_left:
    pk = st.text_input("1. Введите Private Key (0x...)", type="password")
    search_query = st.text_input("2. Что ищем? (например: ethereum или btc)", value="ethereum")
    
    if st.button("Найти рынки"):
        st.session_state.found_markets = search_polymarket(search_query)

    if "found_markets" in st.session_state and st.session_state.found_markets:
        st.write(f"Найдено активных рынков: {len(st.session_state.found_markets)}")
        
        # Выбор рынка из списка найденных
        market_options = {m['name']: m['id'] for m in st.session_state.found_markets}
        selected_market_name = st.selectbox("3. Выберите конкретный рынок:", list(market_options.keys()))
        selected_token_id = market_options[selected_market_name]
        
        st.code(f"Выбран Token ID: {selected_token_id}")

        # Настройки ордера
        c1, c2 = st.columns(2)
        price = c1.number_input("Цена (от 0.01 до 0.99)", value=0.05, step=0.01)
        amount = c2.number_input("Кол-во акций", value=10, step=1)

        if st.button("🚀 ВЫСТАВИТЬ ЛИМИТКУ"):
            if not pk:
                st.error("Сначала введите Private Key!")
            else:
                try:
                    add_log("⚙️ Авторизация...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    add_log(f"📡 Отправка ордера на {selected_token_id}...")
                    order = OrderArgs(token_id=selected_token_id, price=price, size=amount, side=BUY)
                    resp = client.post_order(client.create_order(order))
                    
                    if resp.get("success"):
                        add_log("🎯 УСПЕХ: Ордер в стакане!")
                        st.balloons()
                    else:
                        add_log(f"⚠️ Ошибка: {resp.get('error')}")
                    st.json(resp)
                except Exception as e:
                    add_log(f"⛔ Ошибка: {e}")
    elif "found_markets" in st.session_state:
        st.warning("Ничего не найдено. Попробуйте другое слово.")

with col_right:
    st.subheader("📟 Консоль")
    log_area = st.empty()
    log_area.code("\n".join(st.session_state.logs[::-1]))
