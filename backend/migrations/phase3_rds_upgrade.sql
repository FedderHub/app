BEGIN;

-- =========================
-- USERS TABLE — Phase 3
-- =========================

-- Add username column for Beta Electron app login
ALTER TABLE users
ADD COLUMN IF NOT EXISTS username VARCHAR(255) UNIQUE;

-- =========================
-- ROUND METRICS TABLE — Phase 3
-- =========================

-- Stores per-round FedAvg results posted by Team Gamma's gRPC engine
CREATE TABLE IF NOT EXISTS round_metrics (
    id          SERIAL PRIMARY KEY,
    job_id      INTEGER NOT NULL REFERENCES job_configurations(id),
    round_number INTEGER NOT NULL,
    global_accuracy FLOAT NOT NULL,
    num_clients INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_round_metrics_job_id
    ON round_metrics(job_id);

COMMIT;
