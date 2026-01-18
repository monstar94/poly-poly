import streamlit as st
import requests
import time
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# --- НАСТРОЙКИ ---
BUY = "BUY"
st.set_page_config(page_title="Polymarket Debug Bot", layout="wide")

# --- ДЕБАГ КОНСОЛЬ ---
if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    st.session_state.logs.append(log_entry)
    # Ограничиваем лог последними 20 записями
    if len(st.session_state.logs) > 20:
        st.session_state.logs.pop(0)

# --- ФУНКЦИИ ---
def get_active_eth_market():
    add_log("🔍 Поиск активных 15-минутных рынков ETH...")
    try:
        # Тэг 10051 - это Ethereum
        url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&tag_id=10051"
        resp = requests.get(url).json()
        
        markets = []
        for m in resp:
            title = m.get('question', '').lower()
            # Фильтруем именно краткосрочные рынки цены
            if "ethereum" in title and ("above" in title or "price" in title):
                tokens = m.get('tokens')
                if tokens:
                    markets.append({
                        "id": tokens[0]['token_id'],
                        "name": m['question']
                    })
        
        if markets:
            add_log(f"✅ Найдено рынков: {len(markets)}")
            return markets[0]['id'], markets[0]['name']
    except Exception as e:
        add_log(f"❌ Ошибка поиска рынка: {str(e)}")
    return None, None

# --- ИНТЕРФЕЙС ---
st.title("🛡️ Polymarket Impulse Bot + Debug")

col_main, col_debug = st.columns([2, 1])

with col_main:
    st.subheader("Настройки и Управление")
    
    private_key = st.text_input("Введите Private Key (0x...)", type="password", help="Ваш закрытый ключ от кошелька")
    
    if private_key:
        try:
            # 1. Инициализация (L1 Auth)
            add_log("⚙️ Инициализация клиента...")
            client = ClobClient("https://clob.polymarket.com", key=private_key, chain_id=137)
            
            # 2. Создание API ключей (L2 Auth)
            # Это обязательный шаг для торговли, даже если они уже были созданы
            add_log("🔑 Генерация сессионных ключей (L2 Auth)...")
            api_creds = client.create_or_derive_api_creds()
            client.set_api_creds(api_creds)
            add_log("🔓 Авторизация успешна.")

            # Поиск рынка
            token_id, market_name = get_active_eth_market()
            
            if token_id:
                st.info(f"**Рынок:** {market_name}\n\n**Token ID:** `{token_id}`")
                
                c1, c2, c3 = st.columns(3)
                price = c1.number_input("Цена акции (0.01 - 0.99)", value=0.05)
                amount = c2.number_input("Кол-во акций", value=10)
                
                if st.button("🚀 ВЫСТАВИТЬ ОРДЕР", use_container_width=True):
                    add_log(f"📡 Отправка ордера: {amount} шт по {price} USDC...")
                    order_args = OrderArgs(token_id=token_id, price=price, size=amount, side=BUY)
                    signed_order = client.create_order(order_args)
                    resp = client.post_order(signed_order)
                    
                    if resp.get("success"):
                        add_log("🎯 ОРДЕР ВЫСТАВЛЕН УСПЕШНО!")
                        st.balloons()
                    else:
                        add_log(f"⚠️ Ошибка биржи: {resp.get('error')}")
                    st.json(resp)
            else:
                st.warning("Активные рынки не найдены. Попробуйте обновить страницу через минуту.")
                if st.button("🔄 Обновить поиск"):
                    st.rerun()

        except Exception as e:
            add_log(f"⛔ Критическая ошибка: {str(e)}")
            st.error(f"Проверьте правильность Private Key. Ошибка: {e}")
    else:
        st.info("Ожидание ввода Private Key...")

# --- КОНСОЛЬ ОТЛАДКИ ---
with col_debug:
    st.subheader("📟 Debug Console")
    console_box = st.empty()
    log_text = "\n".join(st.session_state.logs[::-1]) # Показываем новые сверху
    console_box.code(log_text if log_text else "Консоль пуста...")
    
    if st.button("Очистить логи"):
        st.session_state.logs = []
        st.rerun()
