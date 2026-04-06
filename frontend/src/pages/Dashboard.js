import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";
import Navbar from "../components/Navbar";

const STATUS_COLORS = {
  draft: "#94a3b8",
  scheduled: "#fbbf24",
  running: "#38bdf8",
  completed: "#4ade80",
  failed: "#f87171",
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    client
      .get("/jobs/")
      .then((res) => setJobs(res.data))
      .catch(() => setError("Failed to load jobs."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={styles.page}>
      <Navbar />
      <div style={styles.content}>
        <div style={styles.header}>
          <h2 style={styles.heading}>Training Jobs</h2>
          <button style={styles.createBtn} onClick={() => navigate("/jobs/new")}>
            + Create Job
          </button>
        </div>

        {loading && <p style={styles.muted}>Loading jobs…</p>}
        {error && <p style={styles.error}>{error}</p>}
        {!loading && jobs.length === 0 && (
          <div style={styles.emptyState}>
            <p style={styles.muted}>No jobs yet.</p>
            <button style={styles.createBtn} onClick={() => navigate("/jobs/new")}>
              Create your first job
            </button>
          </div>
        )}

        <div style={styles.grid}>
          {jobs.map((job) => (
            <div key={job.id} style={styles.card}>
              <div style={styles.cardTop}>
                <span style={styles.jobName}>{job.job_name}</span>
                <span
                  style={{
                    ...styles.badge,
                    background: STATUS_COLORS[job.status] || "#94a3b8",
                  }}
                >
                  {job.status}
                </span>
              </div>
              <div style={styles.cardMeta}>
                <span>Rounds: <strong>{job.round_count}</strong></span>
                <span>Local epochs: <strong>{job.local_epochs}</strong></span>
              </div>
              <p style={styles.cardDate}>
                Created: {new Date(job.created_at).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#0f172a", fontFamily: "Arial, sans-serif" },
  content: { maxWidth: "960px", margin: "0 auto", padding: "32px 24px" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" },
  heading: { color: "#f1f5f9", fontSize: "22px", margin: 0 },
  createBtn: {
    padding: "10px 20px",
    borderRadius: "8px",
    background: "#38bdf8",
    color: "#0f172a",
    fontWeight: "bold",
    border: "none",
    cursor: "pointer",
    fontSize: "14px",
  },
  muted: { color: "#94a3b8" },
  error: { color: "#f87171" },
  emptyState: { textAlign: "center", padding: "60px 0" },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" },
  card: {
    background: "#1e293b",
    borderRadius: "10px",
    padding: "20px",
    border: "1px solid #334155",
  },
  cardTop: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" },
  jobName: { color: "#f1f5f9", fontWeight: "bold", fontSize: "16px" },
  badge: {
    padding: "3px 10px",
    borderRadius: "999px",
    fontSize: "12px",
    color: "#0f172a",
    fontWeight: "bold",
  },
  cardMeta: { display: "flex", gap: "20px", color: "#94a3b8", fontSize: "14px", marginBottom: "8px" },
  cardDate: { color: "#475569", fontSize: "12px", margin: 0 },
};
