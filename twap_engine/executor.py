import threading
import queue
import logging
import ccxt
import datetime
import time
from .db import log_submitted_order

logging.basicConfig(level=logging.INFO)

class OrderExecutor(threading.Thread):
    def __init__(self, order_queue, order_scheduler):
        super().__init__(daemon=True)
        self.order_queue = order_queue
        self.order_scheduler = order_scheduler
        self._stop_event = threading.Event()

    def run(self):
        logging.info("[Executor] OrderExecutor thread started.")
        while not self._stop_event.is_set():
            try:
                task = self.order_queue.get(timeout=1)
                self.submit_order(task)
                self.order_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"[Executor] Error in processing loop: {e}")
                order_id = task.get("id")
                if order_id:
                    self.order_scheduler.cancel_order(order_id)
                    logging.info(f"[Executor] Order {order_id} cancelled due to error.")

    def submit_order(self, task):
        exchange_name = task["exchange"]
        api_key = task["api_key"]
        api_secret = task["api_secret"]
        password = task.get("password")
        symbol = task["symbol"]
        side = task["side"]
        chunk_size = task["total_size"] / task["num_trades"]
        test_mode = bool(task.get("testnet", False))
        price_cap = task.get("price_limit")

        try:
            # Initialize exchange instance using ccxt
            exchange_class = getattr(ccxt, exchange_name.lower())
            credentials = {"apiKey": api_key, "secret": api_secret}
            if password:
                credentials["password"] = password

            exchange = exchange_class(credentials)
            if test_mode and exchange_name.lower() == "bybit":
                exchange.set_sandbox_mode(True)

            # Get current market price
            ticker = exchange.fetch_ticker(symbol)
            current_market_price = float(ticker["last"])
            logging.info(f"[Executor] Current price for {symbol}: {current_market_price}")

            # Check price cap conditions if provided
            if price_cap is not None:
                if side == "buy" and current_market_price > price_cap:
                    raise Exception(f"Buy limit exceeded: {current_market_price} > {price_cap}")
                if side == "sell" and current_market_price < price_cap:
                    raise Exception(f"Sell limit missed: {current_market_price} < {price_cap}")

            # Submit order via ccxt
            if side == "buy":
                credentials["createMarketBuyOrderRequiresPrice"] = True
                order_response = exchange.create_order(symbol, 'market', side, chunk_size, current_market_price, credentials)
            else:
                order_response = exchange.create_order(symbol, 'market', side, chunk_size, None, credentials)

            logging.info(f"[Executor] Order response: {order_response}")

            # Log submitted order along with the exchange order ID for later tracking.
            step = task.get("executed", 0)
            submitted_log = {
                "timestamp": datetime.datetime.now().isoformat(),
                "exchange": exchange_name,
                "symbol": symbol,
                "price_at_submit": current_market_price,
                "size": chunk_size,
                "side": side,
                "order_type": "market",
                "job_id": task.get("id"),
                "trade_number": step,
                "num_trades": task.get("num_trades"),
                "exchange_order_id": order_response.get("id")
            }
            log_submitted_order(submitted_log)

        except Exception as e:
            logging.error(f"[Executor] Order error: {e}")
            order_id = task.get("id")
            if order_id:
                self.order_scheduler.cancel_order(order_id)
                logging.info(f"[Executor] Order {order_id} cancelled due to error.")

    def stop(self):
        self._stop_event.set()
        logging.info("[Executor] OrderExecutor thread stopped.")


