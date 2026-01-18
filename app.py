import streamlit as st
import requests
import json
import pytz
import time
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

st.set_page_config(page_title="Polymarket Live Terminal", layout="wide")

if "logs" not in st.session_state: st.session_state.logs = []
if "found_m" not in st.session_state: st.session_state.found_m = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 10: st.session_state.logs.pop(0)

def get_live_orderbook(token_id):
    try:
        # Запрос к CLOB API для получения стакана
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        resp = requests.get(url, timeout=5).json()
        bids = resp.get("bids", [])
        asks = resp.get("asks", [])
        mid = (float(bids[0]['price']) + float(asks[0]['price'])) / 2 if bids and asks else 0
        return bids[:5], asks[:5], mid
    except:
        return [], [], 0

def get_event_data(offset=0):
    # Устанавливаем актуальное время ET (Нью-Йорк)
    tz_et = pytz.timezone('US/Eastern')
    t = datetime.now(tz_et) + timedelta(hours=offset)
    
    # Генерируем актуальный слаг (сейчас это уже 18 января)
    month = t.strftime("%B").lower()
    day = t.strftime("%d").lstrip('0')
    hour = t.strftime("%I").lstrip('0')
    am_pm = t.strftime("%p").lower()
    
    event_slug = f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"
    add_log(f"🔎 Проверка АКТИВНОГО рынка: {event_slug}")
    
    try:
        e_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
        e_resp = requests.get(e_url).json()
        
        if e_resp and len(e_resp) > 0:
            event_id = e_resp[0]['id']
            # Запрашиваем только активные и незакрытые рынки
            m_url = f"https://gamma-api.polymarket.com/markets?event_id={event_id}&active=true&closed=false"
            m_resp = requests.get(m_url).json()
            
            valid = []
            for m in m_resp:
                if "Ethereum" in m.get("question", ""):
                    tokens = json.loads(m.get("clobTokenIds", "[]"))
                    if tokens:
                        valid.append({"name": m.get("question"), "id": tokens[0]})
            return valid
        else:
            add_log(f"🔘 Рынок {event_slug} еще не открыт.")
    except Exception as e:
        add_log(f"❌ Ошибка: {e}")
    return []

st.title("🎛️ Polymarket Real-Time Terminal")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    auto_refresh = st.checkbox("Авто-обновление стакана", value=True)

col_main, col_side = st.columns([2, 1])

with col_main:
    c1, c2 = st.columns(2)
    # Кнопки теперь ищут рынки за СЕГОДНЯ (18 января)
    if c1.button("🕒 ТЕКУЩИЙ ЧАС (Live)", use_container_width=True):
        st.session_state.found_m = get_event_data(0)
    if c2.button("⏭️ СЛЕДУЮЩИЙ ЧАС", use_container_width=True):
        st.session_state.found_m = get_event_data(1)

    if st.session_state.found_m:
        m_options = {m['name']: m['id'] for m in st.session_state.found_m}
        selected_name = st.selectbox("🎯 Выбери активный страйк:", list(m_options.keys()))
        token_id = m_options[selected_name]

        st.subheader("📊 Живой стакан (Order Book)")
        bids, asks, mid = get_live_orderbook(token_id)
        
        if mid > 0:
            st.metric("Средняя цена", f"{mid:.4f}")
            o_c1, o_c2 = st.columns(2)
            with o_c1:
                st.write("🟢 Bids")
                st.dataframe(bids, use_container_width=True)
            with o_c2:
                st.write("🔴 Asks")
                st.dataframe(asks, use_container_width=True)
        else:
            st.warning("⚠️ Стакан пуст. Этот рынок уже закрыт или еще не начат.")

        st.divider()
        f1, f2 = st.columns(2)
        price = f1.number_input("Цена", value=0.05)
        amount = f2.number_input("Кол-во", value=10)
        if st.button("🚀 КУПИТЬ", use_container_width=True):
            # Тут код отправки ордера через ClobClient
            add_log(f"📡 Отправка ордера на {token_id}...")
    else:
        st.info("Нажми 'Текущий час'. Если пусто — значит рынок на этот час еще не создан.")

with col_side:
    st.subheader("📟 Логи")
    st.code("\n".join(st.session_state.logs[::-1]))
    if auto_refresh and st.session_state.found_m:
        time.sleep(5)
        st.rerun()
