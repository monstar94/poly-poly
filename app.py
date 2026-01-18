import streamlit as st
import requests
import json
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Константы
BUY = "BUY"
st.set_page_config(page_title="Polymarket Debug Pro", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.logs) > 20: st.session_state.logs.pop(0)

def get_live_markets():
    add_log("📡 Запрос к Gamma API (Active Markets)...")
    try:
        # Увеличиваем лимит и убираем жесткие фильтры для теста
        url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100"
        resp = requests.get(url).json()
        
        add_log(f"📦 API вернуло {len(resp)} рынков всего. Фильтруем ETH...")
        
        live_markets = []
        for m in resp:
            q = m.get("question", "")
            # Ищем любое упоминание Ethereum или ETH
            if "eth" in q.lower():
                tokens = m.get("clobTokenIds")
                if tokens:
                    try:
                        t_list = json.loads(tokens)
                        if t_list:
                            live_markets.append({
                                "name": q,
                                "token_id": t_list[0],
                                "end": m.get("endDate")
                            })
                    except:
                        continue
        
        add_log(f"✅ Найдено {len(live_markets)} подходящих рынков ETH.")
        return live_markets
    except Exception as e:
        add_log(f"❌ Ошибка API: {str(e)}")
        return []

# Интерфейс
st.title("⚡ Polymarket Pro: Debug Mode")

col_left, col_right = st.columns([2, 1])

with col_left:
    pk = st.text_input("Private Key (0x...)", type="password")
    
    if st.button("🔄 ОБНОВИТЬ И НАЙТИ РЫНКИ"):
        found = get_live_markets()
        st.session_state.live_data = found
        if not found:
            st.warning("Рынки не найдены. Попробуйте нажать еще раз через 10 секунд.")

    if "live_data" in st.session_state and st.session_state.live_data:
        market_map = {m['name']: m['token_id'] for m in st.session_state.live_data}
        selected = st.selectbox("Выберите рынок из списка:", list(market_map.keys()))
        token_id = market_map[selected]
        
        st.success(f"Выбран Token ID: `{token_id}`")

        c1, c2 = st.columns(2)
        price = c1.number_input("Цена (0.01 - 0.99)", value=0.05, step=0.01)
        amount = c2.number_input("Кол-во акций", value=10.0, step=1.0)

        if st.button("🚀 ОТПРАВИТЬ ОРДЕР"):
            if not pk:
                st.error("Введите Private Key!")
            else:
                try:
                    add_log("🔐 Авторизация и создание сессии...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    add_log(f"📤 Отправка лимитки на {token_id}...")
                    order = OrderArgs(token_id=token_id, price=price, size=amount, side=BUY)
                    resp = client.post_order(client.create_order(order))
                    
                    if resp.get("success") or resp.get("orderID"):
                        add_log("🎯 УСПЕХ: Ордер принят!")
                        st.balloons()
                    else:
                        add_log(f"⚠️ Ответ биржи: {resp}")
                    st.json(resp)
                except Exception as e:
                    add_log(f"⛔ Ошибка: {str(e)}")
                    st.error(f"Детали ошибки: {e}")

with col_right:
    st.subheader("📟 Дебаг-консоль")
    if st.button("Очистить логи"):
        st.session_state.logs = []
    
    log_text = "\n".join(st.session_state.logs[::-1])
    st.code(log_text if log_text else "Логи появятся здесь...")
