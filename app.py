import streamlit as st
import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Указываем BUY и SELL напрямую, чтобы избежать проблем с импортами
BUY = "BUY"

def get_active_eth_market():
    try:
        url = "https://gamma-api.polymarket.com/markets?active=true&tag_id=10051"
        resp = requests.get(url).json()
        for market in resp:
            if "Ethereum Price" in market.get('question', ''):
                # Берем первый доступный токен (обычно это исход "YES")
                return market['tokens'][0]['token_id'], market['question']
    except Exception as e:
        st.error(f"Ошибка поиска рынка: {e}")
    return None, None

st.title("🤖 Polymarket Cloud Bot")

with st.sidebar:
    st.header("Настройки")
    pk = st.text_input("Private Key (0x...)", type="password")
    st.info("Ключ используется только для подписи транзакций и не сохраняется.")

if pk:
    try:
        # Инициализация клиента
        client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137)
        
        token_id, market_name = get_active_eth_market()
        
        if token_id:
            st.success(f"Подключено к рынку: {market_name}")
            
            col1, col2 = st.columns(2)
            price = col1.number_input("Цена покупки (0.01 - 0.99)", value=0.05, step=0.01)
            amount = col2.number_input("Количество акций", value=10.0, step=1.0)

            if st.button("🚀 ВЫСТАВИТЬ ЛИМИТКУ", use_container_width=True):
                with st.spinner("Отправка ордера..."):
                    order_args = OrderArgs(
                        token_id=token_id, 
                        price=price, 
                        size=amount, 
                        side=BUY
                    )
                    signed_order = client.create_order(order_args)
                    resp = client.post_order(signed_order)
                    st.json(resp)
        else:
            st.warning("Активные 15-минутные рынки ETH не найдены.")
            
    except Exception as e:
        st.error(f"Ошибка инициализации: {e}")
else:
    st.info("Введите Private Key в боковой панели, чтобы начать.")
