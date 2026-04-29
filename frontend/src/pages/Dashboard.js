import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
import Navbar from "../components/Navbar";

const STATUS_COLORS = {
  draft: "#94a3b8",
  scheduled: "#fbbf24",
  running: "#38bdf8",
  completed: "#4ade80",
  failed: "#f87171",
};

const ROLE_LABELS = {
  platform_admin: "Platform Admin",
  ml_engineer: "ML Engineer",
  client_operator: "Client Operator",
};

export default function Dashboard() {
  const navigate = useNavigate();
  const storedUser = useMemo(
    () => JSON.parse(localStorage.getItem("user") || "{}"),
    []
  );
  const [user, setUser] = useState(storedUser);
  const [jobs, setJobs] = useState([]);
  const [users, setUsers] = useState([]);
  const [metricsByJob, setMetricsByJob] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const canManageJobs = user.role === "platform_admin" || user.role === "ml_engineer";
  const isAdmin = user.role === "platform_admin";
  const isClient = user.role === "client_operator";

  const loadDashboard = async () => {
    setError("");
    setLoading(true);

    try {
      const profileRes = await client.get("/auth/me");
      const profile = profileRes.data;
      const nextUser = {
        id: profile.id,
        email: profile.email,
        role: profile.role,
        status: profile.status,
      };
      setUser(nextUser);
      localStorage.setItem("user", JSON.stringify(nextUser));

      const jobsRes = await client.get("/jobs/");
      setJobs(jobsRes.data);

      const metricPairs = await Promise.all(
        jobsRes.data.map(async (job) => {
          try {
            const metricsRes = await client.get(`/jobs/${job.id}/metrics`);
            return [job.id, metricsRes.data];
          } catch {
            return [job.id, []];
          }
        })
      );
      setMetricsByJob(Object.fromEntries(metricPairs));

      if (profile.role === "platform_admin") {
        const usersRes = await client.get("/auth/users");
        setUsers(usersRes.data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startJob = async (jobId) => {
    setActionMessage("");
    try {
      const res = await client.post(`/jobs/${jobId}/start`);
      setActionMessage(res.data.message);
      setJobs((current) =>
        current.map((job) =>
          job.id === jobId ? { ...job, status: res.data.status } : job
        )
      );
    } catch (err) {
      setActionMessage(err.response?.data?.detail || "Failed to start job.");
    }
  };

  const deleteJob = async (jobId, jobName) => {
    const ok = window.confirm(`Delete job "${jobName}"? This also removes its round metrics.`);
    if (!ok) return;

    setActionMessage("");
    try {
      await client.delete(`/jobs/${jobId}`);
      setJobs((current) => current.filter((job) => job.id !== jobId));
      setMetricsByJob((current) => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
      setActionMessage(`Deleted job "${jobName}".`);
    } catch (err) {
      setActionMessage(err.response?.data?.detail || "Failed to delete job.");
    }
  };

  const updateUserStatus = async (userId, status) => {
    setActionMessage("");
    try {
      const res = await client.patch(`/auth/users/${userId}/status`, { status });
      setUsers((current) =>
        current.map((item) => (item.id === userId ? res.data : item))
      );
      setActionMessage(`Updated ${res.data.email} to ${res.data.status}.`);
    } catch (err) {
      setActionMessage(err.response?.data?.detail || "Failed to update user status.");
    }
  };

  return (
    <div style={styles.page}>
      <Navbar />
      <div style={styles.content}>
        <section style={styles.topBand}>
          <div>
            <h2 style={styles.heading}>{ROLE_LABELS[user.role] || "Dashboard"}</h2>
            <p style={styles.subtext}>{user.email}</p>
          </div>
          {canManageJobs && (
            <button style={styles.createBtn} onClick={() => navigate("/jobs/new")}>
              + Create Job
            </button>
          )}
        </section>

        {isClient && <ClientOperatorPanel />}
        {isAdmin && (
          <AdminUsersPanel users={users} onStatusChange={updateUserStatus} />
        )}

        <section style={styles.sectionHeader}>
          <h3 style={styles.sectionTitle}>
            {isClient ? "Available Federated Jobs" : "Training Jobs"}
          </h3>
          <button style={styles.refreshBtn} onClick={loadDashboard}>
            Refresh
          </button>
        </section>

        {loading && <p style={styles.muted}>Loading dashboard...</p>}
        {error && <p style={styles.error}>{error}</p>}
        {actionMessage && <p style={styles.notice}>{actionMessage}</p>}

        {!loading && jobs.length === 0 && (
          <div style={styles.emptyState}>
            <p style={styles.muted}>No jobs have been created yet.</p>
            {canManageJobs && (
              <button style={styles.createBtn} onClick={() => navigate("/jobs/new")}>
                Create your first job
              </button>
            )}
          </div>
        )}

        <div style={styles.grid}>
          {jobs.map((job) => {
            const metrics = metricsByJob[job.id] || [];
            const latestMetric = metrics[metrics.length - 1];
            const isStarted = job.status === "running" || job.status === "scheduled";

            return (
              <article key={job.id} style={styles.card}>
                <div style={styles.cardTop}>
                  <div>
                    <span style={styles.jobName}>{job.job_name}</span>
                    <p style={styles.jobId}>Job ID: {job.id}</p>
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

                <div style={styles.metaStack}>
                  <span>Created by: <strong>{job.creator_email || "Unknown"}</strong></span>
                  <span>Rounds: <strong>{job.round_count}</strong></span>
                  <span>Local epochs: <strong>{job.local_epochs}</strong></span>
                  <span>Completed rounds: <strong>{metrics.length}</strong></span>
                  <span>Participating clients: <strong>{latestMetric?.num_clients ?? "N/A"}</strong></span>
                  <span>Total samples: <strong>{latestMetric?.total_samples ?? "N/A"}</strong></span>
                </div>

                <p style={styles.cardDate}>
                  Created: {new Date(job.created_at).toLocaleString()}
                </p>

                {canManageJobs ? (
                  <div style={styles.cardActions}>
                    <button
                      style={styles.startBtn}
                      onClick={() => startJob(job.id)}
                      disabled={isStarted}
                    >
                      {isStarted ? "Started" : "Start Orchestration"}
                    </button>
                    <button
                      style={styles.deleteBtn}
                      onClick={() => deleteJob(job.id, job.job_name)}
                    >
                      Delete
                    </button>
                  </div>
                ) : (
                  <p style={styles.clientNote}>
                    Use the desktop client with the Alpha API and Gamma server to participate.
                  </p>
                )}
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ClientOperatorPanel() {
  return (
    <section style={styles.infoPanel}>
      <h3 style={styles.panelTitle}>Client Operator Workspace</h3>
      <div style={styles.operatorGrid}>
        <div>
          <span style={styles.operatorLabel}>Alpha API</span>
          <strong style={styles.operatorValue}>http://127.0.0.1:8000</strong>
        </div>
        <div>
          <span style={styles.operatorLabel}>Gamma gRPC</span>
          <strong style={styles.operatorValue}>host.docker.internal:50051</strong>
        </div>
        <div>
          <span style={styles.operatorLabel}>Local app</span>
          <strong style={styles.operatorValue}>merged/client</strong>
        </div>
      </div>
    </section>
  );
}

function AdminUsersPanel({ users, onStatusChange }) {
  return (
    <section style={styles.infoPanel}>
      <h3 style={styles.panelTitle}>User Management</h3>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Email</th>
              <th style={styles.th}>Role</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((item) => (
              <tr key={item.id}>
                <td style={styles.td}>{item.email}</td>
                <td style={styles.td}>{item.role.replace("_", " ")}</td>
                <td style={styles.td}>{item.status}</td>
                <td style={styles.tdActions}>
                  <button style={styles.smallBtn} onClick={() => onStatusChange(item.id, "active")}>Activate</button>
                  <button style={styles.smallDangerBtn} onClick={() => onStatusChange(item.id, "deactivated")}>Deactivate</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#0f172a", fontFamily: "Arial, sans-serif" },
  content: { maxWidth: "1120px", margin: "0 auto", padding: "32px 24px" },
  topBand: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "16px",
    marginBottom: "24px",
  },
  heading: { color: "#f1f5f9", fontSize: "24px", margin: 0 },
  subtext: { color: "#94a3b8", fontSize: "14px", margin: "6px 0 0" },
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
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    margin: "24px 0 16px",
  },
  sectionTitle: { color: "#e2e8f0", fontSize: "18px", margin: 0 },
  refreshBtn: {
    padding: "8px 14px",
    borderRadius: "8px",
    background: "transparent",
    color: "#cbd5e1",
    border: "1px solid #334155",
    cursor: "pointer",
  },
  muted: { color: "#94a3b8" },
  error: { color: "#f87171" },
  notice: { color: "#cbd5e1", background: "#164e63", padding: "10px 12px", borderRadius: "8px" },
  emptyState: { textAlign: "center", padding: "60px 0" },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "16px" },
  card: {
    background: "#1e293b",
    borderRadius: "8px",
    padding: "20px",
    border: "1px solid #334155",
  },
  cardTop: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px", marginBottom: "14px" },
  jobName: { color: "#f1f5f9", fontWeight: "bold", fontSize: "16px" },
  jobId: { color: "#64748b", fontSize: "12px", margin: "4px 0 0" },
  badge: {
    padding: "4px 10px",
    borderRadius: "999px",
    fontSize: "12px",
    color: "#0f172a",
    fontWeight: "bold",
    whiteSpace: "nowrap",
  },
  metaStack: { display: "grid", gap: "7px", color: "#94a3b8", fontSize: "14px", marginBottom: "12px" },
  cardDate: { color: "#64748b", fontSize: "12px", margin: 0 },
  cardActions: { display: "flex", gap: "10px", marginTop: "14px", flexWrap: "wrap" },
  startBtn: {
    padding: "9px 14px",
    borderRadius: "8px",
    background: "#4ade80",
    color: "#052e16",
    fontWeight: "bold",
    border: "none",
    cursor: "pointer",
    fontSize: "13px",
  },
  deleteBtn: {
    padding: "9px 14px",
    borderRadius: "8px",
    background: "#7f1d1d",
    color: "#fecaca",
    fontWeight: "bold",
    border: "1px solid #991b1b",
    cursor: "pointer",
    fontSize: "13px",
  },
  clientNote: { color: "#cbd5e1", fontSize: "13px", margin: "14px 0 0" },
  infoPanel: {
    background: "#1e293b",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "18px",
    marginBottom: "18px",
  },
  panelTitle: { color: "#f1f5f9", fontSize: "16px", margin: "0 0 14px" },
  operatorGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px" },
  operatorLabel: { display: "block", color: "#94a3b8", fontSize: "12px", marginBottom: "4px" },
  operatorValue: { display: "block", color: "#e2e8f0", fontSize: "14px", overflowWrap: "anywhere" },
  tableWrap: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse", color: "#cbd5e1", fontSize: "14px" },
  th: { textAlign: "left", color: "#94a3b8", borderBottom: "1px solid #334155", padding: "8px" },
  td: { borderBottom: "1px solid #334155", padding: "8px" },
  tdActions: { borderBottom: "1px solid #334155", padding: "8px", display: "flex", gap: "8px", flexWrap: "wrap" },
  smallBtn: { padding: "6px 10px", borderRadius: "6px", border: "none", background: "#38bdf8", color: "#082f49", cursor: "pointer" },
  smallDangerBtn: { padding: "6px 10px", borderRadius: "6px", border: "none", background: "#991b1b", color: "#fee2e2", cursor: "pointer" },
};
