import streamlit as st
import requests
import json
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Link Bot", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

from datetime import datetime

# --- ФУНКЦИЯ ПОЛУЧЕНИЯ ДАННЫХ ПО ССЫЛКЕ ---
def get_market_data_by_url(url):
    try:
        # Извлекаем 'slug' из ссылки (часть после /event/ или /market/)
        slug = url.split('/')[-1]
        add_log(f"🔗 Анализ ссылки, слаг: {slug}")
        
        # Запрос к Gamma API для получения ID токена
        api_url = f"https://gamma-api.polymarket.com/markets?slug={slug}"
        resp = requests.get(api_url).json()
        
        if resp and isinstance(resp, list):
            m = resp[0]
            tokens = json.loads(m.get("clobTokenIds"))
            return {
                "name": m.get("question"),
                "token_id": tokens[0], # YES Token
                "active": m.get("active")
            }
        return None
    except Exception as e:
        add_log(f"❌ Ошибка парсинга ссылки: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("🔗 Polymarket Direct Link Trader")

col_main, col_side = st.columns([2, 1])

with col_main:
    st.subheader("1. Доступы")
    pk = st.text_input("Вставьте Private Key (0x...)", type="password")
    
    st.subheader("2. Рынок")
    market_url = st.text_input("Вставьте ссылку на рынок с Polymarket:", 
                               placeholder="https://polymarket.com/market/ethereum-price-at-january-18-2026-4am-et")
    
    if market_url:
        data = get_market_data_by_url(market_url)
        if data:
            st.success(f"✅ Рынок найден: {data['name']}")
            st.info(f"Token ID: `{data['token_id']}`")
            
            st.subheader("3. Параметры ордера")
            c1, c2 = st.columns(2)
            price = c1.number_input("Цена (лимитка)", value=0.05, step=0.01)
            amount = c2.number_input("Количество акций", value=10.0, step=1.0)
            
            if st.button("🚀 ВЫСТАВИТЬ ОРДЕР", use_container_width=True):
                if not pk:
                    st.error("Забыли ввести Private Key!")
                else:
                    try:
                        add_log("🔐 Авторизация...")
                        client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                        client.set_api_creds(client.create_or_derive_api_creds())
                        
                        add_log(f"📡 Отправка ордера на {data['token_id']}...")
                        order = OrderArgs(token_id=data['token_id'], price=price, size=amount, side=BUY)
                        resp = client.post_order(client.create_order(order))
                        
                        if resp.get("success"):
                            add_log("🎯 УСПЕХ: Ордер принят!")
                            st.balloons()
                        else:
                            add_log(f"⚠️ Биржа ответила: {resp}")
                        st.json(resp)
                    except Exception as e:
                        add_log(f"⛔ Ошибка: {e}")
        else:
            st.error("Не удалось найти рынок по этой ссылке. Убедитесь, что это прямая ссылка на исход.")

with col_side:
    st.subheader("📟 Логи")
    if st.button("Очистить"): st.session_state.logs = []
    st.code("\n".join(st.session_state.logs[::-1]))
