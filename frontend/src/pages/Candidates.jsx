import { useEffect, useState } from "react";
import API from "../api";

export default function Candidates({ role }) {
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [previewCandidate, setPreviewCandidate] = useState(null);
  const [creating, setCreating] = useState(false);
  const [email, setEmail] = useState("");
  const [jobId, setJobId] = useState("");
  const [resumeFile, setResumeFile] = useState(null);

  useEffect(() => {
    loadCandidates();
    loadJobs();
  }, []);

  async function loadCandidates() {
    setLoading(true);
    try {
      const { data } = await API.get("/api/candidates");
      setCandidates(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function loadJobs() {
    try {
      const { data } = await API.get("/api/job-openings");
      setJobs(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function createCandidate(e) {
    e.preventDefault();
    if (!jobId) {
      alert("Please select a Job Opening.");
      return;
    }
    if (!resumeFile) {
      alert("Please upload a Resume PDF.");
      return;
    }

    setCreating(true);
    try {
      const formData = new FormData();
      formData.append("resume", resumeFile);
      formData.append("job_opening_id", jobId);

      await API.post("/api/candidates/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });

      setJobId("");
      setResumeFile(null);
      setIsPanelOpen(false);
      loadCandidates();
    } catch (err) {
      console.error(err);
      alert("Failed to create candidate");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="page" style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingBottom: 64 }}>
      <div style={{ width: "100%", maxWidth: 1600, marginBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 className="page-title" style={{ margin: 0, textAlign: "left" }}>All Candidates</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>View and manage the global talent pool across all jobs.</p>
        </div>
      </div>

      {role !== "ORG_ADMIN" && (
        <button 
          className="btn-primary" 
          onClick={() => setIsPanelOpen(true)}
          style={{ 
            width: "100%", 
            maxWidth: 1600, 
            marginBottom: 24, 
            padding: "16px", 
            fontSize: 16, 
            fontWeight: 600, 
            display: "flex", 
            justifyContent: "center", 
            alignItems: "center", 
            gap: 8 
          }}
        >
          <span style={{ fontSize: 20, lineHeight: 1, marginTop: -2 }}>+</span>
          Add Candidate
        </button>
      )}

      <div className="card" style={{ width: "100%", maxWidth: 1600 }}>
        <div style={{ padding: 0 }}>
          {loading ? (
            <div style={{ padding: 64, textAlign: "center", color: "var(--text-secondary)" }}>
              Loading candidates...
            </div>
          ) : candidates.length === 0 ? (
            <div style={{ padding: 64, textAlign: "center", color: "var(--text-secondary)" }}>
              No candidates found across any job openings.
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Experience Level</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.id}>
                    <td className="font-semibold">{c.name}</td>
                    <td className="text-secondary">{c.email}</td>
                    <td><span className="badge badge-in_progress">{c.role || "N/A"}</span></td>
                    <td className="text-secondary">{c.analysis?.detectedLevel || "—"}</td>
                    <td>
                      {c.is_scheduled ? (
                        <span className="badge badge-scheduled">Scheduled</span>
                      ) : (
                        <span className="badge badge-incomplete">Pending</span>
                      )}
                    </td>
                    <td>
                      <button 
                        className="btn-secondary btn-sm" 
                        onClick={() => setPreviewCandidate(c)}
                        style={{ fontSize: 12, padding: "4px 8px" }}
                      >
                        Preview Resume
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Slide-Over Panel Overlay */}
      {isPanelOpen && (
        <div className="slide-over-overlay" onClick={() => setIsPanelOpen(false)}></div>
      )}
      
      {/* Slide-Over Panel */}
      <div className={`slide-over-panel ${isPanelOpen ? "open" : ""}`}>
        <div style={{ padding: "24px 32px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>Add Candidate manually</h2>
          <button className="btn-ghost" onClick={() => setIsPanelOpen(false)} style={{ padding: "4px 8px", fontSize: 20 }}>&times;</button>
        </div>
        
        <div style={{ padding: 32, flex: 1, overflowY: "auto" }}>
          <form onSubmit={createCandidate} className="gap-20">
            <div>
              <label>Assign to Job Opening</label>
              <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
                <option value="">Select Job...</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label>Resume (PDF)</label>
              <input 
                type="file" 
                accept="application/pdf"
                onChange={(e) => setResumeFile(e.target.files[0])}
              />
            </div>


            <div style={{ marginTop: 24, display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button type="button" className="btn-ghost" onClick={() => setIsPanelOpen(false)}>Cancel</button>
              <button type="submit" className="btn-primary" disabled={creating}>
                {creating ? "Adding..." : "Add Candidate"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Resume Preview Panel */}
      {previewCandidate && (
        <>
          <div className="slide-over-overlay" onClick={() => setPreviewCandidate(null)}></div>
          <div className="slide-over-panel open">
            <div style={{ padding: "24px 32px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0, fontSize: 20 }}>Resume: {previewCandidate.name}</h2>
              <button className="btn-ghost" onClick={() => setPreviewCandidate(null)} style={{ padding: "4px 8px", fontSize: 20 }}>&times;</button>
            </div>
            <div style={{ flex: 1, padding: 0 }}>
              <iframe 
                src={`${API.defaults.baseURL || ""}/api/documents/candidate/${previewCandidate.id}`} 
                style={{ width: "100%", height: "100%", border: "none" }}
                title="Resume PDF"
              ></iframe>
            </div>
          </div>
        </>
      )}

    </div>
  );
}
