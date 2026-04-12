import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import client from "../api/client";
import Navbar from "../components/Navbar";

const STATUS_COLORS = {
  draft: "#94a3b8",
  scheduled: "#fbbf24",
  running: "#38bdf8",
  completed: "#4ade80",
  failed: "#f87171",
};

export default function JobDetailPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [rounds, setRounds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      client.get(`/jobs/${jobId}`),
      client.get(`/jobs/${jobId}/rounds`),
    ])
      .then(([jobRes, roundsRes]) => {
        setJob(jobRes.data);
        setRounds(roundsRes.data);
      })
      .catch(() => setError("Failed to load job details."))
      .finally(() => setLoading(false));
  }, [jobId]);

  const latestAccuracy =
    rounds.length > 0 ? rounds[rounds.length - 1].global_accuracy : null;

  const chartMax = rounds.length > 0
    ? Math.max(...rounds.map((r) => r.global_accuracy))
    : 1;

  return (
    <div style={styles.page}>
      <Navbar />
      <div style={styles.content}>
        <button style={styles.back} onClick={() => navigate("/dashboard")}>
          ← Back to Dashboard
        </button>

        {loading && <p style={styles.muted}>Loading…</p>}
        {error && <p style={styles.error}>{error}</p>}

        {job && (
          <>
            {/* Job header */}
            <div style={styles.header}>
              <div>
                <h2 style={styles.jobName}>{job.job_name}</h2>
                <p style={styles.muted}>
                  {job.round_count} rounds · {job.local_epochs} local epochs ·
                  Created {new Date(job.created_at).toLocaleString()}
                </p>
              </div>
              <span
                style={{
                  ...styles.badge,
                  background: STATUS_COLORS[job.status] || "#94a3b8",
                }}
              >
                {job.status}
              </span>
            </div>

            {/* Summary cards */}
            <div style={styles.cards}>
              <div style={styles.card}>
                <p style={styles.cardLabel}>Rounds Completed</p>
                <p style={styles.cardValue}>
                  {rounds.length} / {job.round_count}
                </p>
              </div>
              <div style={styles.card}>
                <p style={styles.cardLabel}>Latest Global Accuracy</p>
                <p style={styles.cardValue}>
                  {latestAccuracy !== null
                    ? `${(latestAccuracy * 100).toFixed(2)}%`
                    : "—"}
                </p>
              </div>
              <div style={styles.card}>
                <p style={styles.cardLabel}>Active Clients (last round)</p>
                <p style={styles.cardValue}>
                  {rounds.length > 0
                    ? rounds[rounds.length - 1].num_clients
                    : "—"}
                </p>
              </div>
            </div>

            {/* Accuracy chart */}
            <div style={styles.chartBox}>
              <h3 style={styles.chartTitle}>Global Accuracy per Round</h3>
              {rounds.length === 0 ? (
                <p style={styles.muted}>
                  No rounds completed yet. Waiting for Team Gamma's aggregation
                  engine to post results.
                </p>
              ) : (
                <div style={styles.chart}>
                  {rounds.map((r) => (
                    <div key={r.id} style={styles.barGroup}>
                      <div style={styles.barWrap}>
                        <div
                          style={{
                            ...styles.bar,
                            height: `${(r.global_accuracy / chartMax) * 160}px`,
                            background:
                              r.round_number === rounds[rounds.length - 1].round_number
                                ? "#38bdf8"
                                : "#334155",
                          }}
                          title={`${(r.global_accuracy * 100).toFixed(2)}%`}
                        />
                      </div>
                      <p style={styles.barLabel}>R{r.round_number}</p>
                      <p style={styles.barValue}>
                        {(r.global_accuracy * 100).toFixed(1)}%
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Round table */}
            {rounds.length > 0 && (
              <div style={styles.tableBox}>
                <h3 style={styles.chartTitle}>Round Details</h3>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Round</th>
                      <th style={styles.th}>Global Accuracy</th>
                      <th style={styles.th}>Clients</th>
                      <th style={styles.th}>Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rounds.map((r) => (
                      <tr key={r.id} style={styles.tr}>
                        <td style={styles.td}>{r.round_number}</td>
                        <td style={{ ...styles.td, color: "#4ade80" }}>
                          {(r.global_accuracy * 100).toFixed(2)}%
                        </td>
                        <td style={styles.td}>{r.num_clients}</td>
                        <td style={styles.td}>
                          {new Date(r.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#0f172a", fontFamily: "Arial, sans-serif" },
  content: { maxWidth: "960px", margin: "0 auto", padding: "32px 24px" },
  back: {
    background: "transparent",
    border: "1px solid #334155",
    color: "#94a3b8",
    padding: "6px 14px",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "13px",
    marginBottom: "24px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "24px",
  },
  jobName: { color: "#f1f5f9", fontSize: "22px", margin: "0 0 4px 0" },
  muted: { color: "#94a3b8", fontSize: "13px", margin: 0 },
  error: { color: "#f87171" },
  badge: {
    padding: "4px 12px",
    borderRadius: "999px",
    fontSize: "12px",
    color: "#0f172a",
    fontWeight: "bold",
  },
  cards: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", marginBottom: "24px" },
  card: {
    background: "#1e293b",
    borderRadius: "10px",
    padding: "20px",
    border: "1px solid #334155",
  },
  cardLabel: { color: "#94a3b8", fontSize: "12px", margin: "0 0 8px 0" },
  cardValue: { color: "#f1f5f9", fontSize: "24px", fontWeight: "bold", margin: 0 },
  chartBox: {
    background: "#1e293b",
    borderRadius: "10px",
    padding: "24px",
    border: "1px solid #334155",
    marginBottom: "24px",
  },
  chartTitle: { color: "#f1f5f9", fontSize: "16px", margin: "0 0 20px 0" },
  chart: { display: "flex", alignItems: "flex-end", gap: "12px", overflowX: "auto", paddingBottom: "8px" },
  barGroup: { display: "flex", flexDirection: "column", alignItems: "center", minWidth: "48px" },
  barWrap: { height: "160px", display: "flex", alignItems: "flex-end" },
  bar: { width: "32px", borderRadius: "4px 4px 0 0", transition: "height 0.3s" },
  barLabel: { color: "#94a3b8", fontSize: "11px", margin: "4px 0 0 0" },
  barValue: { color: "#cbd5e1", fontSize: "10px", margin: "2px 0 0 0" },
  tableBox: {
    background: "#1e293b",
    borderRadius: "10px",
    padding: "24px",
    border: "1px solid #334155",
  },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    color: "#94a3b8",
    fontSize: "12px",
    textAlign: "left",
    padding: "8px 12px",
    borderBottom: "1px solid #334155",
  },
  tr: { borderBottom: "1px solid #1e293b" },
  td: { color: "#cbd5e1", fontSize: "14px", padding: "10px 12px" },
};
