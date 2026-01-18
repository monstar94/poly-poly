import streamlit as st
import requests
import json
import pytz
import time
from datetime import datetime, timedelta
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

st.set_page_config(page_title="Polymarket Live Terminal", layout="wide")

# --- ФУНКЦИЯ ГЕНЕРАЦИИ АКТУАЛЬНОЙ ССЫЛКИ ---
def get_current_slug():
    # Polymarket работает по времени Нью-Йорка (ET)
    tz_et = pytz.timezone('US/Eastern')
    now = datetime.now(tz_et)
    
    # Форматируем под стиль Polymarket: ethereum-up-or-down-month-day-hour-et
    month = now.strftime("%B").lower()
    day = now.strftime("%d").lstrip('0')
    hour = now.strftime("%I").lstrip('0')
    am_pm = now.strftime("%p").lower()
    
    return f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"

# --- ПОЛУЧЕНИЕ ТОКЕНОВ И СТАКАНА ---
def get_market_and_book(slug):
    try:
        # 1. Получаем ID рынка через Gamma API
        gamma_url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        resp = requests.get(gamma_url).json()
        
        if not resp:
            return None, "Рынок еще не создан или ссылка неверна"
        
        market = resp[0]['markets'][0]
        question = market['question']
        tokens = json.loads(market['clobTokenIds'])
        
        # 2. Получаем стакан через CLOB API
        # Используем YES токен (индекс 0) для UP
        book_url = f"https://clob.polymarket.com/book?token_id={tokens[0]}"
        book = requests.get(book_url).json()
        
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        
        price = 0
        if bids and asks:
            price = (float(bids[0]['price']) + float(asks[0]['price'])) / 2
        elif bids: price = float(bids[0]['price'])
        
        return {
            "question": question,
            "price": price,
            "bids": bids[:5],
            "asks": asks[:5],
            "token_id": tokens[0]
        }, None
    except Exception as e:
        return None, str(e)

# --- ИНТЕРФЕЙС ---
st.title("⚡ Polymarket Hourly Terminal")

# Авто-генерация ссылки
current_slug = get_current_slug()
st.subheader(f"Текущий рынок: `{current_slug}`")

if "pk" not in st.session_state: st.session_state.pk = ""
st.session_state.pk = st.sidebar.text_input("Private Key", value=st.session_state.pk, type="password")

# Получаем данные
data, error = get_market_and_book(current_slug)

if data:
    # ОТОБРАЖЕНИЕ ЦЕНЫ
    col1, col2 = st.columns(2)
    with col1:
        if data['price'] > 0:
            st.metric("ТЕКУЩАЯ ЦЕНА (UP)", f"{data['price']:.4f}")
        else:
            st.warning("⚠️ Стакан пуст (торги еще не начались)")
    
    with col2:
        st.write(f"**Вопрос:** {data['question']}")
        st.write(f"**Token ID:** `{data['token_id']}`")

    # СТАКАН
    st.divider()
    b_col, a_col = st.columns(2)
    with b_col:
        st.write("🟢 **Bids (Buy)**")
        st.table(data['bids'])
    with a_col:
        st.write("🔴 **Asks (Sell)**")
        st.table(data['asks'])

    # ТОРГОВЛЯ
    st.divider()
    t_col1, t_col2, t_col3 = st.columns(3)
    p_order = t_col1.number_input("Цена", value=data['price'] if data['price'] > 0 else 0.5, step=0.01)
    a_order = t_col2.number_input("Кол-во акций", value=10)
    
    if t_col3.button("🚀 КУПИТЬ UP", use_container_width=True):
        if not st.session_state.pk:
            st.error("Введи ключ!")
        else:
            try:
                client = ClobClient("https://clob.polymarket.com", key=st.session_state.pk, chain_id=137)
                client.set_api_creds(client.create_or_derive_api_creds())
                order = OrderArgs(token_id=data['token_id'], price=p_order, size=a_order, side="BUY")
                resp = client.post_order(client.create_order(order))
                st.write(resp)
            except Exception as e:
                st.error(f"Ошибка: {e}")
else:
    st.error(f"Не удалось загрузить стакан: {error}")
    st.info("Попробуйте обновить страницу через 5-10 минут, когда Polymarket откроет новый час.")

# Авто-обновление 1 сек
time.sleep(1)
st.rerun()
