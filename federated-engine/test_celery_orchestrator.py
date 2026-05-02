"""Tests for celery_app orchestration tasks.

Strategy
--------
We don't need a Redis broker — Celery tasks expose ``.apply()`` which
runs them synchronously and returns an ``EagerResult`` whose ``.get()``
yields the task's return value.  Combined with a tempfile-based SQLite
database (so multiple ``create_db_session()`` calls share state across
tasks), this exercises the orchestration paths fully without external
infrastructure.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from celery_app import run_federation_job, run_federation_round
from db_connector import create_db_session
from models import JobConfiguration


class TestRunFederationJob(unittest.TestCase):
    """Tests for the run_federation_job orchestration task."""

    def setUp(self):
        # tempfile-based SQLite so the task and our test share state
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_url = f"sqlite:///{self.db_path}"

        session, _ = create_db_session(self.db_url)
        # Seed a runnable job
        session.add(JobConfiguration(
            id=1,
            job_name="celery-test-job",
            round_count=3,
            local_epochs=2,
            status="draft",
        ))
        session.commit()
        session.close()

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_marks_job_running_and_returns_config(self):
        result = run_federation_job.apply(args=[1, self.db_url]).get()
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["job_id"], 1)
        self.assertEqual(result["job_name"], "celery-test-job")
        self.assertEqual(result["round_count"], 3)
        self.assertEqual(result["local_epochs"], 2)

        # Verify status was actually persisted to the DB
        verify_session, _ = create_db_session(self.db_url)
        job = verify_session.query(JobConfiguration).filter_by(id=1).first()
        self.assertEqual(job.status, "running")
        verify_session.close()

    def test_returns_failed_when_job_does_not_exist(self):
        result = run_federation_job.apply(args=[999, self.db_url]).get()
        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)
        self.assertIn("999", result["error"])

    def test_returns_metrics_array_in_result(self):
        result = run_federation_job.apply(args=[1, self.db_url]).get()
        # Newly seeded job has no metrics yet
        self.assertIn("metrics", result)
        self.assertEqual(result["metrics"], [])


class TestRunFederationRound(unittest.TestCase):
    """Tests for the run_federation_round task that records per-round metrics."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_url = f"sqlite:///{self.db_path}"

        session, _ = create_db_session(self.db_url)
        session.add(JobConfiguration(
            id=1, job_name="round-test", round_count=5, status="running"
        ))
        session.commit()
        session.close()

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_records_metric_and_returns_completed(self):
        result = run_federation_round.apply(args=[1, 1, self.db_url]).get()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["job_id"], 1)
        self.assertEqual(result["round_number"], 1)
        self.assertIn("metric_id", result)
        self.assertIsNotNone(result["metric_id"])

    def test_records_multiple_rounds_independently(self):
        for round_num in [1, 2, 3]:
            result = run_federation_round.apply(
                args=[1, round_num, self.db_url]
            ).get()
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["round_number"], round_num)


if __name__ == "__main__":
    unittest.main(verbosity=2)
