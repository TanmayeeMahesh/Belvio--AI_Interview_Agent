import { useEffect, useState } from "react";
import API, { signedDocUrl } from "../api";
import ScheduleModal from "../components/ScheduleModal";

export default function JobDetails({ jobId, jobName, role }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadAnalysis, setUploadAnalysis] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [filter, setFilter] = useState("all");
  const [resume, setResume] = useState(null);
  const [scheduleCandidate, setScheduleCandidate] = useState(null);
  const [stats, setStats] = useState(null);

  const filteredCandidates = candidates.filter((c) =>
    filter === "all" ? true : c.is_scheduled,
  );

  useEffect(() => {
    if (jobId) {
      loadData();
    }
  }, [jobId]);

  async function loadData() {
    try {
      setLoading(true);
      const [candRes, statsRes] = await Promise.all([
        API.get(`/api/job-openings/${jobId}/candidates`),
        API.get(`/api/job-openings/${jobId}/stats`),
      ]);
      setCandidates(
        [...candRes.data].sort(
          (a, b) => new Date(b.created_at) - new Date(a.created_at),
        ),
      );
      setStats(statsRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function createCandidate() {
    if (!resume) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("resume", resume);
      formData.append("job_opening_id", jobId);

      const { data } = await API.post("/api/candidates/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      if (data.analysis) {
        setUploadAnalysis(data.analysis);
      }

      setResume(null);
      loadData();
    } catch (err) {
      console.error(err);
      alert("Failed to upload candidate");
    } finally {
      setUploading(false);
    }
  }

  if (loading) return <div className="page">Loading Job Details...</div>;

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: 32 }}>
        <h1 className="page-title" style={{ margin: 0 }}>
          Job Details:{" "}
          <span style={{ color: "var(--primary)" }}>
            {jobName || "Loading..."}
          </span>
        </h1>
      </div>

      <div className="grid-4" style={{ marginBottom: 40 }}>
        <div
          className="card stat-card"
          style={{
            padding: 20,
            cursor: "pointer",
            border: filter === "all" ? "1px solid var(--primary)" : undefined,
          }}
          onClick={() => setFilter("all")}
        >
          <div
            className="text-secondary font-semibold"
            style={{
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.05em",
            }}
          >
            Total Candidates
          </div>
          <div className="stat-number mt-8">{stats?.total_candidates || 0}</div>
        </div>
        <div
          className="card stat-card"
          style={{
            padding: 20,
            cursor: "pointer",
            border:
              filter === "scheduled" ? "1px solid var(--primary)" : undefined,
          }}
          onClick={() => setFilter("scheduled")}
        >
          <div
            className="text-secondary font-semibold"
            style={{
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.05em",
            }}
          >
            Scheduled
          </div>
          <div className="stat-number mt-8">{stats?.scheduled || 0}</div>
        </div>
        <div className="card stat-card" style={{ padding: 20 }}>
          <div
            className="text-secondary font-semibold"
            style={{
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.05em",
            }}
          >
            In Progress
          </div>
          <div className="stat-number mt-8">{stats?.in_progress || 0}</div>
        </div>
        <div className="card stat-card" style={{ padding: 20 }}>
          <div
            className="text-secondary font-semibold"
            style={{
              textTransform: "uppercase",
              fontSize: 11,
              letterSpacing: "0.05em",
            }}
          >
            Completed
          </div>
          <div className="stat-number mt-8">{stats?.completed || 0}</div>
        </div>
      </div>

      {role !== "ORG_ADMIN" && (
        <div className="card" style={{ marginBottom: 32, padding: 24 }}>
          <h3 style={{ margin: "0 0 16px 0" }}>Add Candidate</h3>
          <div className="flex-row">
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={(e) => setResume(e.target.files[0])}
              style={{ maxWidth: 300 }}
            />
            <button
              className="btn-secondary"
              onClick={createCandidate}
              disabled={!resume || uploading}
            >
              {uploading ? "Analyzing..." : "Upload Resume"}
            </button>
          </div>
        </div>
      )}

      <div className="card">
        <div
          style={{
            padding: "24px 28px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <h2 style={{ fontSize: 18, margin: 0 }}>Candidate Pipeline</h2>
        </div>
        <div style={{ padding: 0 }}>
          {filteredCandidates.length === 0 ? (
            <div
              style={{
                padding: 32,
                textAlign: "center",
                color: "var(--text-secondary)",
              }}
            >
              No candidates match the current filter.
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Experience Level</th>
                  <th>Resume</th>
                  <th>Analysis</th>
                  <th>
                    {role === "ORG_ADMIN" ? "Status" : "Schedule Interview"}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredCandidates.map((c) => (
                  <tr key={c.id}>
                    <td className="font-semibold">{c.name}</td>
                    <td className="text-secondary text-sm">{c.email}</td>
                    <td>
                      <span className="badge badge-in_progress">{c.role}</span>
                    </td>
                    <td className="text-secondary">
                      {c.analysis?.detectedLevel || "—"}
                    </td>
                    <td>
                      <button
                        className="btn-secondary btn-sm"
                        onClick={async () => {
                          try { window.open(await signedDocUrl("candidate", c.id), "_blank"); }
                          catch { alert("Could not open resume."); }
                        }}
                        style={{ padding: "4px 10px", fontSize: 12 }}
                      >
                        📄 View Resume
                      </button>
                    </td>
                    <td>
                      {c.analysis ? (
                        <button
                          className="btn-secondary btn-sm"
                          onClick={() => setUploadAnalysis(c.analysis)}
                          style={{ padding: "4px 10px", fontSize: 12 }}
                        >
                          View Analysis
                        </button>
                      ) : (
                        <span className="text-secondary text-sm">N/A</span>
                      )}
                    </td>
                    <td>
                      {c.is_scheduled ? (
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                          }}
                        >
                          <span
                            style={{
                              fontSize: 13,
                              fontWeight: 500,
                              color: "var(--primary)",
                            }}
                          >
                            Scheduled
                          </span>
                          <span
                            style={{
                              fontSize: 12,
                              color: "var(--text-secondary)",
                            }}
                          >
                            {c.scheduled_time
                              ? new Date(c.scheduled_time).toLocaleString()
                              : ""}
                          </span>
                        </div>
                      ) : role === "ORG_ADMIN" ? (
                        <span className="badge badge-incomplete">Pending</span>
                      ) : (
                        <button
                          className="btn-primary btn-sm"
                          onClick={() => setScheduleCandidate(c)}
                          style={{ padding: "6px 16px" }}
                        >
                          Schedule Interview
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {scheduleCandidate && (
        <ScheduleModal
          candidate={scheduleCandidate}
          onClose={() => setScheduleCandidate(null)}
          onScheduled={loadData}
        />
      )}

      {uploadAnalysis && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
        >
          <div
            className="card"
            style={{
              width: "90%",
              maxWidth: 600,
              maxHeight: "90vh",
              overflowY: "auto",
              padding: 32,
            }}
          >
            <h2 style={{ margin: "0 0 8px 0" }}>Gap Analysis</h2>
            <p className="text-secondary" style={{ marginBottom: 24 }}>
              AI-generated fit assessment based on the job description.
            </p>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 16,
                marginBottom: 16,
              }}
            >
              <div
                style={{
                  background: "rgba(255,255,255,0.05)",
                  padding: 16,
                  borderRadius: 8,
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--text-secondary)",
                    textTransform: "uppercase",
                    marginBottom: 4,
                  }}
                >
                  Candidate Name & Email
                </div>
                <div style={{ fontSize: 16, fontWeight: "bold" }}>
                  {uploadAnalysis.candidateName || "Unknown"}
                </div>
                <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                  {uploadAnalysis.candidateEmail || "No Email"}
                </div>
              </div>
              <div
                style={{
                  background: "rgba(255,255,255,0.05)",
                  padding: 16,
                  borderRadius: 8,
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--text-secondary)",
                    textTransform: "uppercase",
                    marginBottom: 4,
                  }}
                >
                  Match Score
                </div>
                <div
                  style={{
                    fontSize: 24,
                    fontWeight: "bold",
                    color: "var(--primary)",
                  }}
                >
                  {uploadAnalysis.jdMatchScore || 0}/100
                </div>
              </div>
              <div
                style={{
                  background: "rgba(255,255,255,0.05)",
                  padding: 16,
                  borderRadius: 8,
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--text-secondary)",
                    textTransform: "uppercase",
                    marginBottom: 4,
                  }}
                >
                  Role
                </div>
                <div style={{ fontSize: 16, fontWeight: "500" }}>
                  {uploadAnalysis.jobRole || "—"}
                </div>
              </div>
              <div
                style={{
                  background: "rgba(255,255,255,0.05)",
                  padding: 16,
                  borderRadius: 8,
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--text-secondary)",
                    textTransform: "uppercase",
                    marginBottom: 4,
                  }}
                >
                  Experience Level
                </div>
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: "500",
                  }}
                >
                  {uploadAnalysis.detectedLevel || "—"}
                </div>
                {uploadAnalysis.levelReason && (
                  <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                    {uploadAnalysis.levelReason}
                  </div>
                )}
              </div>
            </div>

            <div
              style={{
                background: "rgba(255,255,255,0.05)",
                padding: 16,
                borderRadius: 8,
                marginBottom: 24,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  color: "var(--text-secondary)",
                  textTransform: "uppercase",
                  marginBottom: 8,
                }}
              >
                One-Line Summary
              </div>
              <div style={{ fontSize: 15, lineHeight: 1.5 }}>
                {uploadAnalysis.analysisSummary || "—"}
              </div>
            </div>

            <h3
              style={{
                fontSize: 14,
                margin: "0 0 12px 0",
                color: "var(--text-secondary)",
                textTransform: "uppercase",
              }}
            >
              Strengths / Skills Detected
            </h3>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                marginBottom: 24,
              }}
            >
              {uploadAnalysis.skills?.map((s, i) => (
                <span key={i} className="badge badge-completed">
                  {s}
                </span>
              ))}
            </div>

            <h3
              style={{
                fontSize: 14,
                margin: "0 0 12px 0",
                color: "var(--text-secondary)",
                textTransform: "uppercase",
              }}
            >
              Missing Skills / Gaps
            </h3>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                marginBottom: 32,
              }}
            >
              {uploadAnalysis.missingSkills?.length > 0 ? (
                uploadAnalysis.missingSkills.map((s, i) => (
                  <span key={i} className="badge badge-in_progress">
                    {s}
                  </span>
                ))
              ) : (
                <span className="text-secondary" style={{ fontSize: 14 }}>
                  No significant gaps found.
                </span>
              )}
            </div>

            <button
              className="btn-primary"
              onClick={() => setUploadAnalysis(null)}
              style={{ width: "100%", justifyContent: "center" }}
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
