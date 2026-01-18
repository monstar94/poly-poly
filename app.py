import streamlit as st
import requests
import json
import pytz
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- КОНСТАНТЫ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Auto-Pilot", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 10: st.session_state.logs.pop(0)

# --- ГЕНЕРАТОР СЛАГА (АДРЕСА РЫНКА) ---
def get_auto_market(offset_hours=0):
    # 1. Переходим в часовой пояс Нью-Йорка (ET)
    tz_et = pytz.timezone('US/Eastern')
    target_time = datetime.now(tz_et) + timedelta(hours=offset_hours)
    
    # 2. Форматируем дату (Polymarket любит формат: january-18-2026-4am-et)
    # Важно: убираем ведущий ноль у часов через lstrip('0')
    month = target_time.strftime("%B").lower()
    day = target_time.strftime("%d").lstrip('0')
    year = target_time.strftime("%Y")
    hour_raw = target_time.strftime("%I").lstrip('0')
    am_pm = target_time.strftime("%p").lower()
    
    slug = f"ethereum-price-at-{month}-{day}-{year}-{hour_raw}{am_pm}-et"
    add_log(f"🔗 Сгенерирована ссылка: {slug}")
    
    # 3. Проверяем через API, существует ли такой рынок
    api_url = f"https://gamma-api.polymarket.com/markets?slug={slug}"
    try:
        resp = requests.get(api_url).json()
        if resp and isinstance(resp, list):
            m = resp[0]
            tokens = json.loads(m.get("clobTokenIds"))
            return {
                "name": m.get("question"),
                "token_id": tokens[0],
                "slug": slug,
                "status": "Active" if m.get("active") else "Inactive"
            }
    except Exception as e:
        add_log(f"⚠️ Рынок еще не создан или ошибка: {e}")
    return None

# --- ИНТЕРФЕЙС ---
st.title("🤖 Polymarket Smart Auto-Bot")

with st.sidebar:
    st.header("Настройки")
    pk = st.text_input("Private Key", type="password")
    st.info("Бот сам вычисляет текущий и следующий час по времени ET.")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🛠️ Управление рынком")
    
    c1, c2 = st.columns(2)
    if c1.button("🕒 Найти ТЕКУЩИЙ час", use_container_width=True):
        st.session_state.m_data = get_auto_market(0)
    if c2.button("⏭️ Найти СЛЕДУЮЩИЙ час", use_container_width=True):
        st.session_state.m_data = get_auto_market(1)

    if "m_data" in st.session_state and st.session_state.m_data:
        m = st.session_state.m_data
        st.success(f"**Рынок найден:** {m['name']}")
        st.write(f"**Token ID:** `{m['token_id']}`")
        
        st.divider()
        st.subheader("💰 Торговля")
        price = st.number_input("Цена лимитки (отскок)", value=0.05, step=0.01)
        amount = st.number_input("Кол-во акций", value=10.0, step=1.0)
        
        if st.button("🚀 ВЫСТАВИТЬ ОРДЕР", use_container_width=True):
            if not pk:
                st.error("Введите Private Key!")
            else:
                try:
                    add_log("🔐 Авторизация...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    order = OrderArgs(token_id=m['token_id'], price=price, size=amount, side=BUY)
                    resp = client.post_order(client.create_order(order))
                    
                    if resp.get("success"):
                        add_log(f"🎯 ОРДЕР ВЫСТАВЛЕН: {m['slug']}")
                        st.balloons()
                    else:
                        add_log(f"❌ Ошибка: {resp}")
                    st.json(resp)
                except Exception as e:
                    add_log(f"⛔ Ошибка: {e}")
    else:
        st.warning("Нажми кнопку, чтобы бот сгенерировал ссылку и нашел рынок.")

with col2:
    st.subheader("📟 Логи")
    if st.button("Очистить"): st.session_state.logs = []
    st.code("\n".join(st.session_state.logs[::-1]))
