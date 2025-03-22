from .scheduler_twap import OrderScheduler
from .executor import OrderExecutor
from .db import init_storage
import queue
import logging

logging.basicConfig(level=logging.INFO)

# Step 1: Initialize the database schema
init_storage()

# Step 2: Create a shared queue for TWAP job execution
order_queue = queue.Queue()

# Step 3: Instantiate scheduler and executor for TWAP
order_scheduler = OrderScheduler(queue=order_queue)
order_executor = OrderExecutor(order_queue=order_queue, order_scheduler=order_scheduler)

# Step 4: Start everything
def launch_system():
    order_scheduler.start()
    order_executor.start()
