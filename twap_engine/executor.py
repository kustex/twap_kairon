# executor.py
import threading
import queue
import logging
import ccxt
import datetime
from .db import save_submitted_order

logging.basicConfig(level=logging.INFO)

class TradeExecutor(threading.Thread):
    def __init__(self, execution_queue, scheduler):
        super().__init__(daemon=True)
        self.execution_queue = execution_queue
        self.scheduler = scheduler
        self._stop_event = threading.Event()

    def run(self):
        logging.info("[Executor] TradeExecutor thread started.")
        while not self._stop_event.is_set():
            try:
                job = self.execution_queue.get(timeout=1)
                self.execute_trade(job)
                self.execution_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"[Executor] Error during execution loop: {e}")
                job_id = job.get("id")
                if job_id:
                    self.scheduler.remove_job_by_id(job_id)
                    logging.info(f"[Executor] Job {job_id} removed due to execution error.")

    def execute_trade(self, job):
        exchange_name = job["exchange"]
        api_key = job["api_key"]
        api_secret = job["api_secret"]
        password = job.get("password")
        symbol = job["symbol"]
        side = job["side"]
        size = job["total_size"] / job["num_trades"]
        testnet = bool(job.get("testnet", False))
        price_limit = job.get("price_limit")

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
            logging.info(f"[Executor] Market price for {symbol}: {current_price}")

            if price_limit is not None:
                if side == "buy" and current_price > price_limit:
                    raise Exception(f"Buy price {current_price} exceeds limit {price_limit}")
                if side == "sell" and current_price < price_limit:
                    raise Exception(f"Sell price {current_price} below limit {price_limit}")

            executed = job.get("executed", 0)
            trade_number = executed
            submitted = {
                "timestamp": datetime.datetime.now().isoformat(),
                "exchange": exchange_name,
                "symbol": symbol,
                "price_at_submit": current_price,
                "size": size,
                "side": side,
                "order_type": "market",
                "job_id": job.get("id"),
                "trade_number": trade_number,
                "num_trades": job.get("num_trades")  # 👈 ADD THIS

            }
            save_submitted_order(submitted)

            if side == "buy":
                params["createMarketBuyOrderRequiresPrice"] = True
                order = exchange.create_order(symbol, 'market', side, size, current_price, params)
            else:
                order = exchange.create_order(symbol, 'market', side, size, None, params)

            logging.info(f"[Executor] Trade executed: {order}")

        except Exception as e:
            logging.error(f"[Executor] Error executing trade: {e}")
            job_id = job.get("id")
            if job_id:
                self.scheduler.remove_job_by_id(job_id)
                logging.info(f"[Executor] Job {job_id} removed due to execution error.")

    def stop(self):
        self._stop_event.set()
        logging.info("[Executor] TradeExecutor thread stopped.")
