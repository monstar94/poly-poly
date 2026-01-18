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

st.set_page_config(page_title="ETH Live Terminal", layout="wide")

# --- ЛОГИКА АВТО-ССЫЛКИ ---
def get_auto_slug():
    tz_et = pytz.timezone('US/Eastern')
    now = datetime.now(tz_et)
    month = now.strftime("%B").lower()
    day = now.strftime("%d").lstrip('0')
    hour = now.strftime("%I").lstrip('0')
    am_pm = now.strftime("%p").lower()
    return f"ethereum-up-or-down-{month}-{day}-{hour}{am_pm}-et"

# --- ПОЛУЧЕНИЕ ДАННЫХ (ЖИВОЕ ОБНОВЛЕНИЕ) ---
def get_live_data(token_id):
    try:
        # Добавляем случайный параметр для 100% обхода кэша
        url = f"https://clob.polymarket.com/book?token_id={token_id}&cachebuster={random.random()}"
        resp = requests.get(url, timeout=2).json()
        
        def process_side(data, is_asks=False):
            df = pd.DataFrame(data)
            if df.empty: return pd.DataFrame(columns=['price', 'size', 'total'])
            df['price'] = df['price'].astype(float)
            df['size'] = df['size'].astype(float)
            df = df.sort_values('price', ascending=is_asks)
            df['total'] = df['size'].cumsum()
            return df

        bids = process_side(resp.get('bids', []), False)
        asks = process_side(resp.get('asks', []), True)
        
        # --- ВОЗВРАТ ЖИВОЙ ЦЕНЫ ЧЕРЕЗ MIDPOINT ---
        live_price = 0.0
        if not bids.empty and not asks.empty:
            # Берем лучшие цены из стакана
            best_bid = bids.iloc[0]['price']
            best_ask = asks.iloc[0]['price']
            live_price = (best_bid + best_ask) / 2
        elif not bids.empty:
            live_price = bids.iloc[0]['price']
        elif not asks.empty:
            live_price = asks.iloc[0]['price']
            
        return bids, asks, live_price
    except:
        return pd.DataFrame(), pd.DataFrame(), 0.0

def get_market_config(slug):
    try:
        url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        r = requests.get(url).json()
        if r and len(r) > 0:
            m = r[0]['markets'][0]
            ids = json.loads(m['clobTokenIds'])
            return {"title": m['question'], "yes": ids[0], "no": ids[1]}
    except: return None

# --- ИНТЕРФЕЙС ---
st.title("⚡ ETH Live Midpoint Terminal")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    st.info("Цена рассчитывается как Midpoint между лучшим Bid и Ask для мгновенной реакции.")

# Авто-подбор рынка
slug = get_auto_slug()
m = get_market_config(slug)

if m:
    st.subheader(f"🎯 {m['title']}")
    st.caption(f"Market Slug: `{slug}`")
    
    col_sel, col_stat = st.columns([1, 2])
    side = col_sel.radio("Выбери ставку:", ["UP (YES)", "DOWN (NO)"], horizontal=False)
    tid = m['yes'] if "UP" in side else m['no']

    # ПОЛУЧАЕМ ЖИВОЙ СТАКАН И ЦЕНУ
    bids, asks, live_p = get_live_data(tid)
    
    # Визуализация цены
    with col_stat:
        if live_p > 0:
            st.metric("ЖИВАЯ ЦЕНА (MIDPOINT)", f"{live_p:.4f}", delta=f"{(live_p*100):.1f}% Chance")
        else:
            st.error("СТАКАН ПУСТ - ОЖИДАНИЕ ОРДЕРОВ")

    # СТАКАН ЛЕСЕНКОЙ
    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.write("🔴 **Asks (Sell)**")
        if not asks.empty:
            st.dataframe(asks[['price', 'size', 'total']].sort_values('price', ascending=False), use_container_width=True, hide_index=True)
    with cb:
        st.write("🟢 **Bids (Buy)**")
        if not bids.empty:
            st.dataframe(bids[['price', 'size', 'total']].sort_values('price', ascending=False), use_container_width=True, hide_index=True)

    # ТОРГОВЛЯ
    st.divider()
    t1, t2, t3 = st.columns([1,1,2])
    # Предлагаем цену из Midpoint
    val_p = float(live_p if live_p > 0 else 0.5)
    order_p = t1.number_input("Цена", value=val_p, format="%.4f", step=0.0001)
    order_s = t2.number_input("Кол-во", value=100)
    
    if t3.button("🚀 ОТПРАВИТЬ ОРДЕР", use_container_width=True):
        if not pk: st.error("Введи ключ!")
        else:
            try:
                client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                client.set_api_creds(client.create_or_derive_api_creds())
                order = OrderArgs(token_id=tid, price=order_p, size=order_s, side="BUY")
                res = client.post_order(client.create_order(order))
                st.toast(f"Success: {res.get('success')}")
            except Exception as e: st.error(e)
else:
    st.warning(f"Рынок `{slug}` еще не готов. Ждем открытия часа...")

# Обновление 1 сек
time.sleep(1)
st.rerun()
