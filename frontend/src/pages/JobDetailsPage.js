import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import client from "../api/client";
import Navbar from "../components/Navbar";

export default function JobDetailsPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const user = useMemo(
    () => JSON.parse(sessionStorage.getItem("user") || "{}"),
    []
  );
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const canPublish = user.role === "platform_admin" || user.role === "ml_engineer";

  const loadDetails = async () => {
    setError("");
    setLoading(true);
    try {
      const res = await client.get(`/jobs/${jobId}/details`);
      setDetails(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load job details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const publishResults = async () => {
    setMessage("");
    try {
      const res = await client.post(`/jobs/${jobId}/publish`);
      setMessage(res.data.message);
      await loadDetails();
    } catch (err) {
      setMessage(err.response?.data?.detail || "Failed to publish results.");
    }
  };

  const downloadReport = () => {
    const blob = new Blob([JSON.stringify(details, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `federhub-job-${details.job.id}-details.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const finalMetric = details?.final_metric;
  const finalWeights = details?.final_weights || [];

  return (
    <div style={styles.page}>
      <Navbar />
      <main style={styles.content}>
        <button style={styles.backBtn} onClick={() => navigate("/dashboard")}>
          Back to Dashboard
        </button>

        {loading && <p style={styles.muted}>Loading job details...</p>}
        {error && <p style={styles.error}>{error}</p>}
        {message && <p style={styles.notice}>{message}</p>}

        {details && (
          <>
            <section style={styles.header}>
              <div>
                <p style={styles.eyebrow}>Job #{details.job.id}</p>
                <h1 style={styles.title}>{details.job.job_name}</h1>
                <p style={styles.muted}>Created by {details.job.creator_email || "Unknown"}</p>
              </div>
              <span style={styles.status}>{details.job.status}</span>
            </section>

            {details.job.description && (
              <section style={styles.panel}>
                <h2 style={styles.panelTitle}>Job Description and Feature Notes</h2>
                <p style={styles.descriptionText}>{details.job.description}</p>
                <p style={styles.muted}>
                  Required client weight vector length: <strong>{details.job.weight_count}</strong>
                </p>
              </section>
            )}

            <section style={styles.actions}>
              <button style={styles.downloadBtn} onClick={downloadReport}>
                Download Full Details
              </button>
              {canPublish && details.job.status === "completed" && !details.job.results_published && (
                <button style={styles.publishBtn} onClick={publishResults}>
                  Publish Results to Clients
                </button>
              )}
              {details.job.results_published && (
                <span style={styles.published}>Published to Client Operators</span>
              )}
            </section>

            <section style={styles.summaryGrid}>
              <SummaryCard label="Rounds Completed" value={details.metrics.length} />
              <SummaryCard label="Final Accuracy" value={formatMetric(finalMetric?.accuracy)} />
              <SummaryCard label="Final Loss" value={formatMetric(finalMetric?.loss)} />
              <SummaryCard label="Total Samples" value={finalMetric?.total_samples ?? "N/A"} />
            </section>

            <section style={styles.panel}>
              <h2 style={styles.panelTitle}>Final FedAvg Calculation</h2>
              <p style={styles.muted}>
                Each round computes a weighted average of submitted client weights using sample count as the contribution weight.
              </p>
              <div style={styles.formulaBox}>
                global_weight[i] = sum((client_samples / total_samples) * client_weight[i])
              </div>
              <h3 style={styles.smallHeading}>Final Global Weights</h3>
              <pre style={styles.weightsBox}>{finalWeights.length ? finalWeights.join(", ") : "No final weights available yet."}</pre>
            </section>

            <section style={styles.panel}>
              <h2 style={styles.panelTitle}>Round Aggregates</h2>
              <div style={styles.tableWrap}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Round</th>
                      <th style={styles.th}>Accuracy</th>
                      <th style={styles.th}>Loss</th>
                      <th style={styles.th}>Clients</th>
                      <th style={styles.th}>Samples</th>
                      <th style={styles.th}>Global Weights</th>
                    </tr>
                  </thead>
                  <tbody>
                    {details.metrics.map((metric) => (
                      <tr key={metric.id}>
                        <td style={styles.td}>{metric.round_number}</td>
                        <td style={styles.td}>{formatMetric(metric.accuracy)}</td>
                        <td style={styles.td}>{formatMetric(metric.loss)}</td>
                        <td style={styles.td}>{metric.num_clients ?? "N/A"}</td>
                        <td style={styles.td}>{metric.total_samples ?? "N/A"}</td>
                        <td style={styles.tdMono}>{(metric.global_weights || []).join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section style={styles.panel}>
              <h2 style={styles.panelTitle}>Client Round Submissions</h2>
              <div style={styles.tableWrap}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Client</th>
                      <th style={styles.th}>Email</th>
                      <th style={styles.th}>Round</th>
                      <th style={styles.th}>Samples</th>
                      <th style={styles.th}>Accuracy</th>
                      <th style={styles.th}>Loss</th>
                      <th style={styles.th}>Weights</th>
                    </tr>
                  </thead>
                  <tbody>
                    {details.submissions.map((submission) => (
                      <tr key={submission.id}>
                        <td style={styles.td}>{submission.client_label}</td>
                        <td style={styles.td}>{submission.client_email || "Hidden"}</td>
                        <td style={styles.td}>{submission.round_number}</td>
                        <td style={styles.td}>{submission.sample_count}</td>
                        <td style={styles.td}>{formatMetric(submission.accuracy)}</td>
                        <td style={styles.td}>{formatMetric(submission.loss)}</td>
                        <td style={styles.tdMono}>{submission.weights.join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function SummaryCard({ label, value }) {
  return (
    <article style={styles.summaryCard}>
      <span style={styles.summaryLabel}>{label}</span>
      <strong style={styles.summaryValue}>{value}</strong>
    </article>
  );
}

function formatMetric(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return Number(value).toFixed(4);
}

const styles = {
  page: { minHeight: "100vh", background: "#0f172a", fontFamily: "Arial, sans-serif" },
  content: { maxWidth: "1180px", margin: "0 auto", padding: "32px 24px" },
  backBtn: { background: "transparent", border: "1px solid #334155", color: "#cbd5e1", borderRadius: "8px", padding: "8px 12px", cursor: "pointer", marginBottom: "20px" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px", marginBottom: "20px" },
  eyebrow: { color: "#38bdf8", fontSize: "13px", margin: 0, fontWeight: "bold" },
  title: { color: "#f8fafc", fontSize: "32px", margin: "4px 0" },
  muted: { color: "#94a3b8" },
  error: { color: "#f87171" },
  notice: { color: "#cbd5e1", background: "#164e63", padding: "10px 12px", borderRadius: "8px" },
  status: { background: "#4ade80", color: "#052e16", borderRadius: "999px", padding: "6px 14px", fontWeight: "bold", textTransform: "capitalize" },
  actions: { display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap", marginBottom: "20px" },
  downloadBtn: { padding: "10px 14px", borderRadius: "8px", background: "#38bdf8", color: "#082f49", border: "none", fontWeight: "bold", cursor: "pointer" },
  publishBtn: { padding: "10px 14px", borderRadius: "8px", background: "#4ade80", color: "#052e16", border: "none", fontWeight: "bold", cursor: "pointer" },
  published: { color: "#bbf7d0", fontWeight: "bold" },
  summaryGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px", marginBottom: "20px" },
  summaryCard: { background: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "14px" },
  summaryLabel: { display: "block", color: "#94a3b8", fontSize: "12px", marginBottom: "6px" },
  summaryValue: { display: "block", color: "#f8fafc", fontSize: "20px" },
  panel: { background: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "18px", marginBottom: "18px" },
  panelTitle: { color: "#f8fafc", margin: "0 0 10px", fontSize: "20px" },
  descriptionText: { color: "#cbd5e1", whiteSpace: "pre-wrap", lineHeight: 1.5 },
  smallHeading: { color: "#e2e8f0", margin: "16px 0 8px", fontSize: "15px" },
  formulaBox: { background: "#0f172a", color: "#cbd5e1", border: "1px solid #334155", borderRadius: "8px", padding: "12px", fontFamily: "monospace", overflowX: "auto" },
  weightsBox: { background: "#0f172a", color: "#cbd5e1", border: "1px solid #334155", borderRadius: "8px", padding: "12px", whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
  tableWrap: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse", color: "#cbd5e1", fontSize: "14px" },
  th: { textAlign: "left", color: "#94a3b8", borderBottom: "1px solid #334155", padding: "8px" },
  td: { borderBottom: "1px solid #334155", padding: "8px", verticalAlign: "top" },
  tdMono: { borderBottom: "1px solid #334155", padding: "8px", verticalAlign: "top", fontFamily: "monospace", fontSize: "12px", minWidth: "220px" },
};
