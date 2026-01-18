import streamlit as st
import requests
import json
import pandas as pd
import time
import pytz
import random
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

st.set_page_config(page_title="Polymarket Auto-Terminal", layout="wide")

# --- ЛОГИКА АВТОМАТИЧЕСКОЙ ССЫЛКИ ---
def get_auto_slug():
    # Polymarket ориентируется на время в Нью-Йорке
    tz_et = pytz.timezone('US/Eastern')
    now = datetime.now(tz_et)
    
    # Формируем компоненты: месяц, день, час(12ч), am/pm
    month = now.strftime("%B").lower()
    day = now.strftime("%d").lstrip('0')
    hour = now.strftime("%I").lstrip('0')
    am_pm = now.strftime("%p").lower()
    
    # Шаблон: ethereum-up-or-down-january-17-10pm-et
    return f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"

# --- ПОЛУЧЕНИЕ ДАННЫХ ИЗ API ---
def get_market_data(slug):
    try:
        # Запрашиваем ID токенов через Gamma API
        url = f"https://gamma-api.polymarket.com/events?slug={slug}&_nocache={random.random()}"
        r = requests.get(url, timeout=5).json()
        if r and len(r) > 0:
            m = r[0]['markets'][0]
            ids = json.loads(m['clobTokenIds'])
            return {"title": m['question'], "yes": ids[0], "no": ids[1], "active": m['active']}
    except: return None

def get_orderbook(token_id):
    try:
        # Запрос в CLOB стакан
        url = f"https://clob.polymarket.com/book?token_id={token_id}&_cb={int(time.time())}"
        resp = requests.get(url, timeout=2).json()
        
        def process(data, is_asks=False):
            df = pd.DataFrame(data)
            if df.empty: return pd.DataFrame(columns=['price', 'size', 'total'])
            df['price'] = df['price'].astype(float)
            df['size'] = df['size'].astype(float)
            df = df.sort_values('price', ascending=is_asks)
            df['total'] = df['size'].cumsum() # Накопление для визуализации глубины
            return df

        return process(resp.get('bids', []), False), process(resp.get('asks', []), True), float(resp.get('last_price', 0))
    except: return pd.DataFrame(), pd.DataFrame(), 0

# --- ИНТЕРФЕЙС ---
st.title("🤖 ETH Up/Down Auto-Terminal")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    st.write("---")
    st.info("Бот сам определяет текущий час и подключается к нужному рынку.")

# 1. Генерируем слаг автоматически
current_slug = get_auto_slug()
current_url = f"https://polymarket.com/event/{current_slug}"

st.caption(f"🔗 Активная ссылка: {current_url}")

# 2. Получаем данные рынка
m = get_market_data(current_slug)

if m:
    st.subheader(f"🎯 {m['title']}")
    
    col_sel, col_stat = st.columns([1, 2])
    trade_side = col_sel.radio("Выбери ставку:", ["UP (YES)", "DOWN (NO)"], horizontal=False)
    target_id = m['yes'] if "UP" in trade_side else m['no']

    # 3. Загружаем стакан
    bids, asks, last_price = get_orderbook(target_id)
    
    # Визуализация шанса
    chance = last_price * 100 if last_price > 0 else 50.0
    with col_stat:
        st.metric("ТЕКУЩИЙ ШАНС (ВЕРОЯТНОСТЬ)", f"{chance:.1f}%", delta=f"{last_price:.4f}")

    # СТАКАН «ЛЕСЕНКОЙ»
    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.write("🔴 **Продавцы (Asks)**")
        if not asks.empty:
            st.dataframe(asks[['price', 'size', 'total']].sort_values('price', ascending=False), use_container_width=True, hide_index=True)
        else: st.warning("Ожидание ордеров...")
    with cb:
        st.write("🟢 **Покупатели (Bids)**")
        if not bids.empty:
            st.dataframe(bids[['price', 'size', 'total']].sort_values('price', ascending=False), use_container_width=True, hide_index=True)
        else: st.warning("Ожидание ордеров...")

    # ТОРГОВЛЯ
    st.divider()
    t1, t2, t3 = st.columns([1,1,2])
    order_p = t1.number_input("Цена", value=float(last_price if last_price > 0 else 0.5), format="%.4f")
    order_s = t2.number_input("Кол-во акций", value=100)
    
    if t3.button("🚀 ОТПРАВИТЬ ОРДЕР", use_container_width=True):
        if not pk: st.error("Введи Private Key!")
        else:
            try:
                client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                client.set_api_creds(client.create_or_derive_api_creds())
                order = OrderArgs(token_id=target_id, price=order_p, size=order_s, side="BUY")
                res = client.post_order(client.create_order(order))
                st.toast(f"Успех: {res.get('success')}")
            except Exception as e: st.error(e)

else:
    st.error(f"Рынок `{current_slug}` еще не создан в API Polymarket.")
    st.info("Обычно новые рынки появляются за несколько минут до начала часа.")

# Обновление 1 сек
time.sleep(1)
st.rerun()
