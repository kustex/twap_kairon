import streamlit as st
import ccxt
import json
import os
import time
import pandas as pd
from twap_executor import TWAPExecutor

st.set_page_config(layout="wide")
EXCHANGES_FILE = "exchanges.json"
DATA_DIR = "data"
EXECUTED_ORDERS_FILE = os.path.join(DATA_DIR, "executed_orders.json")

# Create data directory if it doesn't exist.
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ---------- Functions for Executed Orders Storage ----------
def save_executed_orders(df):
    if "datetime" in df.columns:
        df["datetime"] = df["datetime"].astype(str)
    df.to_json(EXECUTED_ORDERS_FILE, orient="records", indent=4)

def load_executed_orders():
    if os.path.exists(EXECUTED_ORDERS_FILE):
        df = pd.read_json(EXECUTED_ORDERS_FILE)
        if "datetime" in df.columns:
            df["datetime"] = df["datetime"].astype(str)
        return df
    else:
        return pd.DataFrame(
            columns=["datetime", "exchange", "price", "size", "side", "order_type", "result"]
        )

# ---------- Initialize Session State ----------
if "orders_df" not in st.session_state:
    st.session_state.orders_df = load_executed_orders()
if "orders_placeholder" not in st.session_state:
    st.session_state.orders_placeholder = None

# ---------- Callbacks ----------
def add_order_to_table(order_info):
    new_df = pd.DataFrame([order_info])
    if st.session_state.orders_df.empty:
        st.session_state.orders_df = new_df
    else:
        st.session_state.orders_df = pd.concat([st.session_state.orders_df, new_df], ignore_index=True)
    if st.session_state.get("orders_placeholder") is not None:
        # Reverse the DataFrame if needed (newest on top), e.g.:
        st.session_state.orders_placeholder.dataframe(st.session_state.orders_df.iloc[::-1].reset_index(drop=True))
    save_executed_orders(st.session_state.orders_df)

def update_executed_orders_display():
    df = load_executed_orders()
    if st.session_state.get("orders_placeholder") is not None:
        st.session_state.orders_placeholder.dataframe(df.iloc[::-1].reset_index(drop=True))

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
        if password:
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
new_password = st.sidebar.text_input("Password (if required)", type="password", key="new_password")
new_testnet = st.sidebar.checkbox("Use Testnet?", value=True)
if st.sidebar.button("Add Exchange"):
    if new_exchange_name and new_api_key and new_api_secret:
        success, message = test_exchange_connection(new_exchange_name, new_api_key, new_api_secret, new_testnet, new_password)
        if success:
            exchanges = load_exchanges()
            exchanges[new_exchange_name.lower()] = {
                "api_key": new_api_key,
                "api_secret": new_api_secret,
                "testnet": new_testnet,
                "password": new_password
            }
            save_exchanges(exchanges)
            st.sidebar.success(f"{new_exchange_name} added successfully!")
        else:
            st.sidebar.error(f"Connection failed: {message}")
    else:
        st.sidebar.error("Please fill in all fields.")

# ---------- Helper Function to Display Balance ----------
def display_balance(selected_exchange, balance_placeholder):
    exchanges = load_exchanges()
    if selected_exchange:
        creds = exchanges[selected_exchange]
        try:
            exchange_class = getattr(ccxt, selected_exchange.lower())
            params = {"apiKey": creds["api_key"], "secret": creds["api_secret"]}
            if creds.get("password"):
                params["password"] = creds["password"]
            exchange = exchange_class(params)
            if creds.get("testnet", False) and selected_exchange.lower() == "bybit":
                exchange.set_sandbox_mode(True)
            balance = exchange.fetch_balance()
            skip_keys = {"info", "timestamp", "datetime"}
            data = []
            total_value = 0.0
            for asset, bal in balance.items():
                if asset.lower() in skip_keys:
                    continue
                if isinstance(bal, dict):
                    free = bal.get("free", 0)
                else:
                    free = bal
                try:
                    free = float(free)
                except Exception:
                    free = 0.0
                if free > 0:
                    if asset.upper() == "USDT":
                        price = 1.0
                    else:
                        try:
                            ticker = exchange.fetch_ticker(f"{asset.upper()}/USDT")
                            price = float(ticker["last"])
                        except Exception:
                            price = 0.0
                    value = free * price
                    total_value += value
                    data.append({
                        "Ticker": asset.upper(),
                        "Price": price,
                        "Free": free,
                        "Dollar Amount": value
                    })
            for item in data:
                item["Percentage"] = (item["Dollar Amount"] / total_value * 100) if total_value > 0 else 0.0
            df_balance = pd.DataFrame(data, columns=["Ticker", "Price", "Free", "Dollar Amount", "Percentage"])
            balance_placeholder.dataframe(df_balance)
        except Exception as e:
            balance_placeholder.error(f"Error fetching balance for {selected_exchange}: {e}")

# ---------- Main Page Layout: Two Columns (Left: Inputs, Right: Order Information) ----------
left_col, right_col = st.columns([1, 2])

# ---------- Right Column: Orders Display (Placeholders) ----------
with right_col:
    st.header("Order Information")
    st.subheader("Executed Orders")
    st.session_state.orders_placeholder = st.empty()
    executed_orders_df = load_executed_orders()
    st.session_state.orders_placeholder.dataframe(executed_orders_df.iloc[::-1].reset_index(drop=True))

# ---------- Left Column: Inputs and Balance Display ----------
with left_col:
    st.header("Exchange & TWAP Parameters")
    exchanges = load_exchanges()
    if exchanges:
        selected_exchange = st.selectbox("Select Exchange", list(exchanges.keys()))
    else:
        st.info("No exchanges available. Please add one in the sidebar.")
        selected_exchange = None

    # Create a placeholder for account balance display.
    balance_placeholder = st.empty()
    if selected_exchange:
        display_balance(selected_exchange, balance_placeholder)

    st.markdown("---")
    st.subheader("TWAP Parameters")
    # First row: Trading Symbol, Side.
    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Trading Symbol (e.g. BTC/USDT)", value="BTC/USDT")
    with col2:
        side = st.selectbox("Side", options=["buy", "sell"])
    # Second row: Total Size, Total Run Time, Frequency.
    col3, col4, col5 = st.columns(3)
    with col3:
        total_size = st.number_input("Total Size", value=1000.0, min_value=0.0, step=1.0)
    with col4:
        total_run_time = st.number_input("Total Run Time (seconds)", value=60, min_value=1, step=1)
    with col5:
        frequency = st.number_input("Frequency (seconds)", value=10, min_value=1, step=1)
    # Third row: Full-width Price Limit (threshold for cancellation).
    price_limit = st.number_input("Price Limit (optional)", value=0.0, step=1.0)
    if price_limit == 0.0:
        price_limit = None

    st.markdown("---")
    status_placeholder = st.empty()
    if st.button("Start TWAP Execution"):
        if selected_exchange is None:
            st.error("Please add and select an exchange first.")
        else:
            creds = exchanges[selected_exchange]
            if selected_exchange.lower() == "bitget" and not creds.get("password"):
                st.error("Bitget requires a password credential. Please update your exchange settings.")
            else:
                status_placeholder.info("Starting TWAP execution. This may take a while...")
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
                    password=creds.get("password")
                )
                orders = executor.execute(order_list_callback=add_order_to_table)
                status_placeholder.empty()  # Clear the status message.
                st.success("TWAP execution completed.")
                update_executed_orders_display()
                # Refresh account balance after TWAP execution.
                if selected_exchange:
                    display_balance(selected_exchange, balance_placeholder)
