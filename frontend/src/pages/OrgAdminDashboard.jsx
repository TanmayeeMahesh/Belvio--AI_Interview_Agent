import { useEffect, useState } from "react";
import API from "../api";

export default function OrgAdminDashboard({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    API.get("/api/dashboard/org-admin")
      .then((res) => setStats(res.data))
      .catch(console.error);
      
    API.get("/api/job-openings")
      .then((res) => setJobs(res.data))
      .catch(console.error);
  }, []);

  if (!stats) return <div className="page">Loading dashboard...</div>;

  return (
    <div className="page" style={{ paddingBottom: 64 }}>
      <div className="flex-between" style={{ marginBottom: 32 }}>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>Organization Dashboard</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>High-level overview of your organization's recruitment performance.</p>
        </div>
      </div>

      <div className="grid-4" style={{ marginBottom: 48 }}>
        <div className="card stat-card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Total HRs</div>
          <div className="stat-number mt-8">{stats.hrs}</div>
        </div>

        <div className="card stat-card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Active Job Openings</div>
          <div className="stat-number mt-8">{stats.job_openings}</div>
        </div>

        <div className="card stat-card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Total Candidates</div>
          <div className="stat-number mt-8">{stats.candidates}</div>
        </div>

        <div className="card stat-card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Interviews Scheduled</div>
          <div className="stat-number mt-8">{stats.scheduled_interviews}</div>
        </div>
      </div>
      
      <div style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "var(--text)" }}>Active Job Openings</h2>
        <button className="btn-secondary btn-sm" onClick={() => onNavigate("jobs")}>View All</button>
      </div>

      <div style={{ width: "100%" }}>
        {jobs.length === 0 ? (
          <div className="card" style={{ padding: 64, textAlign: "center", color: "var(--text-secondary)" }}>
            No active job openings found.
          </div>
        ) : (
          <div className="grid-3">
            {jobs.map((job) => (
              <div 
                key={job.id} 
                className="card" 
                style={{ cursor: "pointer", transition: "transform 0.2s, box-shadow 0.2s", display: "flex", flexDirection: "column", padding: 24, minHeight: 160 }}
                onClick={() => onNavigate("jobs")}
                onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-4px)"; e.currentTarget.style.boxShadow = "0 12px 24px rgba(0,0,0,0.1)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "var(--shadow)"; }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                  <h3 style={{ margin: 0, fontSize: 18, color: "var(--primary)" }}>{job.title}</h3>
                  <span className="badge badge-completed">{job.status || "Open"}</span>
                </div>
                <p className="text-secondary" style={{ flex: 1, margin: "0 0 16px 0", fontSize: 14, lineHeight: 1.5 }}>
                  {job.description || "No description provided."}
                </p>
                <div style={{ marginTop: "auto", display: "flex", justifyContent: "flex-end" }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--primary)" }}>View Candidates &rarr;</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
