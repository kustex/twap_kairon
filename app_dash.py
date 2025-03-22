import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import json
import os
import pandas as pd
import pytz

from twap_engine import start_engine, scheduler
from twap_engine.db import fetch_submitted_orders

# ------------------- Initialization -------------------
start_engine()
tz = pytz.timezone('Europe/Paris')
EXCHANGES_FILE = "exchanges.json"
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ------------------- Helper Functions -------------------
def load_exchanges():
    if os.path.exists(EXCHANGES_FILE):
        with open(EXCHANGES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_exchanges(exchanges):
    with open(EXCHANGES_FILE, "w") as f:
        json.dump(exchanges, f, indent=4)

# ------------------- Dash App Setup -------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

app.layout = dbc.Container([
    dbc.Button("Add Exchange", id="open-sidebar", n_clicks=0, className="mb-3", color="info"),

    dbc.Offcanvas([
        html.H5("Add New Exchange", className="mb-3"),
        dbc.Label("Exchange name (e.g. bybit, binance, bitget)"),
        dbc.Input(id="new-exchange", type="text", value="", className="mb-2"),
        dbc.Label("API Key"),
        dbc.Input(id="new-api-key", type="password", className="mb-2"),
        dbc.Label("API Secret"),
        dbc.Input(id="new-api-secret", type="password", className="mb-2"),
        dbc.Label("Password (if required)"),
        dbc.Input(id="new-password", type="password", className="mb-2"),
        dbc.Checkbox(id="new-testnet", label="Use Testnet?", value=True, className="mb-3"),
        dbc.Button("Save Exchange", id="save-exchange", color="primary", className="me-2"),
        html.Div(id="exchange-save-feedback", className="mt-2")
    ], id="sidebar", title="Exchange Settings", is_open=False, placement="start"),

    dbc.Row([
        dbc.Col([
            html.H3("TWAP Parameters"),
            dbc.Label("Select Exchange"),
            dcc.Dropdown(
                id="exchange-dropdown",
                options=[{"label": k, "value": k} for k in load_exchanges().keys()],
                value=list(load_exchanges().keys())[0] if load_exchanges() else None
            ),
            dbc.Label("Trading Symbol"),
            dbc.Input(id="symbol-input", type="text", value="BTC/USDT"),
            dbc.Label("Side"),
            dcc.Dropdown(
                id="side-dropdown",
                options=[{"label": "buy", "value": "buy"}, {"label": "sell", "value": "sell"}],
                value="buy"
            ),
            dbc.Label("Total Size"),
            dbc.Input(id="total-size", type="number", value=0.1),
            dbc.Label("Total Run Time (seconds)"),
            dbc.Input(id="total-run-time", type="number", value=60),
            dbc.Label("Number of Trades"),
            dbc.Input(id="number-of-trades", type="number", value=6),
            dbc.Label("Price Limit (optional)"),
            dbc.Input(id="price-limit", type="number", value=0.0),
            dbc.Button("Start TWAP Execution", id="start-twap", color="primary", className="mt-3"),
            html.Div(id="start-twap-output", className="mt-2")
        ], width=4),

        dbc.Col([
            html.H3("Submitted Trades"),
            dash_table.DataTable(
                id="submitted-orders-table",
                columns=[
                    {"name": "ID", "id": "id"},
                    {"name": "Trade #", "id": "trade_number"},
                    {"name": "Timestamp", "id": "timestamp"},
                    {"name": "Exchange", "id": "exchange"},
                    {"name": "Symbol", "id": "symbol"},
                    {"name": "Submit Price", "id": "price_at_submit"},
                    {"name": "Size", "id": "size"},
                    {"name": "Side", "id": "side"},
                    {"name": "Order Type", "id": "order_type"},
                    {"name": "Job ID", "id": "job_id"}
                ],
                data=[],
                style_table={"overflowX": "auto"},
                page_size=10
            ),
            html.Hr(),
            html.H3("Active TWAP Jobs"),
            dash_table.DataTable(
                id="active-jobs-table",
                columns=[
                    {"name": "Exchange", "id": "exchange"},
                    {"name": "Symbol", "id": "symbol"},
                    {"name": "Side", "id": "side"},
                    {"name": "Remaining Trades", "id": "remaining_trades"},
                    {"name": "Next Execution", "id": "next_exec"}
                ],
                data=[],
                style_table={"overflowX": "auto"},
                page_size=10
            )
        ], width=8)
    ]),

    dcc.Interval(id="orders-interval", interval=5000, n_intervals=0)
], fluid=True)

# ------------------- Callbacks -------------------
@app.callback(
    Output("sidebar", "is_open"),
    Input("open-sidebar", "n_clicks"),
    State("sidebar", "is_open"),
    prevent_initial_call=True
)
def toggle_sidebar(n_clicks, is_open):
    return not is_open

@app.callback(
    Output("exchange-save-feedback", "children"),
    Output("exchange-dropdown", "options"),
    Input("save-exchange", "n_clicks"),
    State("new-exchange", "value"),
    State("new-api-key", "value"),
    State("new-api-secret", "value"),
    State("new-password", "value"),
    State("new-testnet", "value"),
    prevent_initial_call=True
)
def save_exchange(n_clicks, name, api_key, api_secret, password, testnet):
    if not name or not api_key or not api_secret:
        return "Please fill in all required fields.", dash.no_update
    try:
        import ccxt
        exchange_class = getattr(ccxt, name.lower())
        params = {"apiKey": api_key, "secret": api_secret}
        if password:
            params["password"] = password
        exchange = exchange_class(params)
        if testnet and name.lower() == "bybit":
            exchange.set_sandbox_mode(True)
        exchange.fetch_ticker("BTC/USDT")
    except Exception as e:
        return f"Connection failed: {str(e)}", dash.no_update

    exchanges = load_exchanges()
    exchanges[name.lower()] = {
        "api_key": api_key,
        "api_secret": api_secret,
        "password": password,
        "testnet": testnet
    }
    save_exchanges(exchanges)
    options = [{"label": k, "value": k} for k in exchanges.keys()]
    return f"{name} saved successfully.", options

@app.callback(
    Output("start-twap-output", "children"),
    Input("start-twap", "n_clicks"),
    State("exchange-dropdown", "value"),
    State("symbol-input", "value"),
    State("side-dropdown", "value"),
    State("total-size", "value"),
    State("total-run-time", "value"),
    State("number-of-trades", "value"),
    State("price-limit", "value"),
    prevent_initial_call=True
)
def start_twap(n_clicks, selected_exchange, symbol, side, total_size, total_run_time, number_of_trades, price_limit):
    if not selected_exchange:
        return "Please select an exchange."

    exchanges = load_exchanges()
    creds = exchanges.get(selected_exchange)
    if not creds:
        return "Exchange credentials not found."

    interval = total_run_time / number_of_trades
    price_limit = price_limit if price_limit > 0 else None

    scheduler.add_job({
        "exchange": selected_exchange,
        "api_key": creds["api_key"],
        "api_secret": creds["api_secret"],
        "password": creds.get("password"),
        "symbol": symbol,
        "side": side,
        "total_size": total_size,
        "num_trades": number_of_trades,
        "delay_seconds": interval,
        "testnet": creds.get("testnet", False),
        "price_limit": price_limit
    })

    return "TWAP job submitted successfully."

@app.callback(
    Output("active-jobs-table", "data"),
    Input("orders-interval", "n_intervals")
)
def update_active_jobs(n):
    return scheduler.get_active_jobs()

@app.callback(
    Output("submitted-orders-table", "data"),
    Input("orders-interval", "n_intervals")
)
def update_submitted_orders(n):
    orders = fetch_submitted_orders()
    for order in orders:
        tn = order.get("trade_number")
        nt = order.get("num_trades")
        if tn is not None and nt:
            order["trade_number"] = f"{tn}/{nt}" 
    return orders




if __name__ == "__main__":
    app.run(debug=True)