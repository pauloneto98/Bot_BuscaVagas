import os
import sys
import unittest
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.repositories import UserRepository
from app.services.job_queue import JobQueue
from app.services.worker import run_worker

class JobQueueWorkerTest(unittest.TestCase):
    def setUp(self):
        # Create a test user
        self.test_email = "worker_test@example.com"
        # Ensure clean state
        user = UserRepository.get_by_email(self.test_email)
        if user:
            UserRepository.delete(user["id"])
            
        self.user_id = UserRepository.create({
            "email": self.test_email,
            "password_hash": "dummyhash",
            "name": "Worker Test User",
            "is_admin": False,
            "is_active": True
        })

    def tearDown(self):
        if hasattr(self, "user_id") and self.user_id:
            UserRepository.delete(self.user_id)

    def test_job_lifecycle_and_worker(self):
        # 1. Test queue insertion
        job_id = JobQueue.add_job(self.user_id, "teste")
        self.assertIsNotNone(job_id)

        # 2. Check position
        pos = JobQueue.get_queue_position(self.user_id, job_id)
        self.assertEqual(pos, 1)

        # 3. Get next pending
        job = JobQueue.get_next_pending()
        self.assertEqual(job["id"], job_id)
        self.assertEqual(job["status"], "pending")

        # 4. Verify cancel works
        cancelled = JobQueue.cancel_job(job_id)
        self.assertTrue(cancelled)
        job = JobQueue.get_job_by_id(job_id)
        self.assertEqual(job["status"], "cancelled")

        # 5. Add another job and run a mock worker run
        job_id = JobQueue.add_job(self.user_id, "teste")
        
        # We start the worker in a separate thread
        worker_thread = threading.Thread(target=run_worker, daemon=True)
        worker_thread.start()

        # Wait a bit for the worker to pick up and process/fail the job
        time.sleep(3)

        # Retrieve job details
        job = JobQueue.get_job_by_id(job_id)
        # Should be processed (either running, done, or error)
        self.assertIn(job["status"], ["done", "error", "running"])

if __name__ == "__main__":
    unittest.main()
