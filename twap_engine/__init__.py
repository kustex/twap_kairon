from .scheduler_twap import OrderScheduler
from .executor import OrderExecutor
from .db import init_storage
import queue

# Initialize database schema
init_storage()

# Shared queue for order tasks
order_queue = queue.Queue()

# Instantiate scheduler and executor with shared state
order_scheduler = OrderScheduler(queue=order_queue)
order_executor = OrderExecutor(order_queue=order_queue, order_scheduler=order_scheduler)

def launch_system():
    order_scheduler.start()
    order_executor.start()
