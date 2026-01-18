import streamlit as st
import requests
import json
import pandas as pd
import time
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

st.set_page_config(page_title="Polymarket Pro Terminal", layout="wide")

# --- СТИЛИЗАЦИЯ ПОД КРИПТО-БИРЖУ ---
st.markdown("""
    <style>
    .big-price { font-size: 48px !important; font-weight: bold; color: #00ff00; text-align: center; }
    .stTable { font-size: 12px !important; }
    </style>
""", unsafe_allow_html=True)

# --- ГЕТТЕРЫ ДАННЫХ ---
def get_orderbook_data(token_id):
    try:
        url = f"https://clob.polymarket.com/book?token_id={token_id}&_t={int(time.time())}"
        data = requests.get(url, timeout=2).json()
        
        def process_side(entries, reverse=False):
            df = pd.DataFrame(entries)
            if df.empty: return pd.DataFrame(columns=['price', 'size', 'total'])
            df['price'] = df['price'].astype(float)
            df['size'] = df['size'].astype(float)
            df = df.sort_values('price', ascending=not reverse)
            df['total'] = df['size'].cumsum() # Накопление объема
            return df

        return process_side(data.get('bids', []), True), process_side(data.get('asks', [])), data.get('last_price', 0)
    except:
        return pd.DataFrame(), pd.DataFrame(), 0

def get_active_market(url):
    try:
        slug = url.strip().split('/')[-1]
        resp = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
        if resp:
            m = resp[0]['markets'][0]
            tokens = json.loads(m['clobTokenIds'])
            return {"name": m['question'], "yes": tokens[0], "no": tokens[1]}
    except: return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Polymarket Depth Terminal")

with st.sidebar:
    st.header("🔐 Торговый доступ")
    pk = st.text_input("Private Key", type="password")
    refresh = st.toggle("Live Refresh (1s)", value=True)
    st.divider()
    st.info("Бот автоматически рассчитывает суммарный объем (Total) для визуализации глубины стакана.")

link = st.text_input("URL События (Up/Down):", "https://polymarket.com/event/ethereum-up-or-down-january-18-4am-et")

if link:
    market = get_active_market(link)
    if market:
        st.subheader(f"🎯 {market['name']}")
        
        # Выбор стороны
        side_col1, side_col2 = st.columns([1, 3])
        trade_side = side_col1.radio("Торговать:", ["UP (YES)", "DOWN (NO)"], horizontal=False)
        target_id = market['yes'] if "UP" in trade_side else market['no']

        # Получение данных стакана
        bids, asks, last_p = get_orderbook_data(target_id)

        # ТЕКУЩАЯ ЦЕНА (ЦЕНТР)
        st.markdown(f"<div class='big-price'>{float(last_p)*100:.1f}¢</div>", unsafe_allow_html=True)
        
        # --- ВИЗУАЛИЗАЦИЯ СТАКАНА (Лесенка) ---
        col_asks, col_bids = st.columns(2)
        
        with col_asks:
            st.write("🔴 **Asks (Продажа / Лесенка вверх)**")
            if not asks.empty:
                # Окрашивание для визуализации накопления
                st.dataframe(
                    asks[['price', 'size', 'total']].sort_values('price', ascending=False).style.background_gradient(subset=['total'], cmap='Reds'),
                    use_container_width=True, hide_index=True
                )
            else: st.info("Стакан пуст")

        with col_bids:
            st.write("🟢 **Bids (Покупка / Лесенка вниз)**")
            if not bids.empty:
                st.dataframe(
                    bids[['price', 'size', 'total']].style.background_gradient(subset=['total'], cmap='Greens'),
                    use_container_width=True, hide_index=True
                )
            else: st.info("Стакан пуст")

        # --- ТОРГОВАЯ ПАНЕЛЬ ---
        st.divider()
        t_col1, t_col2, t_col3 = st.columns(3)
        # Автозаполнение цены из ближайшего ордера
        default_p = asks['price'].min() if not asks.empty else 0.5
        order_p = t_col1.number_input("Цена (¢)", value=float(default_p), format="%.3f")
        order_s = t_col2.number_input("Кол-во акций", value=100, step=10)
        
        if t_col3.button("⚡ ОТПРАВИТЬ ОРДЕР", use_container_width=True):
            if not pk: st.error("Введите ключ!")
            else:
                try:
                    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
                    client.set_api_creds(client.create_or_derive_api_creds())
                    order = OrderArgs(token_id=target_id, price=order_p, size=order_s, side="BUY")
                    resp = client.post_order(client.create_order(order)) # Отправка в CLOB
                    st.toast(f"Ответ API: {resp.get('success')}")
                except Exception as e: st.error(e)

# --- АВТО-ОБНОВЛЕНИЕ ---
if refresh:
    time.sleep(1)
    st.rerun()
