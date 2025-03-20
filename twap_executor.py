import time
import ccxt
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TWAPExecutor:
    def __init__(self, exchange_name, api_key, api_secret, symbol, side, total_size, total_run_time, frequency,
                 testnet=False, price_limit=None, password=None):
        """
        Initializes the TWAP executor for market orders only.
        
        Parameters:
            exchange_name (str): Exchange name (e.g. "bybit", "binance", "bitget").
            api_key (str): API key.
            api_secret (str): API secret.
            symbol (str): Trading symbol (e.g. "BTC/USDT").
            side (str): "buy" or "sell".
            total_size (float): Total order size to execute.
            total_run_time (float): Total run time in seconds.
            frequency (float): Time (in seconds) between orders.
            testnet (bool): If True, enable testnet/sandbox mode.
            price_limit (float, optional): For buy orders, if current price > price_limit, execution stops;
                                           for sell orders, if current price < price_limit, execution stops.
            password (str, optional): Additional password credential required by some exchanges (e.g. Bitget).
        """
        self.exchange_name = exchange_name.lower()
        self.symbol = symbol
        self.side = side.lower()
        self.total_size = total_size
        self.total_run_time = total_run_time
        self.frequency = frequency
        self.price_limit = price_limit  # Used as threshold only.
        self.testnet = testnet
        self.password = password

        self.iterations = int(total_run_time / frequency)
        if self.iterations == 0:
            raise ValueError("Total run time must be greater than frequency.")
        self.order_size = total_size / self.iterations

        exchange_class = getattr(ccxt, self.exchange_name)
        params = {"apiKey": api_key, "secret": api_secret}
        if self.password:
            params["password"] = self.password
        self.exchange = exchange_class(params)
        if self.testnet and self.exchange_name == "bybit":
            self.exchange.set_sandbox_mode(True)

        self.exchange.load_markets()
        self.market_info = self.exchange.market(self.symbol)
        max_amount = self.market_info.get("limits", {}).get("amount", {}).get("max", None)
        if max_amount is not None and self.order_size > max_amount:
            logging.warning(
                f"Calculated order size {self.order_size} exceeds the maximum allowed ({max_amount}). "
                f"Setting per-order size to the maximum."
            )
            self.order_size = max_amount

    def get_market_price(self):
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            price = float(ticker["last"])
            logging.info(f"Fetched market price for {self.symbol}: {price}")
            return price
        except Exception as e:
            logging.error(f"Error fetching market price: {e}")
            return None

    def place_order(self, price=None):
        try:
            params = {}
            order_params = {
                "symbol": self.symbol,
                "side": self.side,
                "amount": self.order_size,
            }
            # For market orders, always use market order logic.
            if self.side == "buy":
                if price is None:
                    price = self.get_market_price()
                    if price is None:
                        raise ValueError("Unable to fetch price for market buy order.")
                params["createMarketBuyOrderRequiresPrice"] = True
                order_params["type"] = "market"
                order_params["price"] = price
                order_params["params"] = params
            else:
                order_params["type"] = "market"
                order_params["params"] = params

            logging.info("Placing order with parameters:")
            logging.info(order_params)
            order = self.exchange.create_order(**order_params)
            logging.info(f"Order placed: {order}")
            order_id = order.get("id", None)
            return {"order_id": order_id, "status": order.get("status", "unknown")}
        except Exception as e:
            logging.error(f"Error placing order: {e}")
            return {"error": str(e)}

    def execute(self, order_list_callback=None):
        """
        Executes the TWAP strategy for market orders.
        Checks if the current market price is within the acceptable threshold (price_limit).
        For buy orders, if current price > price_limit, execution stops.
        For sell orders, if current price < price_limit, execution stops.
        
        Parameters:
            order_list_callback (function, optional): Callback to update each executed order.
        
        Returns:
            List of dictionaries containing the executed orders.
        """
        logging.info(f"Starting TWAP execution for {self.iterations} iterations.")
        orders_executed = []
        for i in range(self.iterations):
            current_price = self.get_market_price()
            if current_price is None:
                logging.error("Skipping iteration due to market data error.")
                time.sleep(self.frequency)
                continue

            if self.price_limit is not None:
                if self.side == "buy" and current_price > self.price_limit:
                    logging.error(f"Current price {current_price} exceeds acceptable buy threshold {self.price_limit}. Stopping TWAP execution.")
                    break
                if self.side == "sell" and current_price < self.price_limit:
                    logging.error(f"Current price {current_price} is below acceptable sell threshold {self.price_limit}. Stopping TWAP execution.")
                    break

            result = self.place_order(price=current_price)
            order_info = {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "exchange": self.exchange_name,
                "price": current_price,
                "size": self.order_size,
                "side": self.side,
                "order_type": "market",
                "result": result
            }
            orders_executed.append(order_info)
            if order_list_callback:
                order_list_callback(order_info)
            time.sleep(self.frequency)
        logging.info("TWAP execution completed.")
        return orders_executed
