import streamlit as st
import requests
import json
import time
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Polymarket Up/Down Terminal", layout="wide")

if "logs" not in st.session_state: st.session_state.logs = []

def add_log(message):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    if len(st.session_state.logs) > 10: st.session_state.logs.pop(0)

# --- ПОЛУЧЕНИЕ СТАКАНА ---
def get_live_orderbook(token_id):
    try:
        url = f"https://clob.polymarket.com/book?token_id={token_id}"
        resp = requests.get(url, timeout=5).json()
        bids, asks = resp.get("bids", []), resp.get("asks", [])
        mid = (float(bids[0]['price']) + float(asks[0]['price'])) / 2 if bids and asks else 0
        return bids[:5], asks[:5], mid
    except:
        return [], [], 0

# --- ИЗВЛЕЧЕНИЕ ДАННЫХ ИЗ ССЫЛКИ ---
def get_market_from_slug(url):
    try:
        # Извлекаем последнюю часть ссылки (slug)
        slug = url.strip().split('/')[-1]
        add_log(f"🔎 Подключение к событию: {slug}")
        
        # Получаем событие через API
        e_url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        e_resp = requests.get(e_url).json()
        
        if e_resp and len(e_resp) > 0:
            event_id = e_resp[0]['id']
            # Берем только АКТИВНЫЕ рынки внутри этого конкретного события
            m_url = f"https://gamma-api.polymarket.com/markets?event_id={event_id}&active=true"
            m_resp = requests.get(m_url).json()
            
            if m_resp:
                # Фильтруем, чтобы найти основной рынок Ethereum
                m = next((item for item in m_resp if "Ethereum" in item.get("question", "")), m_resp[0])
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                return {
                    "question": m.get("question"),
                    "yes_token": tokens[0],
                    "no_token": tokens[1],
                    "slug": slug
                }
        add_log("🔘 Событие не найдено или еще не активно.")
    except Exception as e:
        add_log(f"❌ Ошибка API: {e}")
    return None

# --- ИНТЕРФЕЙС ---
st.title("📈 Polymarket Up/Down Hourly")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    auto_refresh = st.checkbox("Авто-обновление стакана", value=True)
    st.info("Вставь ссылку на Event, чтобы бот подцепил стакан.")

# ПОЛЕ ВВОДА ССЫЛКИ
input_url = st.text_input(
    "Вставь ссылку на событие:", 
    value="https://polymarket.com/event/ethereum-up-or-down-january-17-9pm-et"
)

if input_url:
    m = get_market_from_slug(input_url)
    
    if m:
        col_main, col_side = st.columns([2, 1])
        
        with col_main:
            st.success(f"🎯 Активный рынок: {m['question']}")
            
            # Выбор токена (Up или Down)
            choice = st.radio("Выбери исход:", ["UP (YES)", "DOWN (NO)"], horizontal=True)
            token_to_trade = m['yes_token'] if "UP" in choice else m['no_token']
            
            # СТАКАН
            st.subheader(f"📊 Стакан для {choice}")
            bids, asks, mid = get_live_orderbook(token_to_trade)
            
            if mid > 0:
                st.metric("Средняя цена", f"{mid:.4f}")
                o1, o2 = st.columns(2)
                with o1:
                    st.write("🟢 Bids (Покупка)")
                    st.dataframe(bids, use_container_width=True)
                with o2:
                    st.write("🔴 Asks (Продажа)")
                    st.dataframe(asks, use_container_width=True)
            else:
                st.warning("⚠️ Стакан пуст. Возможно, торги по этому часу еще не начались или уже завершены.")

            # ТОРГОВЛЯ
            st.divider()
            f1, f2 = st.columns(2)
            price = f1.number_input("Твоя цена", value=0.05)
            amount = f2.number_input("Кол-во акций", value=10)
            
            if st.button("🚀 ОТПРАВИТЬ ОРДЕР", use_container_width=True):
                if not pk: st.error("Введи Private Key!")
                else:
                    try:
                        add_log("🔐 Авторизация...")
                        client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                        client.set_api_creds(client.create_or_derive_api_creds())
                        order = OrderArgs(token_id=token_to_trade, price=price, size=amount, side="BUY")
                        resp = client.post_order(client.create_order(order))
                        add_log(f"📡 Ответ: {resp}")
                        if resp.get("success"): st.balloons()
                    except Exception as e:
                        add_log(f"❌ Ошибка: {e}")

        with col_side:
            st.subheader("📟 Логи")
            st.code("\n".join(st.session_state.logs[::-1]))
            if auto_refresh:
                time.sleep(5)
                st.rerun()
    else:
        st.error("Не удалось найти Ethereum-рынок по этой ссылке.")
