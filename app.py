import streamlit as st
import requests
import json
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Hourly Bot", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.logs) > 15: st.session_state.logs.pop(0)

# --- ФУНКЦИЯ ПОЛУЧЕНИЯ РЫНКОВ ПО SLUG ---
def get_markets_by_slug(slug):
    add_log(f"🔗 Обработка события: {slug}")
    try:
        # 1. Получаем ID события по его слагу
        event_url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        e_resp = requests.get(event_url).json()
        
        if not e_resp or "error" in e_resp:
            add_log("❌ Событие не найдено. Проверьте правильность ссылки/слага.")
            return []
        
        event_id = e_resp[0].get("id")
        add_log(f"🆔 Event ID получен: {event_id}")

        # 2. Получаем все активные рынки внутри этого события
        markets_url = f"https://gamma-api.polymarket.com/markets?event_id={event_id}&active=true"
        m_resp = requests.get(markets_url).json()
        
        found = []
        for m in m_resp:
            tokens = m.get("clobTokenIds")
            if tokens:
                t_list = json.loads(tokens)
                found.append({
                    "name": m.get("question"),
                    "token_id": t_list[0], # YES Token
                    "end": m.get("endDate")
                })
        
        add_log(f"✅ Найдено вложенных рынков: {len(found)}")
        return found
    except Exception as e:
        add_log(f"❌ Ошибка API: {str(e)}")
        return []

# --- ИНТЕРФЕЙС ---
st.title("🚀 Polymarket Hourly Pulse Bot")

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("1. Настройка подключения")
    pk = st.text_input("Вставьте Private Key (0x...)", type="password")
    
    # Авто-генерация слага на основе текущего времени (ET)
    # Пример: ethereum-up-or-down-january-18-3am-et (учитывая текущую дату)
    current_slug = st.text_input("Slug события (из ссылки)", value="ethereum-up-or-down-january-17-9pm-et")
    
    if st.button("🔄 ЗАГРУЗИТЬ РЫНКИ ЧАСА"):
        st.session_state.active_markets = get_markets_by_slug(current_slug)

    if "active_markets" in st.session_state and st.session_state.active_markets:
        st.subheader("2. Выбор интервала")
        market_options = {m['name']: m['token_id'] for m in st.session_state.active_markets}
        selected_name = st.selectbox("Какой 15-минутный интервал торгуем?", list(market_options.keys()))
        token_id = market_options[selected_name]
        
        st.info(f"Выбран Token ID: `{token_id}`")

        st.subheader("3. Параметры ордера")
        c1, c2 = st.columns(2)
        price = c1.number_input("Цена (отскок, например 0.05)", value=0.05, step=0.01)
        amount = c2.number_input("Кол-во акций", value=10, step=1)

        if st.button("🚀 ВЫСТАВИТЬ ОРДЕР", use_container_width=True):
            if not pk:
                st.error("Введите ключ в поле выше!")
            else:
                try:
                    add_log("🔐 Авторизация...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    
                    add_log(f"📡 Отправка лимитки на {token_id}...")
                    order = OrderArgs(token_id=token_id, price=price, size=amount, side=BUY)
                    resp = client.post_order(client.create_order(order))
                    
                    if resp.get("success"):
                        add_log("🎯 ОРДЕР В СТАКАНЕ!")
                        st.balloons()
                    else:
                        add_log(f"⚠️ Ответ биржи: {resp}")
                    st.json(resp)
                except Exception as e:
                    add_log(f"⛔ Ошибка: {str(e)}")
    else:
        st.warning("Список рынков пуст. Вставьте актуальный slug и нажмите кнопку загрузки.")

with col_right:
    st.subheader("📟 Консоль логов")
    if st.button("Очистить"):
        st.session_state.logs = []
    
    log_text = "\n".join(st.session_state.logs[::-1])
    st.code(log_text if log_text else "Тут будет виден процесс...")
