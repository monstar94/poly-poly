import streamlit as st
import requests
import json
import time
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Polymarket Link Terminal", layout="wide")

if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 10: st.session_state.logs.pop(0)

# --- ФУНКЦИЯ ПОЛУЧЕНИЯ ДАННЫХ ИЗ API ---
def get_market_data_by_url(url):
    try:
        # Извлекаем слаг из ссылки (последняя часть URL)
        slug = url.split('/')[-1]
        add_log(f"🔎 Поиск данных для: {slug}")
        
        # Запрос к Gamma API для получения ID токена
        api_url = f"https://gamma-api.polymarket.com/markets?slug={slug}"
        resp = requests.get(api_url, timeout=5).json()
        
        if resp and isinstance(resp, list) and len(resp) > 0:
            m = resp[0]
            tokens = json.loads(m.get("clobTokenIds", "[]"))
            if tokens:
                return {
                    "name": m.get("question"),
                    "token_id": tokens[0], # YES Token
                    "status": "Active" if m.get("active") and not m.get("closed") else "Closed"
                }
        return None
    except Exception as e:
        add_log(f"❌ Ошибка парсинга: {e}")
        return None

# --- ПОЛУЧЕНИЕ СТАКАНА (ORDERBOOK) ---
def get_live_orderbook(token_id):
    try:
        # Прямое подключение к CLOB API
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        resp = requests.get(url, timeout=5).json()
        bids = resp.get("bids", [])
        asks = resp.get("asks", [])
        
        mid_price = 0
        if bids and asks:
            mid_price = (float(bids[0]['price']) + float(asks[0]['price'])) / 2
        return bids[:5], asks[:5], mid_price
    except:
        return [], [], 0

# --- ИНТЕРФЕЙС ---
st.title("🎛️ Polymarket Link Terminal")

with st.sidebar:
    pk = st.text_input("Private Key (0x...)", type="password")
    st.divider()
    auto_refresh = st.checkbox("Авто-обновление стакана", value=True)
    st.info("Вставь прямую ссылку на исход (рынок), чтобы увидеть стакан.")

col_main, col_side = st.columns([2, 1])

with col_main:
    st.subheader("1. Подключение по ссылке")
    market_url = st.text_input(
        "Вставь ссылку на рынок:", 
        placeholder="https://polymarket.com/market/ethereum-price-at-january-18-2026-4am-et-above-3300"
    )

    if market_url:
        m_data = get_market_data_by_url(market_url)
        
        if m_data:
            st.success(f"✅ Подключено: {m_data['name']}")
            st.write(f"**Статус:** {m_data['status']} | **ID:** `{m_data['token_id']}`")
            
            # --- ОТОБРАЖЕНИЕ СТАКАНА ---
            st.subheader("📊 Живой стакан (CLOB API)")
            bids, asks, mid = get_live_orderbook(m_data['token_id'])
            
            if mid > 0:
                st.metric("Текущая цена (Midpoint)", f"${mid:.4f}")
                
                o_c1, o_c2 = st.columns(2)
                with o_c1:
                    st.write("🟢 **Bids (Покупка)**")
                    st.dataframe(bids, use_container_width=True)
                with o_c2:
                    st.write("🔴 **Asks (Продажа)**")
                    st.dataframe(asks, use_container_width=True)
            else:
                st.warning("⚠️ Стакан пуст. Либо нет заявок, либо рынок закрыт.")

            # --- ФОРМА ОРДЕРА ---
            st.divider()
            st.subheader("🚀 Быстрая торговля")
            f1, f2 = st.columns(2)
            p = f1.number_input("Цена", value=0.05, step=0.01)
            a = f2.number_input("Кол-во", value=10, step=1)
            
            if st.button("ВЫСТАВИТЬ ЛИМИТКУ", use_container_width=True):
                if not pk: st.error("Введи ключ!")
                else:
                    try:
                        add_log("🔐 Авторизация...")
                        client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                        client.set_api_creds(client.create_or_derive_api_creds())
                        
                        order = OrderArgs(token_id=m_data['token_id'], price=p, size=a, side="BUY")
                        resp = client.post_order(client.create_order(order))
                        add_log(f"📡 Ответ: {resp}")
                        if resp.get("success"): st.balloons()
                    except Exception as e:
                        add_log(f"❌ Ошибка: {e}")
        else:
            st.error("Не удалось найти рынок по этой ссылке. Убедись, что это ссылка на конкретный исход.")

with col_side:
    st.subheader("📟 Логи")
    if st.button("Очистить"): st.session_state.logs = []
    st.code("\n".join(st.session_state.logs[::-1]))
    
    if auto_refresh and market_url and 'm_data' in locals() and m_data:
        time.sleep(5)
        st.rerun()
