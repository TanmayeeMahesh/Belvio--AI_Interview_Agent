import { useEffect, useState } from "react";
import API, { signedDocUrl } from "../api";

// Fallback until /api/roles loads — the 17 stored question-bank roles, in bank order.
const ROLE_SUGGESTIONS = [
  "Software Engineer", "Data Analyst", "Data Scientist", "Product Manager", "Project Manager",
  "Business Analyst", "DevOps Engineer", "UI/UX Designer", "HR Executive", "Digital Marketing Specialist",
  "Sales / Business Development Executive", "Customer Success Manager", "Finance Analyst",
  "Cybersecurity Analyst", "Frontend Developer", "Backend Developer", "Full-Stack Developer",
];

export default function JobOpenings({ onOpenJob }) {
  const [jobs, setJobs] = useState([]);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [previewJob, setPreviewJob] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [loading, setLoading] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [jdFile, setJdFile] = useState(null);

  // Role for the question bank (drives which of the 17 banks / LLM this card uses).
  const [roleSelect, setRoleSelect] = useState("Software Engineer"); // dropdown value or '__other__'
  const [customRole, setCustomRole] = useState("");                  // free-text when 'Other'
  const [otherMode, setOtherMode] = useState("match");               // 'match' (nearest bank) | 'llm'
  const [roleOptions, setRoleOptions] = useState(ROLE_SUGGESTIONS);
  const [roleInfo, setRoleInfo] = useState(null);                    // how an 'Other' role resolved
  const isOther = roleSelect === "__other__";
  const effRole = (isOther ? customRole : roleSelect).trim();
  const roleSource = isOther ? otherMode : "bank";

  useEffect(() => {
    loadJobs();
    API.get("/api/roles")
      .then((res) => setRoleOptions(Array.isArray(res.data?.roles) && res.data.roles.length ? res.data.roles : ROLE_SUGGESTIONS))
      .catch(() => {});
  }, []);

  function loadJobs() {
    API.get("/api/job-openings")
      .then((res) => {
        setJobs(res.data);
      })
      .catch(console.error);
  }

  async function createJob(e) {
    e.preventDefault();
    if (isOther && !customRole.trim()) { alert("Enter the role name for 'Other'."); return; }
    setLoading(true);
    setRoleInfo(null);
    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("description", description);
      formData.append("role", effRole || title);   // drives the question bank / LLM
      formData.append("roleSource", roleSource);    // 'bank' | 'match' | 'llm'
      if (jdFile) {
        formData.append("jd_file", jdFile);
      }

      const { data } = await API.post("/api/job-openings", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });

      setRoleInfo(data?.roleInfo || null);
      setTitle("");
      setDescription("");
      setJdFile(null);
      if (!data?.roleInfo) setIsPanelOpen(false);   // keep panel open to show a "matched X → Y" note
      loadJobs();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || "Failed to create job opening.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page" style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingBottom: 64 }}>
      <div style={{ width: "100%", maxWidth: 1600, marginBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 className="page-title" style={{ margin: 0, textAlign: "left" }}>Job Openings</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>Create and manage active job postings.</p>
        </div>
      </div>

      <div style={{ width: "100%", maxWidth: 1600 }}>
        <div className="grid-3">
          {/* Add New Post Card */}
          <div 
            className="card" 
            style={{ 
              cursor: "pointer", 
              transition: "transform 0.2s, box-shadow 0.2s", 
              display: "flex", 
              flexDirection: "column", 
              alignItems: "center", 
              justifyContent: "center",
              padding: 24, 
              minHeight: 160,
              background: "rgba(37, 99, 235, 0.03)",
              border: "2px dashed rgba(37, 99, 235, 0.2)",
              textAlign: "center"
            }}
            onClick={() => setIsPanelOpen(true)}
            onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-4px)"; e.currentTarget.style.boxShadow = "0 12px 24px rgba(0,0,0,0.1)"; e.currentTarget.style.borderColor = "var(--primary)"; e.currentTarget.style.background = "rgba(37, 99, 235, 0.08)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "var(--shadow)"; e.currentTarget.style.borderColor = "rgba(37, 99, 235, 0.2)"; e.currentTarget.style.background = "rgba(37, 99, 235, 0.03)"; }}
          >
            <div style={{ width: 48, height: 48, borderRadius: "50%", background: "rgba(37, 99, 235, 0.1)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--primary)", fontSize: 24, fontWeight: 300, marginBottom: 12 }}>
              +
            </div>
            <h3 style={{ margin: 0, fontSize: 16, color: "var(--primary)" }}>Create New Post</h3>
          </div>

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
              <p className="text-secondary" style={{ flex: 1, margin: "0 0 16px 0", fontSize: 14, lineHeight: 1.5 }}>
                {job.description || "No description provided."}
              </p>
              <div style={{ marginTop: "auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <button 
                  className="btn-secondary btn-sm" 
                  onClick={(e) => { e.stopPropagation(); setPreviewJob(job); setPreviewUrl(""); signedDocUrl("job", job.id).then(setPreviewUrl).catch(() => setPreviewUrl("")); }}
                  style={{ fontSize: 12, padding: "4px 8px" }}
                >
                  Preview JD
                </button>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--primary)" }}>View Candidates &rarr;</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Slide-Over Panel Overlay */}
      {isPanelOpen && (
        <div className="slide-over-overlay" onClick={() => setIsPanelOpen(false)}></div>
      )}
      
      {/* Slide-Over Panel */}
      <div className={`slide-over-panel ${isPanelOpen ? "open" : ""}`}>
        <div style={{ padding: "24px 32px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>Create Job Opening</h2>
          <button className="btn-ghost" onClick={() => setIsPanelOpen(false)} style={{ padding: "4px 8px", fontSize: 20 }}>&times;</button>
        </div>
        
        <div style={{ padding: 32, flex: 1, overflowY: "auto" }}>
          <form onSubmit={createJob} className="gap-20">
            <div>
              <label>Job Title</label>
              <input
                type="text"
                placeholder="e.g. Senior Software Engineer"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div>
              <label>Role (question bank)</label>
              <select value={roleSelect} onChange={(e) => { const v = e.target.value; setRoleSelect(v); if (v === "__other__") setOtherMode("match"); }}>
                {roleOptions.map((r) => <option key={r} value={r}>{r}</option>)}
                <option value="__other__">Other (specify)…</option>
              </select>
              {isOther && (
                <div style={{ marginTop: 8 }}>
                  <input type="text" value={customRole} onChange={(e) => setCustomRole(e.target.value)} placeholder="e.g. Machine Learning Engineer" />
                  <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 13 }}>
                    <label style={{ display: "flex", gap: 6, alignItems: "center", fontWeight: 400 }}>
                      <input type="radio" name="otherMode" checked={otherMode === "match"} onChange={() => setOtherMode("match")} /> Match nearest stored role
                    </label>
                    <label style={{ display: "flex", gap: 6, alignItems: "center", fontWeight: 400 }}>
                      <input type="radio" name="otherMode" checked={otherMode === "llm"} onChange={() => setOtherMode("llm")} /> Generate with AI
                    </label>
                  </div>
                  <p className="text-secondary text-xs" style={{ marginTop: 6 }}>
                    "Match" reuses the closest of our 17 question banks; "Generate with AI" writes fresh technical questions for this role.
                  </p>
                </div>
              )}
              {roleInfo && roleInfo.resolved && (
                <div className="text-secondary text-xs" style={{ marginTop: 6 }}>
                  No exact bank for "{roleInfo.requested}" — using <b>{roleInfo.resolved}</b> questions ({roleInfo.method}).
                </div>
              )}
            </div>

            <div>
              <label>Description</label>
              <textarea
                placeholder="Brief summary of the role..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                required
              />
            </div>

            <div>
              <label>Job Description (PDF)</label>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => setJdFile(e.target.files[0])}
                style={{ padding: "8px" }}
              />
              <span className="text-secondary text-xs mt-4" style={{ display: "block" }}>Upload the detailed Job Description.</span>
            </div>

            <div style={{ marginTop: 24, display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button type="button" className="btn-ghost" onClick={() => setIsPanelOpen(false)}>Cancel</button>
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? "Creating..." : "Create Job"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* JD Preview Panel */}
      {previewJob && (
        <>
          <div className="slide-over-overlay" onClick={() => { setPreviewJob(null); setPreviewUrl(""); }}></div>
          <div className="slide-over-panel open">
            <div style={{ padding: "24px 32px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0, fontSize: 20 }}>Job Description: {previewJob.title}</h2>
              <button className="btn-ghost" onClick={() => { setPreviewJob(null); setPreviewUrl(""); }} style={{ padding: "4px 8px", fontSize: 20 }}>&times;</button>
            </div>
            <div style={{ flex: 1, padding: 0 }}>
              {previewUrl ? (
                <iframe
                  src={previewUrl}
                  style={{ width: "100%", height: "100%", border: "none" }}
                  title="Job Description PDF"
                ></iframe>
              ) : (
                <div className="text-secondary" style={{ padding: 24 }}>Loading document…</div>
              )}
            </div>
          </div>
        </>
      )}

    </div>
  );
}
