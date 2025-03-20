import time
import ccxt
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TWAPExecutor:
    def __init__(self, exchange_name, api_key, api_secret, symbol, side, total_size, total_run_time, frequency, testnet=False, price_limit=None, order_type="limit"):
        """
        Initializes the TWAP executor.
        
        Parameters:
            exchange_name (str): Exchange name (e.g., "bybit", "binance").
            api_key (str): API key.
            api_secret (str): API secret.
            symbol (str): Trading symbol (e.g., "BTC/USDT").
            side (str): "buy" or "sell".
            total_size (float): Total order size to execute.
                - For limit orders, this is the BASE amount.
                - For market orders: if side=="buy", this is the QUOTE amount; if side=="sell", this is the BASE amount.
            total_run_time (float): Total run time in seconds.
            frequency (float): Time (in seconds) between orders.
            testnet (bool): If True, enable testnet/sandbox mode.
            price_limit (float, optional): Price limit for the orders (used with limit orders).
            order_type (str): "limit" or "market" order type.
        """
        self.exchange_name = exchange_name.lower()
        self.symbol = symbol
        self.side = side.lower()
        self.total_size = total_size
        self.total_run_time = total_run_time
        self.frequency = frequency
        self.price_limit = price_limit
        self.order_type = order_type.lower()
        self.testnet = testnet

        # Calculate iterations and order size per iteration
        self.iterations = int(total_run_time / frequency)
        if self.iterations == 0:
            raise ValueError("Total run time must be greater than frequency.")
        self.order_size = total_size / self.iterations

        # Initialize exchange instance using CCXT
        exchange_class = getattr(ccxt, self.exchange_name)
        self.exchange = exchange_class({
            "apiKey": api_key,
            "secret": api_secret,
        })
        # If testnet is enabled and the exchange is Bybit, set sandbox mode
        if self.testnet and self.exchange_name == "bybit":
            self.exchange.set_sandbox_mode(True)

        # Load market info to check limits
        self.exchange.load_markets()
        self.market_info = self.exchange.market(self.symbol)
        max_amount = self.market_info.get("limits", {}).get("amount", {}).get("max", None)
        if max_amount is not None and self.order_size > max_amount:
            logging.warning(
                f"Calculated order size {self.order_size} exceeds the maximum allowed ({max_amount}). "
                f"Setting per-order size to the maximum."
            )
            self.order_size = max_amount
        else:
            logging.info("No maximum order size limit found or within allowed limits.")

    def get_market_price(self):
        """Fetches the current market price."""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            price = float(ticker["last"])
            logging.info(f"Fetched market price for {self.symbol}: {price}")
            return price
        except Exception as e:
            logging.error(f"Error fetching market price: {e}")
            return None

    def print_balance(self):
        """Fetches and logs the account balance for debugging."""
        try:
            balance = self.exchange.fetch_balance()
            base_currency, quote_currency = self.symbol.split('/')
            relevant = quote_currency if self.side == "buy" else base_currency
            asset = balance.get(relevant, {})
            free_balance = asset.get("free", "N/A")
            total_balance = asset.get("total", "N/A")
            logging.info(f"Balance for {relevant}: free={free_balance}, total={total_balance}")
            return balance
        except Exception as e:
            logging.error(f"Error fetching balance: {e}")
            return None

    def place_order(self, price=None):
        """
        Places an order using the provided order type and parameters.
        
        For limit orders, a price must be provided.
        For market orders:
          - If side is "buy", the amount is interpreted as the QUOTE amount if a price is provided.
          - If side is "sell", the amount is interpreted as the BASE amount.
        
        Returns:
            Dictionary with order details or error information.
        """
        try:
            params = {}
            order_params = {
                "symbol": self.symbol,
                "side": self.side,
                "amount": self.order_size,
            }
            if self.order_type == "market":
                if self.side == "buy":
                    # For market buy orders, force interpretation as quote amount.
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
            elif self.order_type == "limit":
                if price is None:
                    raise ValueError("Price is required for limit orders.")
                order_params["type"] = "limit"
                order_params["price"] = price
                order_params["params"] = params
            else:
                raise ValueError("Invalid order type. Use 'market' or 'limit'.")

            logging.info("Placing order with parameters:")
            logging.info(order_params)

            order = self.exchange.create_order(**order_params)
            logging.info(f"Order placed: {order}")
            order_id = order.get("id", None)
            return {"order_id": order_id, "status": order.get("status", "unknown")}
        except Exception as e:
            logging.error(f"Error placing order: {e}")
            return {"error": str(e)}

    def fetch_closed_orders(self):
        """Fetches closed (completed) orders for the given symbol from the exchange."""
        try:
            closed_orders = self.exchange.fetch_closed_orders(self.symbol)
            logging.info(f"Fetched {len(closed_orders)} closed orders for {self.symbol}.")
            return closed_orders
        except Exception as e:
            logging.error(f"Error fetching closed orders: {e}")
            return []

    def execute(self, order_list_callback=None): 
        """
        Executes the TWAP strategy over the total runtime.
        
        Parameters:
            order_list_callback (function, optional): Callback to update each executed order.
        Returns:
            List of dictionaries containing the executed orders.
        """
        logging.info(f"Starting TWAP execution for {self.iterations} iterations.")
        orders_executed = []
        for i in range(self.iterations):
            self.print_balance()
            current_price = self.get_market_price()
            if current_price is None:
                logging.error("Skipping iteration due to market data error.")
                time.sleep(self.frequency)
                continue

            order_price = current_price
            if self.order_type == "limit" and self.price_limit is not None:
                if self.side == "buy" and current_price > self.price_limit:
                    order_price = self.price_limit
                elif self.side == "sell" and current_price < self.price_limit:
                    order_price = self.price_limit

            result = self.place_order(price=order_price if self.order_type == "limit" else None)
            order_info = {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "exchange": self.exchange_name,
                "price": order_price if self.order_type == "limit" else current_price,
                "size": self.order_size,
                "side": self.side,
                "order_type": self.order_type,
                "result": result
            }
            orders_executed.append(order_info)
            if order_list_callback:
                order_list_callback(order_info)
            time.sleep(self.frequency)
        logging.info("TWAP execution completed.")
        return orders_executed

if __name__ == '__main__':
    # Standalone testing parameters.
    exchange_name = "bybit"
    api_key = "YOUR_TESTNET_API_KEY"
    api_secret = "YOUR_TESTNET_API_SECRET"
    symbol = "BTC/USDT"
    side = "buy" 
    order_type = "market"  
    total_size = 1000  
    total_run_time = 60  
    frequency = 10      
    price_limit = None   
    testnet = True       

    executor = TWAPExecutor(
        exchange_name=exchange_name,
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        side=side,
        total_size=total_size,
        total_run_time=total_run_time,
        frequency=frequency,
        testnet=testnet,
        price_limit=price_limit,
        order_type=order_type
    )

    orders = executor.execute()
    logging.info("Final executed orders:")
    for order in orders:
        logging.info(order)

    closed_orders = executor.fetch_closed_orders()
    logging.info("Closed Orders:")
    for o in closed_orders:
        logging.info(o)
