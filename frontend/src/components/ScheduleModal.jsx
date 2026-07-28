import { useState } from "react";
import API from "../api";

// v2.1 engine flow: set count -> generate plan -> HR reviews / edits / adds / removes -> confirm & schedule.
const TYPE_LABEL = {
  introduction: "Opening", behavioral: "Opening", technical: "Technical",
  gap: "Gap", closing: "Closing", custom: "Custom",
};

// Only meeting platforms the interview bot / Recall.ai can join. A YouTube/Netflix/random URL fails this.
const MEETING_URL_RE = /^https?:\/\/(([\w-]+\.)?zoom\.us\/|meet\.google\.com\/|teams\.(microsoft|live)\.com\/|([\w-]+\.)?webex\.com\/)/i;
const isSupportedMeetingUrl = (u) => MEETING_URL_RE.test((u || "").trim());

export default function ScheduleModal({ candidate, onClose, onScheduled }) {
  const [questions, setQuestions] = useState(null);   // null = not generated yet (no auto-generate)
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [count, setCount] = useState(12);
  const [delay, setDelay] = useState(30);
  const [newQ, setNewQ] = useState("");
  const [scheduling, setScheduling] = useState(false);
  const [scheduled, setScheduled] = useState(null);   // schedule response -> confirmation panel
  const [email, setEmail] = useState(candidate.email || candidate.analysis?.candidateEmail || "");

  const analysis = candidate.analysis || {};
  const detected = (analysis.jobRole || "").trim();
  const jobRole = (candidate.role || "").trim();
  const roleMismatch =
    detected && jobRole && detected.toLowerCase() !== jobRole.toLowerCase()
      ? { detected, selected: jobRole } : null;

  async function generate() {
    const qc = parseInt(count || "12");
    if (isNaN(qc) || qc < 10 || qc > 16) { setError("Questions must be between 10 and 16."); return; }
    setLoading(true); setError("");
    try {
      const { data } = await API.post(`/api/candidate/${candidate.id}/generate-questions`, { question_count: qc });
      setQuestions(data.questions || []);
    } catch (err) {
      const d = err.response?.data?.detail;
      setError((d && (d.error || d)) || "Failed to generate questions.");
    } finally { setLoading(false); }
  }

  const updateText = (i, text) => setQuestions((qs) => qs.map((q, idx) => (idx === i ? { ...q, question: text } : q)));
  const removeQ = (i) => setQuestions((qs) => qs.filter((_, idx) => idx !== i));
  function addQ() {
    const t = newQ.trim(); if (!t) return;
    setQuestions((qs) => [...(qs || []), { question: t, question_type: "custom", topic: "Custom (HR)", depth: "medium" }]);
    setNewQ("");
  }

  async function confirmSchedule() {
    if (!email.trim()) return setError("Candidate email is required to send the invite.");
    if (!meetingUrl.trim()) return setError("A meeting link is required.");
    if (!isSupportedMeetingUrl(meetingUrl))
      return setError("Unsupported meeting link — use a Zoom, Google Meet, or Microsoft Teams link (not a YouTube or other link).");
    const clean = (questions || []).filter((q) => (q.question || "").trim());
    if (clean.length === 0) return setError("Add at least one question.");
    setScheduling(true); setError("");
    try {
      const { data } = await API.post(`/api/candidate/${candidate.id}/schedule`, {
        meeting_url: meetingUrl.trim(),
        confirmedEmail: email.trim(),
        delay_minutes: parseInt(delay || "30"),
        question_count: parseInt(count || "12"),
        questions: clean,
      });
      setScheduled(data);              // show the confirmation panel
      onScheduled && onScheduled();    // refresh the parent list in the background
    } catch (err) {
      const d = err.response?.data?.detail;
      setError(typeof d === "string" ? d : (d?.error || "Failed to schedule interview."));
    } finally { setScheduling(false); }
  }

  const meetingBad = meetingUrl.trim() && !isSupportedMeetingUrl(meetingUrl);

  return (
    <>
      <div className="slide-over-overlay" onClick={onClose}></div>
      <div className="slide-over-panel open" style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "20px 28px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 20 }}>{scheduled ? "Interview Scheduled" : "Review & Schedule"}</h2>
            <div className="text-secondary text-sm">{candidate.name} · level: {analysis.detectedLevel || "—"}</div>
          </div>
          <button className="btn-ghost" onClick={onClose} style={{ padding: "4px 8px", fontSize: 20 }}>&times;</button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "20px 28px" }}>
          {scheduled ? (
            <div className="card" style={{ padding: 20, borderLeft: "4px solid var(--primary)" }}>
              <div style={{ fontWeight: 600, color: "var(--primary)", marginBottom: 14 }}>✓ Interview Scheduled</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <div>
                  <div className="text-secondary text-xs">Bot joins at</div>
                  <div>{scheduled.scheduled_at ? new Date(scheduled.scheduled_at + "Z").toLocaleString() : "—"}</div>
                </div>
                <div>
                  <div className="text-secondary text-xs">Questions</div>
                  <div>{scheduled.questions_generated ?? "—"}</div>
                </div>
                <div>
                  <div className="text-secondary text-xs">Invite email</div>
                  <div style={{ color: scheduled.email_sent ? "#16a34a" : "#dc2626", fontWeight: 500 }}>
                    {scheduled.email_sent ? `✓ Sent to ${email || candidate.email || "candidate"}` : "✗ Not sent (check email config)"}
                  </div>
                </div>
                <div>
                  <div className="text-secondary text-xs">Status</div>
                  <div><span className="badge badge-scheduled">Scheduled</span></div>
                </div>
                <div style={{ gridColumn: "1 / -1" }}>
                  <div className="text-secondary text-xs">Session ID</div>
                  <div style={{ fontFamily: "monospace", fontSize: 12 }}>{scheduled.session_id}</div>
                </div>
              </div>
              <div className="text-secondary text-xs" style={{ marginTop: 14 }}>
                Track it in the <b>Interviews</b> tab — the bot joins the meeting at the scheduled time, and the report appears there when it's done.
              </div>
            </div>
          ) : (
            <>
              {roleMismatch && (
                <div className="text-xs" style={{ marginBottom: 14, color: "#b45309" }}>
                  ⚠️ The resume looks like <b>{roleMismatch.detected}</b>, but this job targets <b>{roleMismatch.selected}</b>. Questions follow the job's role.
                </div>
              )}

              <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap", alignItems: "flex-start" }}>
                <div style={{ flex: "1 1 220px" }}>
                  <label>Candidate Email</label>
                  <input type="email" placeholder="candidate@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
                <div style={{ flex: "1 1 220px" }}>
                  <label>Meeting Link</label>
                  <input placeholder="https://meet.google.com/..." value={meetingUrl} onChange={(e) => setMeetingUrl(e.target.value)} />
                  {meetingBad && <div className="text-xs" style={{ marginTop: 4, color: "#b45309" }}>Use a Zoom, Google Meet, or Microsoft Teams link.</div>}
                </div>
                <div>
                  <label>Questions</label>
                  <input type="number" min={10} max={16} value={count} onChange={(e) => setCount(e.target.value)} style={{ width: 80 }} />
                </div>
                <div>
                  <label>Delay (mins)</label>
                  <input type="number" min={1} max={1440} value={delay} onChange={(e) => setDelay(e.target.value)} style={{ width: 90 }} />
                </div>
              </div>

              {error && <div className="text-danger text-sm" style={{ marginBottom: 12 }}>{String(error)}</div>}

              {/* Step 1 — set the count, then generate (nothing is scheduled yet) */}
              {!questions && (
                <>
                  <button className="btn-primary" onClick={generate} disabled={loading}>
                    {loading ? "Generating plan…" : "Generate Question Plan"}
                  </button>
                  <div className="text-secondary text-xs" style={{ marginTop: 8 }}>
                    Set the number of questions (10–16) above, then generate. You'll review and edit before scheduling.
                  </div>
                </>
              )}

              {/* Step 2 — review / edit / add / remove, then confirm */}
              {questions && (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <h3 style={{ margin: 0, fontSize: 15 }}>Question Plan — review before scheduling ({questions.length})</h3>
                    <button className="btn-ghost btn-sm" onClick={generate} disabled={loading}>{loading ? "Regenerating…" : "↻ Regenerate"}</button>
                  </div>
                  <div className="text-secondary text-xs" style={{ marginBottom: 10 }}>
                    Edit any question, remove with ✕, or add your own. The interview asks exactly these, in order.
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {questions.map((q, i) => (
                      <div key={i} className="card" style={{ padding: 12, display: "flex", gap: 10, alignItems: "flex-start" }}>
                        <span className="badge badge-in_progress" style={{ marginTop: 6, whiteSpace: "nowrap" }}>{i + 1}. {TYPE_LABEL[q.question_type] || "Custom"}</span>
                        <textarea value={q.question || ""} onChange={(e) => updateText(i, e.target.value)} rows={2} placeholder="Question text…" style={{ flex: 1, resize: "vertical" }} />
                        <button onClick={() => removeQ(i)} title="Remove" className="btn-ghost btn-sm" style={{ color: "#ef4444", fontWeight: 700 }}>✕</button>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                    <input value={newQ} onChange={(e) => setNewQ(e.target.value)} placeholder="Add a custom question…" onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addQ(); } }} style={{ flex: 1 }} />
                    <button className="btn-ghost" onClick={addQ} style={{ minWidth: 70, fontWeight: 600 }}>+ Add</button>
                  </div>
                </>
              )}
            </>
          )}
        </div>

        <div style={{ padding: "16px 28px", borderTop: "1px solid var(--border)", display: "flex", justifyContent: "flex-end", gap: 12 }}>
          {scheduled ? (
            <button className="btn-primary" onClick={onClose}>Done</button>
          ) : questions ? (
            <>
              <button className="btn-ghost" onClick={onClose} disabled={scheduling}>Cancel</button>
              <button className="btn-primary" onClick={confirmSchedule} disabled={scheduling || loading || questions.length === 0}>
                {scheduling ? "Scheduling…" : `Confirm & Schedule (${questions.length})`}
              </button>
            </>
          ) : (
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
          )}
        </div>
      </div>
    </>
  );
}
