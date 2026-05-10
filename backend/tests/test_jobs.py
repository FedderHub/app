"""Tests for /jobs endpoints and the FedAvg aggregation pipeline."""
from __future__ import annotations

import json

import pytest

from app.auth import create_access_token


def _create_job(client, headers, **overrides):
    payload = {
        "job_name": "test-job",
        "round_count": 2,
        "local_epochs": 1,
        "expected_clients": 1,
        "weight_count": 3,
    }
    payload.update(overrides)
    r = client.post("/jobs/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _headers_for(user) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


class TestJobCRUD:
    def test_create_job_as_ml_engineer(self, client, engineer_headers):
        headers, _ = engineer_headers
        r = client.post(
            "/jobs/",
            json={
                "job_name": "phase4-run",
                "round_count": 5,
                "local_epochs": 3,
                "expected_clients": 2,
                "weight_count": 4,
            },
            headers=headers,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["job_name"] == "phase4-run"
        assert body["status"] == "draft"
        assert body["current_round"] == 0
        assert body["results_published"] is False
        assert body["round_count"] == 5
        assert body["weight_count"] == 4

    def test_create_job_as_admin(self, client, admin_headers):
        headers, _ = admin_headers
        r = client.post(
            "/jobs/", json={"job_name": "admin-job"}, headers=headers
        )
        assert r.status_code == 201

    def test_create_job_as_client_operator_forbidden(self, client, client_op_headers):
        headers, _ = client_op_headers
        r = client.post("/jobs/", json={"job_name": "x"}, headers=headers)
        assert r.status_code == 403

    def test_create_job_unauthenticated(self, client):
        r = client.post("/jobs/", json={"job_name": "x"})
        assert r.status_code == 401

    def test_list_jobs_returns_all(self, client, engineer_headers):
        headers, _ = engineer_headers
        _create_job(client, headers, job_name="A")
        _create_job(client, headers, job_name="B")
        r = client.get("/jobs/", headers=headers)
        assert r.status_code == 200
        names = [j["job_name"] for j in r.json()]
        assert set(names) == {"A", "B"}

    def test_list_jobs_includes_creator_email(self, client, engineer_headers):
        headers, user = engineer_headers
        _create_job(client, headers)
        r = client.get("/jobs/", headers=headers)
        body = r.json()
        assert body[0]["creator_email"] == user.email

    def test_get_job(self, client, engineer_headers):
        headers, _ = engineer_headers
        job = _create_job(client, headers)
        r = client.get(f"/jobs/{job['id']}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == job["id"]

    def test_get_job_not_found(self, client, engineer_headers):
        headers, _ = engineer_headers
        r = client.get("/jobs/99999", headers=headers)
        assert r.status_code == 404

    def test_delete_job_removes_it(self, client, engineer_headers):
        headers, _ = engineer_headers
        job = _create_job(client, headers)
        r = client.delete(f"/jobs/{job['id']}", headers=headers)
        assert r.status_code == 204
        assert client.get(f"/jobs/{job['id']}", headers=headers).status_code == 404

    def test_delete_job_as_client_operator_forbidden(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(client, eng_headers)
        r = client.delete(f"/jobs/{job['id']}", headers=c_headers)
        assert r.status_code == 403


class TestJobStatus:
    def test_start_job_sets_running_and_round_one(self, client, engineer_headers):
        headers, _ = engineer_headers
        job = _create_job(client, headers)
        r = client.post(f"/jobs/{job['id']}/start", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "running"

        r2 = client.get(f"/jobs/{job['id']}", headers=headers)
        assert r2.json()["current_round"] == 1

    def test_start_nonexistent_job(self, client, engineer_headers):
        headers, _ = engineer_headers
        r = client.post("/jobs/99999/start", headers=headers)
        assert r.status_code == 404

    @pytest.mark.parametrize(
        "new_status", ["draft", "scheduled", "running", "completed", "failed"]
    )
    def test_update_job_status_accepts_valid(
        self, client, engineer_headers, new_status
    ):
        headers, _ = engineer_headers
        job = _create_job(client, headers)
        r = client.patch(
            f"/jobs/{job['id']}/status?new_status={new_status}", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["status"] == new_status

    def test_update_job_status_invalid_rejected(self, client, engineer_headers):
        headers, _ = engineer_headers
        job = _create_job(client, headers)
        r = client.patch(
            f"/jobs/{job['id']}/status?new_status=quantum", headers=headers
        )
        assert r.status_code == 400


class TestClientSubmissionValidation:
    def test_submit_requires_client_role(self, client, engineer_headers):
        headers, _ = engineer_headers
        job = _create_job(client, headers)
        r = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 10, "weights": [0.1, 0.2, 0.3]},
            headers=headers,
        )
        assert r.status_code == 403

    def test_submit_when_job_not_running_rejected(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(client, eng_headers)
        r = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 10, "weights": [0.1, 0.2, 0.3]},
            headers=c_headers,
        )
        assert r.status_code == 400

    def test_submit_to_nonexistent_job(self, client, client_op_headers):
        c_headers, _ = client_op_headers
        r = client.post(
            "/jobs/99999/submissions",
            json={"sample_count": 10, "weights": [0.1, 0.2, 0.3]},
            headers=c_headers,
        )
        assert r.status_code == 404

    def test_submit_wrong_weight_count_rejected(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(client, eng_headers, weight_count=3)
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)
        r = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 10, "weights": [0.1, 0.2]},
            headers=c_headers,
        )
        assert r.status_code == 400
        assert "3 weights" in r.json()["detail"]

    def test_submit_zero_sample_count_rejected(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(client, eng_headers)
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)
        r = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 0, "weights": [0.1, 0.2, 0.3]},
            headers=c_headers,
        )
        assert r.status_code == 400

    def test_submit_empty_weights_rejected(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(client, eng_headers, weight_count=3)
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)
        r = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 10, "weights": []},
            headers=c_headers,
        )
        assert r.status_code == 400

    def test_submit_duplicate_round_rejected(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(client, eng_headers, weight_count=3, expected_clients=2)
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)
        ok = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 10, "weights": [0.1, 0.2, 0.3]},
            headers=c_headers,
        )
        assert ok.status_code == 201
        dup = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 10, "weights": [0.1, 0.2, 0.3]},
            headers=c_headers,
        )
        assert dup.status_code == 400


class TestFedAvgAggregation:
    def test_single_client_submission_triggers_aggregation(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(
            client, eng_headers, weight_count=3, expected_clients=1, round_count=2
        )
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)
        r = client.post(
            f"/jobs/{job['id']}/submissions",
            json={
                "client_label": "Hospital A",
                "sample_count": 100,
                "accuracy": 0.9,
                "loss": 0.1,
                "weights": [0.5, 0.5, 0.5],
            },
            headers=c_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["aggregation_ran"] is True
        assert body["job"]["status"] == "running"
        assert body["job"]["current_round"] == 2

    def test_two_client_aggregation_uses_weighted_average(
        self, client, engineer_headers, make_user
    ):
        eng_headers, _ = engineer_headers
        op1 = make_user(email="op1@example.com", role="client_operator")
        op2 = make_user(email="op2@example.com", role="client_operator")
        h1 = _headers_for(op1)
        h2 = _headers_for(op2)

        job = _create_job(
            client, eng_headers,
            weight_count=2, expected_clients=2, round_count=1,
        )
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)

        r1 = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 100, "weights": [1.0, 0.0]},
            headers=h1,
        )
        assert r1.status_code == 201
        assert r1.json()["aggregation_ran"] is False

        r2 = client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 300, "weights": [0.0, 1.0]},
            headers=h2,
        )
        assert r2.status_code == 201, r2.text
        body = r2.json()
        assert body["aggregation_ran"] is True
        assert body["job"]["status"] == "completed"

        m = client.get(f"/jobs/{job['id']}/metrics", headers=eng_headers)
        assert m.status_code == 200
        metrics = m.json()
        assert len(metrics) == 1
        assert metrics[0]["num_clients"] == 2
        assert metrics[0]["total_samples"] == 400
        snapshot = json.loads(metrics[0]["global_weights_snapshot"])
        assert snapshot["algorithm"] == "FedAvg"
        assert snapshot["round_number"] == 1
        assert snapshot["global_weights"] == pytest.approx([0.25, 0.75])

    def test_two_client_metrics_use_weighted_accuracy_and_loss(
        self, client, engineer_headers, make_user
    ):
        eng_headers, _ = engineer_headers
        op1 = make_user(email="opA@example.com", role="client_operator")
        op2 = make_user(email="opB@example.com", role="client_operator")
        h1 = _headers_for(op1)
        h2 = _headers_for(op2)

        job = _create_job(
            client, eng_headers,
            weight_count=2, expected_clients=2, round_count=1,
        )
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)

        client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 100, "accuracy": 0.8, "loss": 0.5,
                  "weights": [0.0, 0.0]},
            headers=h1,
        )
        client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 300, "accuracy": 1.0, "loss": 0.1,
                  "weights": [0.0, 0.0]},
            headers=h2,
        )

        m = client.get(f"/jobs/{job['id']}/metrics", headers=eng_headers).json()
        assert m[0]["accuracy"] == pytest.approx(0.95)
        assert m[0]["loss"] == pytest.approx(0.20)


class TestPublish:
    def test_publish_non_completed_job_rejected(self, client, engineer_headers):
        headers, _ = engineer_headers
        job = _create_job(client, headers)
        r = client.post(f"/jobs/{job['id']}/publish", headers=headers)
        assert r.status_code == 400

    def test_publish_completed_job_with_metrics(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(
            client, eng_headers, weight_count=2, expected_clients=1, round_count=1
        )
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)
        client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 50, "weights": [0.4, 0.6]},
            headers=c_headers,
        )
        r = client.post(f"/jobs/{job['id']}/publish", headers=eng_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["job"]["results_published"] is True
        assert body["job"]["published_at"] is not None

    def test_publish_nonexistent_job(self, client, engineer_headers):
        headers, _ = engineer_headers
        r = client.post("/jobs/99999/publish", headers=headers)
        assert r.status_code == 404

    def test_publish_as_client_operator_forbidden(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(client, eng_headers)
        r = client.post(f"/jobs/{job['id']}/publish", headers=c_headers)
        assert r.status_code == 403


class TestJobDetails:
    def test_client_cannot_view_unpublished_details(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(client, eng_headers)
        r = client.get(f"/jobs/{job['id']}/details", headers=c_headers)
        assert r.status_code == 403

    def test_engineer_can_view_unpublished_details(self, client, engineer_headers):
        eng_headers, _ = engineer_headers
        job = _create_job(client, eng_headers)
        r = client.get(f"/jobs/{job['id']}/details", headers=eng_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["job"]["id"] == job["id"]
        assert body["submissions"] == []
        assert body["metrics"] == []
        assert body["visible_to_clients"] is False

    def test_client_can_view_published_details(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(
            client, eng_headers, weight_count=2, expected_clients=1, round_count=1
        )
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)
        client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 50, "weights": [0.1, 0.2]},
            headers=c_headers,
        )
        client.post(f"/jobs/{job['id']}/publish", headers=eng_headers)

        r = client.get(f"/jobs/{job['id']}/details", headers=c_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["visible_to_clients"] is True
        for sub in body["submissions"]:
            assert sub["client_email"] == "client@example.com"


class TestJobSubmissionsList:
    def test_engineer_sees_all_submissions(
        self, client, engineer_headers, client_op_headers
    ):
        eng_headers, _ = engineer_headers
        c_headers, _ = client_op_headers
        job = _create_job(
            client, eng_headers, weight_count=2, expected_clients=1, round_count=2
        )
        client.post(f"/jobs/{job['id']}/start", headers=eng_headers)
        client.post(
            f"/jobs/{job['id']}/submissions",
            json={"sample_count": 10, "weights": [0.1, 0.1]},
            headers=c_headers,
        )
        r = client.get(f"/jobs/{job['id']}/submissions", headers=eng_headers)
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_get_metrics_for_job_with_no_rounds(self, client, engineer_headers):
        headers, _ = engineer_headers
        job = _create_job(client, headers)
        r = client.get(f"/jobs/{job['id']}/metrics", headers=headers)
        assert r.status_code == 200
        assert r.json() == []
