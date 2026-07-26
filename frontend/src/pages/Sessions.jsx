import { useState, useEffect } from "react";
import API from "../api";

const STATUS_OPTIONS = [
  "all",
  "scheduled",
  "in_progress",
  "completed",
  "incomplete",
  "no_show",
  "capped",
];
const RESULT_OPTIONS = [
  "all",
  "Strongly Recommended",
  "Recommended",
  "Needs Further Review",
  "Not Recommended",
];

function badgeClass(status) {
  if (!status) return "badge";

  const map = {
    scheduled: "badge-scheduled",
    joining_call: "badge-in_progress",
    in_waiting_room: "badge-capped",
    interviewing: "badge-in_progress",
    in_progress: "badge-in_progress",
    completed: "badge-completed",
    incomplete: "badge-incomplete",
    no_show: "badge-no_show",
    capped: "badge-capped",
    failed: "badge-error",
    stopped: "badge-error",
    error: "badge-error",
  };

  return `badge ${map[status] || "badge-capped"}`;
}

function displayStatus(status) {
  if (!status) return "—";

  const labels = {
    scheduled: "Scheduled",
    joining_call: "Joining Meeting",
    in_waiting_room: "Waiting Room",
    interviewing: "Interviewing",
    in_progress: "In Progress",
    completed: "Completed",
    failed: "Failed",
    no_show: "No Show",
    capped: "Time Limit Reached",
  };

  if (status.startsWith("incomplete")) return "Incomplete";

  return labels[status] || status;
}

function StatusBadge({ status }) {
  return <span className={badgeClass(status)}>{displayStatus(status)}</span>;
}

function RecommendationBadge({ rec }) {
  if (!rec) return null;
  const base = rec.replace(/ \(Incomplete Session\)$/, "");
  const styles = {
    "Strongly Recommended": { bg: "#ecfdf5", color: "#059669" },
    Recommended: { bg: "#eff6ff", color: "#3b82f6" },
    "Needs Further Review": { bg: "#fffbeb", color: "#d97706" },
    "Not Recommended": { bg: "#fef2f2", color: "#dc2626" },
  };
  const s = styles[base] || { bg: "#f3f4f6", color: "#6b7280" };
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 999,
        fontWeight: 500,
        fontSize: 12,
        background: s.bg,
        color: s.color,
      }}
    >
      {base}
    </span>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="flex-between" style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 600 }}>{title}</div>
          <button className="btn-ghost btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function PlanModal({ sessionId, onClose, token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    API.get(`/api/hr/session/${sessionId}`, {
      headers: { authorization: `Bearer ${token}` },
    })
      .then((r) => {
        setData(r.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [sessionId]);

  const questions = data?.questions || [];

  return (
    <Modal title="Question Plan" onClose={onClose}>
      {loading && <div className="text-secondary text-sm">Loading…</div>}
      {!loading && questions.length === 0 && (
        <div className="text-secondary text-sm">No questions found.</div>
      )}
      {questions.map((q, i) => (
        <div
          key={i}
          style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}
        >
          <div className="flex-row" style={{ marginBottom: 4 }}>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--accent)",
                minWidth: 24,
              }}
            >
              Q{i + 1}
            </span>
            <span className="badge badge-scheduled" style={{ fontSize: 11 }}>
              {q.topic || "General"}
            </span>
          </div>
          <div style={{ fontSize: 14, paddingLeft: 24 }}>
            {q.question_text || q.question}
          </div>
          {q.key_concepts?.length > 0 && (
            <div
              className="text-xs text-secondary"
              style={{ paddingLeft: 24, marginTop: 4 }}
            >
              Concepts: {(q.key_concepts || []).join(", ")}
            </div>
          )}
        </div>
      ))}
    </Modal>
  );
}

export default function Sessions({ token, onViewReport }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [resultFilter, setResultFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [planFor, setPlanFor] = useState(null);
  const [reasonFor, setReasonFor] = useState(null);

  useEffect(() => {
    fetchSessions();

    const interval = setInterval(() => {
      fetchSessions();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  async function fetchSessions() {
    setLoading(true);
    setError("");
    try {
      const { data } = await API.get("/api/hr/sessions", {
        headers: { authorization: `Bearer ${token}` },
      });
      setSessions(Array.isArray(data) ? data : []);
    } catch (e) {
      setError("Failed to load sessions.");
    }
    setLoading(false);
  }

  const uniqueRoles = [
    ...new Set(sessions.map((s) => s.role).filter(Boolean)),
  ].sort();

  const filtered = sessions.filter((s) => {
    if (statusFilter !== "all" && !(s.status || "").startsWith(statusFilter))
      return false;
    if (roleFilter !== "all" && s.role !== roleFilter) return false;
    if (resultFilter !== "all") {
      const base = (s.recommendation || "").replace(
        / \(Incomplete Session\)$/,
        "",
      );
      if (base !== resultFilter) return false;
    }
    if (search) {
      const q = search.toLowerCase();
      return (s.candidate_name || "").toLowerCase().includes(q);
    }
    return true;
  });

  function formatDateIST(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("en-US", {
        timeZone: "Asia/Kolkata",
        dateStyle: "medium",
        timeStyle: "short",
      }) + " IST";
    } catch(e) {
      return new Date(iso).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      });
    }
  }

  return (
    <div className="page">
      <div className="flex-between" style={{ marginBottom: 20 }}>
        <div className="page-title" style={{ marginBottom: 0 }}>
          Sessions
        </div>
        <button className="btn-ghost btn-sm" onClick={fetchSessions}>
          ↻ Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="card" style={{ padding: "10px 14px", marginBottom: 16 }}>
        <div
          style={{
            display: "flex",
            gap: 10,
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search candidate name…"
            style={{ height: 34, flex: "2 1 180px" }}
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ height: 34, flex: "1 1 140px", width: "auto" }}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s === "all" ? "All statuses" : s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            style={{ height: 34, flex: "1 1 150px", width: "auto" }}
          >
            <option value="all">All roles</option>
            {uniqueRoles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <select
            value={resultFilter}
            onChange={(e) => setResultFilter(e.target.value)}
            style={{ height: 34, flex: "1 1 180px", width: "auto" }}
          >
            {RESULT_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r === "all" ? "All results" : r}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="text-danger text-sm" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      <div className="card">
        {loading ? (
          <div
            style={{
              padding: 32,
              textAlign: "center",
              color: "var(--text-secondary)",
            }}
          >
            Loading…
          </div>
        ) : filtered.length === 0 ? (
          <div
            style={{
              padding: 32,
              textAlign: "center",
              color: "var(--text-secondary)",
            }}
          >
            {sessions.length === 0
              ? "No sessions yet."
              : "No sessions match the filter."}
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Role</th>
                <th>Level</th>
                <th>Scheduled Time IST</th>
                <th>Status</th>
                <th>Meeting Link</th>
                <th>Result</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => {
                let level = "—";
                if (s.analysis && s.analysis.detectedLevel) {
                  level = s.analysis.detectedLevel;
                }
                
                return (
                <tr key={s.id}>
                  <td>
                    <div className="font-semibold">
                      {s.candidate_name || "—"}
                    </div>
                    {s.candidate_email && (
                      <div className="text-xs text-secondary">
                        {s.candidate_email}
                      </div>
                    )}
                  </td>
                  <td className="text-secondary">{s.role || "—"}</td>
                  <td className="text-secondary">{level}</td>
                  <td className="text-secondary text-sm">
                    {formatDateIST(s.scheduled_at || s.created_at)}
                  </td>
                  <td>
                    <StatusBadge status={s.status} />
                  </td>
                  <td>
                    {s.meeting_url ? (
                      <a href={s.meeting_url} target="_blank" rel="noreferrer" style={{ color: "var(--primary)", textDecoration: "underline", fontSize: 13 }}>Link</a>
                    ) : (
                      <span className="text-secondary text-sm">—</span>
                    )}
                  </td>
                  <td>
                    {s.recommendation ? (
                      <RecommendationBadge rec={s.recommendation} />
                    ) : s.overall_score != null ? (
                      <span className="font-semibold text-sm">
                        {s.overall_score}/10
                      </span>
                    ) : (
                      <span className="text-secondary">—</span>
                    )}
                  </td>
                  <td>
                    <div
                      style={{
                        display: "flex",
                        gap: 6,
                        justifyContent: "flex-end",
                      }}
                    >
                      <button
                        className="btn-ghost btn-sm"
                        onClick={() => setPlanFor(s.id)}
                      >
                        Plan
                      </button>
                      {s.status &&
                        !["scheduled", "completed"].includes(s.status) && (
                          <button
                            className="btn-ghost btn-sm"
                            onClick={() => setReasonFor(s)}
                          >
                            Reason
                          </button>
                        )}
                      {(s.recommendation || s.overall_score != null) && (
                        <button
                          className="btn-primary btn-sm"
                          onClick={() => onViewReport(s.id)}
                        >
                          Report
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Plan modal */}
      {planFor && (
        <PlanModal
          sessionId={planFor}
          token={token}
          onClose={() => setPlanFor(null)}
        />
      )}

      {/* Reason modal */}
      {reasonFor && (
        <Modal title="Session Details" onClose={() => setReasonFor(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <div className="text-xs text-secondary">Candidate</div>
              <div className="font-semibold">
                {reasonFor.candidate_name || "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-secondary">Status</div>
              <StatusBadge status={reasonFor.status} />
            </div>
            <div>
              <div className="text-xs text-secondary">Questions reached</div>
              <div>
                {reasonFor.questions_reached != null ? (
                  reasonFor.questions_reached
                ) : reasonFor.status === "in_progress" ? (
                  <span className="text-secondary text-sm">
                    Session interrupted — bot left before the interview could
                    close properly
                  </span>
                ) : (
                  <span className="text-secondary text-sm">Not recorded</span>
                )}
              </div>
            </div>
            {reasonFor.status?.startsWith("incomplete") && (
              <div>
                <div className="text-xs text-secondary">Reason</div>
                <div className="text-sm">
                  {reasonFor.status === "incomplete_no_response" &&
                    "Candidate stopped responding during the interview"}
                  {reasonFor.status === "incomplete_silence" &&
                    "Ended due to prolonged silence"}
                  {!["incomplete_no_response", "incomplete_silence"].includes(
                    reasonFor.status,
                  ) && "Interview ended before all questions were completed"}
                </div>
              </div>
            )}
            {reasonFor.status === "no_show" && (
              <div>
                <div className="text-xs text-secondary">Reason</div>
                <div className="text-sm">
                  Candidate did not respond to the consent prompt within 5
                  minutes
                </div>
              </div>
            )}
            {reasonFor.status === "capped" && (
              <div>
                <div className="text-xs text-secondary">Reason</div>
                <div className="text-sm">45-minute interview cap reached</div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
