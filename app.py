import streamlit as st
import ccxt
import json
import os
import time
import pandas as pd
from twap_executor import TWAPExecutor

st.set_page_config(layout="wide")
EXCHANGES_FILE = "exchanges.json"

# Initialize session state for orders_df and placeholders if not present
if "orders_df" not in st.session_state:
    st.session_state.orders_df = pd.DataFrame(columns=["datetime", "exchange", "price", "size", "side", "order_type", "result"])
if "orders_placeholder" not in st.session_state:
    st.session_state.orders_placeholder = None
if "closed_orders_placeholder" not in st.session_state:
    st.session_state.closed_orders_placeholder = None

# ---------- Callbacks and Order Updates ----------
def add_order_to_table(order_info):
    new_df = pd.DataFrame([order_info])
    st.session_state.orders_df = pd.concat([st.session_state.orders_df, new_df], ignore_index=True)
    st.session_state.orders_placeholder.dataframe(st.session_state.orders_df)

def update_closed_orders():
    all_closed_orders = []
    for ex_name, creds in exchanges.items():
        try:
            executor_instance = TWAPExecutor(
                exchange_name=ex_name,
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                side=side,
                total_size=total_size,    # Placeholder values for fetching orders
                total_run_time=10,
                frequency=1,
                testnet=creds.get("testnet", False),
                order_type=order_type
            )
            closed = executor_instance.fetch_closed_orders()
            all_closed_orders.extend(closed)
        except Exception as e:
            st.error(f"Error fetching closed orders for {ex_name}: {e}")
    if all_closed_orders:
        df_closed = pd.DataFrame(all_closed_orders)
        st.session_state.closed_orders_placeholder.dataframe(df_closed)
    else:
        st.session_state.closed_orders_placeholder.info("No closed orders found.")

# ---------- Exchange Management ----------
def load_exchanges():
    if os.path.exists(EXCHANGES_FILE):
        with open(EXCHANGES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_exchanges(exchanges):
    with open(EXCHANGES_FILE, "w") as f:
        json.dump(exchanges, f, indent=4)

def test_exchange_connection(exchange_name, api_key, api_secret, testnet, password=None):
    try:
        exchange_class = getattr(ccxt, exchange_name.lower())
        params = {"apiKey": api_key, "secret": api_secret}
        if exchange_name.lower() == "bitget" and password:
            params["password"] = password
        exchange = exchange_class(params)
        if testnet and exchange_name.lower() == "bybit":
            exchange.set_sandbox_mode(True)
        exchange.fetch_ticker("BTC/USDT")
        return True, "Connection successful."
    except Exception as e:
        return False, str(e)

# ---------- Sidebar: Add New Exchange ----------
st.sidebar.header("Add New Exchange")
new_exchange_name = st.sidebar.text_input("Exchange name (e.g. bybit, binance, bitget)", key="new_exchange")
new_api_key = st.sidebar.text_input("API Key", type="password", key="new_api_key")
new_api_secret = st.sidebar.text_input("API Secret", type="password", key="new_api_secret")
# Show password input if exchange is bitget (or if user manually types "bitget")
if new_exchange_name and new_exchange_name.lower() == "bitget":
    new_password = st.sidebar.text_input("Password", type="password", key="new_password")
else:
    new_password = None
new_testnet = st.sidebar.checkbox("Use Testnet?", value=True)
if st.sidebar.button("Add Exchange"):
    if new_exchange_name and new_api_key and new_api_secret:
        success, message = test_exchange_connection(new_exchange_name, new_api_key, new_api_secret, new_testnet, new_password)
        if success:
            exchanges = load_exchanges()
            exchanges[new_exchange_name.lower()] = {
                "api_key": new_api_key,
                "api_secret": new_api_secret,
                "testnet": new_testnet
            }
            if new_exchange_name.lower() == "bitget" and new_password:
                exchanges[new_exchange_name.lower()]["password"] = new_password
            save_exchanges(exchanges)
            st.sidebar.success(f"{new_exchange_name} added successfully!")
        else:
            st.sidebar.error(f"Connection failed: {message}")
    else:
        st.sidebar.error("Please fill in all fields.")

# ---------- Main Page Layout: Two Columns ----------
left_col, right_col = st.columns([1, 2])

# ---------- Left Column: Inputs ----------
with left_col:
    st.header("Exchange & TWAP Parameters")
    exchanges = load_exchanges()
    if exchanges:
        selected_exchange = st.selectbox("Select Exchange", list(exchanges.keys()))
    else:
        st.info("No exchanges available. Please add one in the sidebar.")
        selected_exchange = None

    # Below the select box, display the account balance for the selected exchange
    if selected_exchange:
        creds = exchanges[selected_exchange]
        try:
            exchange_class = getattr(ccxt, selected_exchange.lower())
            params = {"apiKey": creds["api_key"], "secret": creds["api_secret"]}
            if selected_exchange.lower() == "bitget":
                if "password" not in creds:
                    st.error("For Bitget, please add your password in the exchange settings.")
                else:
                    params["password"] = creds["password"]
            exchange = exchange_class(params)
            if creds.get("testnet", False) and selected_exchange.lower() == "bybit":
                exchange.set_sandbox_mode(True)
            balance = exchange.fetch_balance()
            st.markdown("### Account Balance")
            st.json(balance)
        except Exception as e:
            st.error(f"Error fetching balance for {selected_exchange}: {e}")

    st.markdown("---")
    st.subheader("TWAP Parameters")
    # First row: Trading Symbol, Side, Order Type
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Trading Symbol (e.g. BTC/USDT)", value="BTC/USDT")
    with col2:
        side = st.selectbox("Side", options=["buy", "sell"])
    with col3:
        order_type = st.selectbox("Order Type", options=["limit", "market"])
    # Second row: Total Size, Total Run Time, Frequency
    col4, col5, col6 = st.columns(3)
    with col4:
        total_size = st.number_input("Total Size", value=1000.0, min_value=0.0, step=1.0)
    with col5:
        total_run_time = st.number_input("Total Run Time (seconds)", value=60, min_value=1, step=1)
    with col6:
        frequency = st.number_input("Frequency (seconds)", value=10, min_value=1, step=1)
    # Third row: Full-width Price Limit
    price_limit = st.number_input("Price Limit (optional)", value=0.0, step=1.0)
    if price_limit == 0.0:
        price_limit = None

    st.markdown("---")
    if st.button("Start TWAP Execution"):
        if selected_exchange is None:
            st.error("Please add and select an exchange first.")
        else:
            creds = exchanges[selected_exchange]
            st.info("Starting TWAP execution. This may take a while...")
            executor = TWAPExecutor(
                exchange_name=selected_exchange,
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                symbol=symbol,
                side=side,
                total_size=total_size,
                total_run_time=total_run_time,
                frequency=frequency,
                testnet=creds.get("testnet", False),
                price_limit=price_limit,
                order_type=order_type
            )
            orders = executor.execute(order_list_callback=add_order_to_table)
            st.success("TWAP execution completed.")
            update_closed_orders()

# ---------- Right Column: Orders Display ----------
with right_col:
    st.header("Order Information")
    st.subheader("Executed Orders")
    st.session_state.orders_placeholder = st.empty()
    
    st.subheader("Closed (Completed) Orders from All Exchanges")
    st.session_state.closed_orders_placeholder = st.empty()

# Update closed orders at startup
update_closed_orders()
