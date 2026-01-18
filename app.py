import streamlit as st
import requests
import json
import pandas as pd
import time
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

st.set_page_config(page_title="Polymarket Diagnostic Terminal", layout="wide")

# --- ФУНКЦИИ ДАННЫХ ---
def get_orderbook_data(token_id):
    try:
        # Прямое обращение к CLOB API с таймстампом
        ts = int(time.time() * 1000)
        url = f"https://clob.polymarket.com/book?token_id={token_id}&_ts={ts}"
        resp = requests.get(url, timeout=3).json()
        
        # Проверяем сырые данные
        if not resp.get('bids') and not resp.get('asks'):
            return None, None, 0, "EMPTY_BOOK"

        def process(entries, side):
            df = pd.DataFrame(entries)
            if df.empty: return pd.DataFrame(columns=['price', 'size', 'total'])
            df['price'] = df['price'].astype(float)
            df['size'] = df['size'].astype(float)
            # Сортировка для лесенки
            df = df.sort_values('price', ascending=(side == 'asks'))
            df['total'] = df['size'].cumsum()
            return df

        bids = process(resp.get('bids', []), 'bids')
        asks = process(resp.get('asks', []), 'asks')
        
        # Берем цену последней сделки или лучший Bid
        last_price = resp.get('last_price') or (bids.iloc[0]['price'] if not bids.empty else 0.5)
        
        return bids, asks, float(last_price), "OK"
    except Exception as e:
        return None, None, 0, str(e)

def get_market_details(url):
    try:
        slug = url.strip().split('/')[-1]
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
        if r and 'markets' in r[0]:
            m = r[0]['markets'][0]
            ids = json.loads(m['clobTokenIds'])
            return {"q": m['question'], "yes": ids[0], "no": ids[1], "active": m.get('active')}
    except: return None

# --- ИНТЕРФЕЙС ---
st.title("📟 Polymarket Debug Terminal")

with st.sidebar:
    pk = st.text_input("Private Key", type="password")
    st.info("Если цена стоит на 0.5 — это значит, что в стакане CLOB нет активных ордеров.")

url = st.text_input("Ссылка на рынок:", "https://polymarket.com/event/ethereum-up-or-down-january-18-4am-et")

if url:
    m = get_market_details(url)
    if m:
        st.write(f"### {m['q']}")
        st.write(f"Статус в API: {'🟢 АКТИВЕН' if m['active'] else '🔴 ЗАКРЫТ'}")
        
        side = st.radio("Сторона:", ["UP (YES)", "DOWN (NO)"], horizontal=True)
        token_id = m['yes'] if "UP" in side else m['no']
        
        # ЗАПРОС ДАННЫХ
        bids, asks, price, status = get_orderbook_data(token_id)
        
        if status == "OK":
            # Визуализация шанса (цены)
            chance = price * 100
            st.metric("ТЕКУЩИЙ ШАНС", f"{chance:.1f}%", delta=f"{price:.4f}")
            
            # РАБОЧИЙ СТАКАН
            c1, c2 = st.columns(2)
            with c1:
                st.write("🔴 **Asks (Продажа)**")
                st.dataframe(asks[['price', 'size', 'total']].sort_values('price', ascending=False), use_container_width=True, hide_index=True)
            with c2:
                st.write("🟢 **Bids (Покупка)**")
                st.dataframe(bids[['price', 'size', 'total']].sort_values('price', ascending=False), use_container_width=True, hide_index=True)
        
        elif status == "EMPTY_BOOK":
            st.error("⚠️ ВНИМАНИЕ: Стакан этого токена абсолютно пуст в API.")
            st.warning("Это происходит, если рынок завершен или по нему еще нет лимитных заявок.")
            st.write(f"Проверяемый Token ID: `{token_id}`")
        else:
            st.error(f"Ошибка API: {status}")

# Авто-рефреш 1 сек
time.sleep(1)
st.rerun()
