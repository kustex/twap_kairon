# scheduler_twap.py
import threading
import time
from datetime import datetime, timedelta
import logging
import uuid

logging.basicConfig(level=logging.INFO)

class InMemoryTWAPJob:
    def __init__(self, job_id, job_data):
        self.id = job_id
        self.job = job_data
        self.executed = 0
        self.next_exec = datetime.now()

    def is_due(self):
        return datetime.now() >= self.next_exec

    def advance(self):
        self.executed += 1
        self.next_exec += timedelta(seconds=self.job["delay_seconds"])
        return self.executed >= self.job["num_trades"]

class TWAPScheduler:
    def __init__(self, execution_queue, interval_seconds=1):
        self.execution_queue = execution_queue
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self.jobs = []
        self.job_counter = 1
        self._lock = threading.Lock()

    def start(self):
        logging.info("[SCHEDULER] Starting scheduler thread...")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join()
        logging.info("[SCHEDULER] Scheduler thread stopped.")

    def add_job(self, job_data):
        with self._lock:
            job_id = str(uuid.uuid4())  # Unique ID
            new_job = InMemoryTWAPJob(job_id, job_data)
            self.jobs.append(new_job)
            logging.info(f"[SCHEDULER] Job {job_id} added: {job_data}")
            return job_id

    def remove_job_by_id(self, job_id):
        with self._lock:
            before = len(self.jobs)
            self.jobs = [job for job in self.jobs if job.id != job_id]
            after = len(self.jobs)
            logging.info(f"[SCHEDULER] Job {job_id} removed due to error. {before} → {after} jobs.")

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    for job in list(self.jobs):
                        if job.is_due():
                            finished = job.advance()
                            
                            job_dict = job.job.copy()
                            job_dict["id"] = job.id
                            job_dict["executed"] = job.executed
                            job_dict["next_exec"] = job.next_exec.isoformat()

                            logging.info(f"[SCHEDULER] Dispatching job {job.id} (trade {job_dict['executed']}/{job.job['num_trades']}) to executor")
                            self.execution_queue.put(job_dict)

                            if finished:
                                self.jobs.remove(job)
                                logging.info(f"[SCHEDULER] Job {job.id} complete and removed from memory.")

            except Exception as e:
                logging.error(f"[SCHEDULER] Error in loop: {e}")

            time.sleep(self.interval_seconds)

    def get_active_jobs(self):
        with self._lock:
            return [{
                "exchange": job.job["exchange"],
                "symbol": job.job["symbol"],
                "side": job.job["side"],
                "remaining_trades": job.job["num_trades"] - job.executed,
                "next_exec": job.next_exec.isoformat()
            } for job in self.jobs]
