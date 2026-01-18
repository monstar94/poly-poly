import streamlit as st
import requests
import json
import pytz
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Direct Bot", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

# --- ПРЯМАЯ ГЕНЕРАЦИЯ И ПОЛУЧЕНИЕ ДАННЫХ ---
def get_current_event_data(offset=0):
    # Устанавливаем время Нью-Йорка
    tz_et = pytz.timezone('US/Eastern')
    t = datetime.now(tz_et) + timedelta(hours=offset)
    
    # Генерируем слаг (как в ссылке)
    month = t.strftime("%B").lower()
    day = t.strftime("%d").lstrip('0')
    hour = t.strftime("%I").lstrip('0')
    am_pm = t.strftime("%p").lower()
    
    event_slug = f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"
    add_log(f"🛠️ Генерирую ссылку: https://polymarket.com/event/{event_slug}")
    
    try:
        # Запрос 1: Получаем само событие по его точному адресу
        e_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
        e_resp = requests.get(e_url).json()
        
        if e_resp and len(e_resp) > 0:
            event_id = e_resp[0]['id']
            add_log(f"✅ Событие найдено! ID: {event_id}")
            
            # Запрос 2: Берем ТОЛЬКО активные рынки внутри ЭТОГО события
            m_url = f"https://gamma-api.polymarket.com/markets?event_id={event_id}&active=true&closed=false"
            m_resp = requests.get(m_url).json()
            
            valid_markets = []
            for m in m_resp:
                # Берем только те, где в названии НЕТ слова "Biden" или "2020" (на всякий случай)
                if "Ethereum" in m.get("question", ""):
                    tokens = json.loads(m.get("clobTokenIds", "[]"))
                    if tokens:
                        valid_markets.append({"name": m.get("question"), "id": tokens[0]})
            
            return valid_markets, event_slug
        else:
            add_log(f"🔘 Рынок {event_slug} еще не создан на сервере.")
    except Exception as e:
        add_log(f"❌ Ошибка связи: {e}")
    
    return [], event_slug

# --- ИНТЕРФЕЙС ---
st.title("🛡️ Polymarket 100% ETH Bot")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    st.divider()
    st.info("Бот игнорирует старые рынки и ищет только ETH по прямой ссылке.")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📡 Подключение к часу")
    c1, c2 = st.columns(2)
    if c1.button("🕒 ТЕКУЩИЙ ЧАС", use_container_width=True):
        st.session_state.markets, st.session_state.slug = get_current_event_data(0)
    if c2.button("⏭️ СЛЕДУЮЩИЙ ЧАС", use_container_width=True):
        st.session_state.markets, st.session_state.slug = get_current_event_data(1)

    if "markets" in st.session_state and st.session_state.markets:
        st.success(f"Найдено актуальных рынков: {len(st.session_state.markets)}")
        
        m_map = {m['name']: m['id'] for m in st.session_state.markets}
        selected = st.selectbox("Выбери цену (Strike):", list(m_map.keys()))
        token_id = m_map[selected]
        
        st.divider()
        st.subheader("💰 Твоя ставка")
        p = st.number_input("Цена (например 0.05)", value=0.05)
        a = st.number_input("Кол-во", value=10)
        
        if st.button("🚀 ВЫСТАВИТЬ ОРДЕР", use_container_width=True):
            if not pk: st.error("Вставь Private Key!")
            else:
                try:
                    add_log("🔐 Авторизация...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    order = OrderArgs(token_id=token_id, price=p, size=a, side=BUY)
                    resp = client.post_order(client.create_order(order))
                    add_log(f"📡 Ответ: {resp}")
                    if resp.get("success"): st.balloons()
                    st.json(resp)
                except Exception as e:
                    add_log(f"❌ Ошибка: {e}")
    else:
        st.info("Нажми кнопку. Бот проверит именно ETH-ссылку текущего часа.")

with col2:
    st.subheader("📟 Дебаг-лог")
    st.code("\n".join(st.session_state.logs[::-1]))
