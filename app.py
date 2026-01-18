import streamlit as st
import requests
import json
import pandas as pd
import time
import random
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

st.set_page_config(page_title="Polymarket Pro 1.0", layout="wide")

# --- СТИЛИЗАЦИЯ ---
st.markdown("""
    <style>
    .price-container { background-color: #1e1e1e; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; border: 1px solid #333; }
    .main-price { font-size: 54px !important; font-weight: bold; color: #00ff00; line-height: 1; }
    .chance-text { font-size: 24px; color: #888; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

def get_orderbook_detailed(token_id):
    try:
        # Принудительный обход кэша через таймстемп
        url = f"https://clob.polymarket.com/book?token_id={token_id}&ts={int(time.time() * 1000)}"
        resp = requests.get(url, timeout=2).json()
        
        def to_df(data, is_asks=False):
            df = pd.DataFrame(data)
            if df.empty: return pd.DataFrame(columns=['price', 'size', 'total'])
            df['price'] = df['price'].astype(float)
            df['size'] = df['size'].astype(float)
            # Сортировка для лесенки: Аски по убыванию, Биды по убыванию
            df = df.sort_values('price', ascending=not is_asks)
            df['total'] = df['size'].cumsum()
            return df

        asks = to_df(resp.get('asks', []), is_asks=True)
        bids = to_df(resp.get('bids', []), is_asks=False)
        
        # Получаем актуальную цену
        lp = resp.get('last_price')
        if not lp or float(lp) == 0:
            if not bids.empty and not asks.empty:
                lp = (bids.iloc[0]['price'] + asks.iloc[0]['price']) / 2
            elif not bids.empty: lp = bids.iloc[0]['price']
            else: lp = 0.5 # Default if market is dead
            
        return bids, asks, float(lp)
    except:
        return pd.DataFrame(), pd.DataFrame(), 0.5

def get_market_info(url):
    try:
        slug = url.strip().split('/')[-1]
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
        if r:
            m = r[0]['markets'][0]
            ids = json.loads(m['clobTokenIds'])
            return {"title": m['question'], "yes": ids[0], "no": ids[1]}
    except: return None

# --- ИНТЕРФЕЙС ---
st.sidebar.header("⚙️ Настройки")
pk = st.sidebar.text_input("Private Key", type="password")
refresh_speed = st.sidebar.slider("Обновление (сек)", 1, 5, 1)

url_input = st.text_input("Вставь URL (Ethereum Up/Down):", "https://polymarket.com/event/ethereum-up-or-down-january-18-4am-et")

if url_input:
    m_info = get_market_info(url_input)
    if m_info:
        st.subheader(f"📊 {m_info['title']}")
        
        side = st.radio("Выбери сторону:", ["UP (YES)", "DOWN (NO)"], horizontal=True)
        tid = m_info['yes'] if "UP" in side else m_info['no']
        
        bids, asks, price = get_orderbook_detailed(tid)

        # БЛОК ТЕКУЩЕЙ ЦЕНЫ И ШАНСА
        chance = price * 100
        st.markdown(f"""
            <div class="price-container">
                <div class="main-price">{price:.4f}</div>
                <div class="chance-text">Текущий шанс: {chance:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)

        # СТАКАН «ЛЕСЕНКОЙ»
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("🔴 **Продавцы (Asks)**")
            if not asks.empty:
                # Самые дешевые цены внизу списка (ближе к центру)
                st.dataframe(asks[['price', 'size', 'total']].sort_values('price', ascending=False), use_container_width=True, hide_index=True)
            else: st.info("Пусто")
            
        with col_b:
            st.write("🟢 **Покупатели (Bids)**")
            if not bids.empty:
                # Самые дорогие цены вверху списка (ближе к центру)
                st.dataframe(bids[['price', 'size', 'total']].sort_values('price', ascending=False), use_container_width=True, hide_index=True)
            else: st.info("Пусто")

        # ТОРГОВЛЯ
        st.divider()
        c1, c2, c3 = st.columns([1,1,2])
        trade_p = c1.number_input("Цена", value=price, format="%.4f")
        trade_s = c2.number_input("Кол-во", value=100)
        
        if c3.button("🚀 ОТПРАВИТЬ ОРДЕР", use_container_width=True):
            if not pk: st.error("Введи ключ!")
            else:
                try:
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    order = OrderArgs(token_id=tid, price=trade_p, size=trade_s, side="BUY")
                    res = client.post_order(client.create_order(order))
                    st.toast(f"Результат: {res.get('success')}")
                except Exception as e: st.error(e)

# Авто-обновление
time.sleep(refresh_speed)
st.rerun()
