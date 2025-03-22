# __init__.py
from .scheduler_twap import TWAPScheduler
from .db import init_db
import queue

init_db()

# Shared execution queue between scheduler and executor
execution_queue = queue.Queue()

# Instantiate scheduler FIRST
scheduler = TWAPScheduler(execution_queue=execution_queue)

# ✅ Import executor AFTER scheduler to avoid circular import
from .executor import TradeExecutor

# Now pass scheduler into the executor
executor = TradeExecutor(execution_queue=execution_queue, scheduler=scheduler)

def start_engine():
    scheduler.start()
    executor.start()
