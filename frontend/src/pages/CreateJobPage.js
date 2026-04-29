import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
import Navbar from "../components/Navbar";

export default function CreateJobPage() {
  const navigate = useNavigate();
  const user = JSON.parse(sessionStorage.getItem("user") || "{}");
  const [form, setForm] = useState({
    job_name: "",
    round_count: 5,
    local_epochs: 3,
    expected_clients: 1,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user.role === "client_operator") {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate, user.role]);

  const handleChange = (e) => {
    const value =
      e.target.type === "number" ? parseInt(e.target.value, 10) : e.target.value;
    setForm({ ...form, [e.target.name]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!form.job_name.trim()) {
      setError("Job name is required.");
      return;
    }
    if (form.round_count < 1 || form.local_epochs < 1) {
      setError("Round count and local epochs must be at least 1.");
      return;
    }
    if (form.expected_clients < 1) {
      setError("Expected clients must be at least 1.");
      return;
    }

    setLoading(true);
    try {
      await client.post("/jobs/", form);
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create job.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <Navbar />
      <div style={styles.content}>
        <div style={styles.card}>
          <h2 style={styles.heading}>Create Training Job</h2>
          <p style={styles.subtext}>
            Configure a new federated learning training job. Parameters will be
            saved to the database and passed to the orchestration engine.
          </p>

          <form onSubmit={handleSubmit} style={styles.form}>
            {/* Job Name */}
            <div style={styles.field}>
              <label style={styles.label}>Job Name</label>
              <input
                style={styles.input}
                type="text"
                name="job_name"
                value={form.job_name}
                onChange={handleChange}
                placeholder="e.g. mnist-federated-run-1"
                required
              />
              <p style={styles.hint}>A unique name to identify this training run.</p>
            </div>

            {/* Round Count */}
            <div style={styles.field}>
              <label style={styles.label}>Round Count</label>
              <input
                style={styles.input}
                type="number"
                name="round_count"
                value={form.round_count}
                onChange={handleChange}
                min={1}
                max={100}
              />
              <p style={styles.hint}>
                Number of global aggregation rounds. Each round collects updates
                from all clients and runs FedAvg.
              </p>
            </div>

            {/* Local Epochs */}
            <div style={styles.field}>
              <label style={styles.label}>Local Epochs</label>
              <input
                style={styles.input}
                type="number"
                name="local_epochs"
                value={form.local_epochs}
                onChange={handleChange}
                min={1}
                max={50}
              />
              <p style={styles.hint}>
                How many epochs each client trains locally before sending weight
                updates to the server.
              </p>
            </div>

            <div style={styles.field}>
              <label style={styles.label}>Expected Clients Per Round</label>
              <input
                style={styles.input}
                type="number"
                name="expected_clients"
                value={form.expected_clients}
                onChange={handleChange}
                min={1}
                max={25}
              />
              <p style={styles.hint}>
                Aggregation runs automatically after this many Client Operators
                submit local updates for the active round.
              </p>
            </div>

            {/* Summary preview */}
            <div style={styles.summary}>
              <span style={styles.summaryLabel}>Summary:</span>
              <span style={styles.summaryText}>
                <strong style={styles.highlight}>{form.round_count}</strong> rounds ×{" "}
                <strong style={styles.highlight}>{form.local_epochs}</strong> local epochs ×{" "}
                <strong style={styles.highlight}>{form.expected_clients}</strong> clients
              </span>
            </div>

            {error && <p style={styles.error}>{error}</p>}

            <div style={styles.actions}>
              <button
                type="button"
                style={styles.cancelBtn}
                onClick={() => navigate("/dashboard")}
              >
                Cancel
              </button>
              <button type="submit" style={styles.submitBtn} disabled={loading}>
                {loading ? "Creating…" : "Create Job"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#0f172a", fontFamily: "Arial, sans-serif" },
  content: { maxWidth: "600px", margin: "0 auto", padding: "40px 24px" },
  card: {
    background: "#1e293b",
    borderRadius: "12px",
    padding: "36px",
    border: "1px solid #334155",
  },
  heading: { color: "#f1f5f9", margin: "0 0 8px 0", fontSize: "22px" },
  subtext: { color: "#94a3b8", fontSize: "14px", marginBottom: "28px" },
  form: { display: "flex", flexDirection: "column", gap: "20px" },
  field: { display: "flex", flexDirection: "column", gap: "4px" },
  label: { color: "#cbd5e1", fontSize: "14px", fontWeight: "bold" },
  input: {
    padding: "10px 14px",
    borderRadius: "8px",
    border: "1px solid #334155",
    background: "#0f172a",
    color: "#f1f5f9",
    fontSize: "15px",
  },
  hint: { color: "#475569", fontSize: "12px", margin: "4px 0 0 0" },
  summary: {
    background: "#0f172a",
    borderRadius: "8px",
    padding: "14px 16px",
    display: "flex",
    gap: "10px",
    alignItems: "center",
    border: "1px solid #334155",
  },
  summaryLabel: { color: "#94a3b8", fontSize: "13px" },
  summaryText: { color: "#cbd5e1", fontSize: "14px" },
  highlight: { color: "#38bdf8" },
  error: { color: "#f87171", fontSize: "13px", margin: 0 },
  actions: { display: "flex", gap: "12px", justifyContent: "flex-end" },
  cancelBtn: {
    padding: "10px 20px",
    borderRadius: "8px",
    background: "transparent",
    color: "#94a3b8",
    border: "1px solid #334155",
    cursor: "pointer",
    fontSize: "14px",
  },
  submitBtn: {
    padding: "10px 24px",
    borderRadius: "8px",
    background: "#38bdf8",
    color: "#0f172a",
    fontWeight: "bold",
    border: "none",
    cursor: "pointer",
    fontSize: "14px",
  },
};
