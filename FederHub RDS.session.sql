INSERT INTO organizations (name) VALUES ('Hospital A');
INSERT INTO organizations (name) VALUES ('Clinic B');

INSERT INTO users (email, role, status, organization_id)
VALUES ('admin@federhub.com', 'platform_admin', 'active', 1);

INSERT INTO users (email, role, status, organization_id)
VALUES ('ml@federhub.com', 'ml_engineer', 'active', 1);

INSERT INTO job_configurations (job_name, status)
VALUES ('Round-Test-Job', 'draft');