import streamlit as st
import requests
import json
import pytz
import time
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Polymarket Up/Down Bot", layout="wide")

if "logs" not in st.session_state: st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 10: st.session_state.logs.pop(0)

# --- ПОЛУЧЕНИЕ СТАКАНА ---
def get_live_orderbook(token_id):
    try:
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        resp = requests.get(url, timeout=5).json()
        bids = resp.get("bids", [])
        asks = resp.get("asks", [])
        mid = (float(bids[0]['price']) + float(asks[0]['price'])) / 2 if bids and asks else 0
        return bids[:5], asks[:5], mid
    except:
        return [], [], 0

# --- ПОИСК ТЕКУЩЕГО UP/DOWN ---
def get_up_down_market(offset=0):
    tz_et = pytz.timezone('US/Eastern')
    t = datetime.now(tz_et) + timedelta(hours=offset)
    
    # Формат: ethereum-up-or-down-january-18-4am-et
    month = t.strftime("%B").lower()
    day = t.strftime("%d").lstrip('0')
    hour = t.strftime("%I").lstrip('0')
    am_pm = t.strftime("%p").lower()
    
    event_slug = f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"
    add_log(f"🔎 Ищу рынок: {event_slug}")
    
    try:
        # Находим событие
        e_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
        e_resp = requests.get(e_url).json()
        
        if e_resp and len(e_resp) > 0:
            # В Up/Down рынке обычно один главный маркет
            m_url = f"https://gamma-api.polymarket.com/markets?event_id={e_resp[0]['id']}"
            m_resp = requests.get(m_url).json()
            
            if m_resp:
                m = m_resp[0] # Берем первый (основной) рынок
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                return {
                    "question": m.get("question"),
                    "yes_token": tokens[0],
                    "no_token": tokens[1],
                    "slug": event_slug
                }
    except Exception as e:
        add_log(f"❌ Ошибка поиска: {e}")
    return None

# --- ИНТЕРФЕЙС ---
st.title("📈 ETH Up/Down Hourly Bot")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    auto_refresh = st.checkbox("Авто-обновление стакана", value=True)

col_main, col_side = st.columns([2, 1])

with col_main:
    # Кнопки поиска
    c1, c2 = st.columns(2)
    if c1.button("🕒 ТЕКУЩИЙ ЧАС", use_container_width=True):
        st.session_state.market = get_up_down_market(0)
    if c2.button("⏭️ СЛЕДУЮЩИЙ ЧАС", use_container_width=True):
        st.session_state.market = get_up_down_market(1)

    if "market" in st.session_state and st.session_state.market:
        m = st.session_state.market
        st.subheader(f"🎯 {m['question']}")
        
        # Выбор стороны
        side = st.radio("На что ставим?", ["YES (Вверх)", "NO (Вниз)"], horizontal=True)
        active_token = m['yes_token'] if "YES" in side else m['no_token']
        
        # СТАКАН
        st.divider()
        st.subheader("📊 Живой стакан")
        bids, asks, mid = get_live_orderbook(active_token)
        
        if mid > 0:
            st.metric(f"Цена {side}", f"${mid:.4f}")
            o1, o2 = st.columns(2)
            with o1:
                st.write("🟢 Покупатели (Bids)")
                st.dataframe(bids, use_container_width=True)
            with o2:
                st.write("🔴 Продавцы (Asks)")
                st.dataframe(asks, use_container_width=True)
        else:
            st.warning("Стакан пуст или рынок еще не открыт.")

        # ТОРГОВЛЯ
        st.divider()
        f1, f2 = st.columns(2)
        p = f1.number_input("Твоя лимитка (цена)", value=0.05, step=0.01)
        a = f2.number_input("Кол-во акций", value=10, step=1)
        
        if st.button("🚀 ВЫСТАВИТЬ ОРДЕР", use_container_width=True):
            if not pk: st.error("Введи ключ!")
            else:
                try:
                    add_log("🔐 Подключение к CLOB...")
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    order = OrderArgs(token_id=active_token, price=p, size=a, side="BUY")
                    resp = client.post_order(client.create_order(order))
                    add_log(f"📡 Ответ: {resp}")
                    if resp.get("success"): st.balloons()
                except Exception as e:
                    add_log(f"❌ Ошибка: {e}")
    else:
        st.info("Нажми кнопку часа, чтобы подключиться к рынку.")

with col_side:
    st.subheader("📟 Логи")
    st.code("\n".join(st.session_state.logs[::-1]))
    if auto_refresh and "market" in st.session_state:
        time.sleep(5)
        st.rerun()
