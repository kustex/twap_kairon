# tasks.py
from celery import Celery
import ccxt
import logging
from datetime import datetime

app = Celery('tasks', broker='redis://localhost:6379/0')
logging.basicConfig(level=logging.INFO)

@app.task(bind=True)
def execute_single_trade(self, exchange_name, api_key, api_secret, password, symbol, side, order_size, testnet, price_limit):
    """
    Executes a single market order.
    For buy orders, if the current price exceeds price_limit, the trade is cancelled.
    For sell orders, if the current price is below price_limit, the trade is cancelled.
    """
    try:
        exchange_class = getattr(ccxt, exchange_name.lower())
        params = {"apiKey": api_key, "secret": api_secret}
        if password:
            params["password"] = password
        exchange = exchange_class(params)
        if testnet and exchange_name.lower() == "bybit":
            exchange.set_sandbox_mode(True)
        ticker = exchange.fetch_ticker(symbol)
        current_price = float(ticker["last"])
        logging.info(f"Fetched market price for {symbol}: {current_price}")
        
        # Check threshold
        if price_limit is not None:
            if side.lower() == "buy" and current_price > price_limit:
                logging.error(f"Trade cancelled: current price {current_price} exceeds buy threshold {price_limit}.")
                return {"error": "Price above threshold"}
            if side.lower() == "sell" and current_price < price_limit:
                logging.error(f"Trade cancelled: current price {current_price} is below sell threshold {price_limit}.")
                return {"error": "Price below threshold"}
        
        # Place market order.
        if side.lower() == "buy":
            params["createMarketBuyOrderRequiresPrice"] = True
            order = exchange.create_order(symbol, 'market', side, order_size, current_price, params)
        else:
            order = exchange.create_order(symbol, 'market', side, order_size, None, params)
        logging.info(f"Order executed: {order}")
        return order
    except Exception as e:
        logging.error(f"Error executing trade: {e}")
        return {"error": str(e)}
