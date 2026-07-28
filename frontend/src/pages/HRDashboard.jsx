import { useEffect, useState } from "react";
import API from "../api";

export default function HRDashboard({ onOpenJob }) {
  const [stats, setStats] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [previewJob, setPreviewJob] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, jobsRes] = await Promise.all([
          API.get("/api/dashboard/hr"),
          API.get("/api/job-openings")
        ]);
        setStats(statsRes.data);
        setJobs(jobsRes.data);
      } catch (err) {
        console.error("Failed to load HR dashboard data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) return <div className="page">Loading dashboard...</div>;

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: 32 }}>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>HR Overview</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>Monitor your recruitment pipeline and interview metrics at a glance.</p>
        </div>
      </div>

      <div className="grid-3" style={{ marginBottom: 40 }}>
        <div className="card stat-card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Total Job Openings</div>
          <div className="stat-number mt-8">{stats?.total_jobs || 0}</div>
        </div>
        <div className="card stat-card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Total Candidates</div>
          <div className="stat-number mt-8">{stats?.total_candidates || 0}</div>
        </div>
        <div className="card stat-card" style={{ padding: 24 }}>
          <div className="text-secondary font-semibold" style={{ textTransform: "uppercase", fontSize: 12, letterSpacing: "0.05em" }}>Interviews Scheduled</div>
          <div className="stat-number mt-8">{stats?.total_interviews || 0}</div>
        </div>
      </div>

      <div style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "var(--text)" }}>Active Job Openings</h2>
      </div>

      <div style={{ width: "100%" }}>
        {jobs.length === 0 ? (
          <div className="card" style={{ padding: 64, textAlign: "center", color: "var(--text-secondary)" }}>
            No active job openings found. Create one in the Job Openings tab.
          </div>
        ) : (
          <div className="grid-3">
            {jobs.map((job) => (
              <div 
                key={job.id} 
                className="card" 
                style={{ cursor: "pointer", transition: "transform 0.2s, box-shadow 0.2s", display: "flex", flexDirection: "column", padding: 24, minHeight: 160 }}
                onClick={() => onOpenJob(job.id, job.title)}
                onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-4px)"; e.currentTarget.style.boxShadow = "0 12px 24px rgba(0,0,0,0.1)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "var(--shadow)"; }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                  <h3 style={{ margin: 0, fontSize: 18, color: "var(--primary)" }}>{job.title}</h3>
                  <span className="badge badge-completed">{job.status || "Open"}</span>
                </div>
                <p className="text-secondary" style={{ flex: 1, margin: "0 0 16px 0", fontSize: 14, lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                  {job.description || "No description provided."}
                </p>
                <div style={{ marginTop: "auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <button 
                    className="btn-outline btn-sm" 
                    onClick={(e) => { e.stopPropagation(); setPreviewJob(job); }}
                    style={{ color: "#3b82f6", borderColor: "rgba(59, 130, 246, 0.5)" }}
                  >
                    Preview JD
                  </button>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--primary)" }}>View Job Details &rarr;</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* JD Preview Panel */}
      {previewJob && (
        <>
          <div className="slide-over-overlay" onClick={() => setPreviewJob(null)}></div>
          <div className="slide-over-panel open">
            <div style={{ padding: "24px 32px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0, fontSize: 20 }}>Job Description: {previewJob.title}</h2>
              <button className="btn-ghost" onClick={() => setPreviewJob(null)} style={{ padding: "4px 8px", fontSize: 20 }}>&times;</button>
            </div>
            <div style={{ flex: 1, padding: 0 }}>
              <iframe 
                src={`${API.defaults.baseURL || ""}/api/documents/job/${previewJob.id}`} 
                style={{ width: "100%", height: "100%", border: "none" }}
                title="JD Preview"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
