import threading
import time
from datetime import datetime, timedelta
import logging
import uuid

logging.basicConfig(level=logging.INFO)

class ScheduledTWAPTask:
    def __init__(self, task_id, task_data):
        self.id = task_id
        self.details = task_data
        self.completed = 0
        self.next_trigger = datetime.now()

    def is_ready(self):
        return datetime.now() >= self.next_trigger

    def mark_progress(self):
        self.completed += 1
        self.next_trigger += timedelta(seconds=self.details["delay_seconds"])
        return self.completed >= self.details["num_trades"]


class OrderScheduler:
    def __init__(self, queue, interval=1):
        self.queue = queue
        self.interval = interval
        self._shutdown = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._tasks = []
        self._id_lock = threading.Lock()

    def start(self):
        logging.info("[Scheduler] OrderScheduler thread running...")
        self._thread.start()

    def stop(self):
        self._shutdown.set()
        self._thread.join()
        logging.info("[Scheduler] OrderScheduler stopped.")

    def schedule_order(self, config):
        with self._id_lock:
            task_id = str(uuid.uuid4())
            task = ScheduledTWAPTask(task_id, config)
            self._tasks.append(task)
            logging.info(f"[Scheduler] Scheduled {task_id}: {config}")
            return task_id

    def cancel_order(self, task_id):
        with self._id_lock:
            before = len(self._tasks)
            self._tasks = [t for t in self._tasks if t.id != task_id]
            after = len(self._tasks)
            logging.info(f"[Scheduler] Cancelled {task_id}. Queue size: {before} → {after}")

    def _run(self):
        while not self._shutdown.is_set():
            try:
                with self._id_lock:
                    for task in list(self._tasks):
                        if task.is_ready():
                            done = task.mark_progress()

                            payload = task.details.copy()
                            payload["id"] = task.id
                            payload["executed"] = task.completed
                            payload["next_exec"] = task.next_trigger.isoformat()

                            logging.info(f"[Scheduler] Dispatching {task.id} (step {task.completed}/{task.details['num_trades']})")
                            self.queue.put(payload)

                            if done:
                                self._tasks.remove(task)
                                logging.info(f"[Scheduler] Task {task.id} completed.")
            except Exception as err:
                logging.error(f"[Scheduler] Error: {err}")

            time.sleep(self.interval)

    def list_pending_orders(self):
        with self._id_lock:
            return [{
                "exchange": t.details["exchange"],
                "symbol": t.details["symbol"],
                "side": t.details["side"],
                "remaining_trades": t.details["num_trades"] - t.completed,
                "next_exec": t.next_trigger.isoformat(),
                "job_id": t.id
            } for t in self._tasks]