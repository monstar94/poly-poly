import streamlit as st
import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.constants import BUY

# --- ФУНКЦИЯ ПОИСКА СВЕЖЕГО РЫНКА ---
def get_active_eth_market():
    # Запрос к Gamma API для поиска рынков Ethereum
    url = "https://gamma-api.polymarket.com/markets?active=true&tag_id=10051" # Тэг эфира
    resp = requests.get(url).json()
    # Ищем рынок, который заканчивается в ближайшие 15 минут
    for market in resp:
        if "Ethereum Price" in market['question']:
            return market['tokens'][0]['token_id'], market['question']
    return None, None

# --- ИНТЕРФЕЙС ---
st.title("🤖 Polymarket Cloud Bot")

with st.sidebar:
    st.header("Ключи доступа")
    pk = st.text_input("Private Key", type="password")
    
if pk:
    client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
    
    token_id, market_name = get_active_eth_market()
    
    if token_id:
        st.info(f"Активный рынок: {market_name}")
        st.write(f"ID токена: {token_id}")
        
        if st.button("Запустить стратегию (Лимитка по 0.05)"):
            order_args = OrderArgs(token_id=token_id, price=0.05, size=10.0, side=BUY)
            signed_order = client.create_order(order_args)
            resp = client.post_order(signed_order)
            st.success(f"Ордер выставлен! Ответ API: {resp}")
    else:
        st.error("Не удалось найти активный 15-мин рынок")
