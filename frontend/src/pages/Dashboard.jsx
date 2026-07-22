import { useState, useRef, useEffect } from 'react'
import API from '../api'

const ROLE_SUGGESTIONS = [
  'Software Engineer', 'Frontend Developer', 'Backend Developer', 'Full Stack Developer',
  'Business Analyst', 'Data Scientist', 'Product Manager', 'DevOps Engineer', 'QA Engineer', 'Data Engineer'
]

function DropZone({ label, file, onChange, accept = '.pdf' }) {
  const ref = useRef()
  const [drag, setDrag] = useState(false)

  function handleDrop(e) {
    e.preventDefault(); setDrag(false)
    const f = e.dataTransfer.files[0]
    if (f) onChange(f)
  }

  return (
    <div
      onClick={() => ref.current.click()}
      onDragOver={e => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${drag ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 'var(--radius)',
        padding: '20px 16px',
        cursor: 'pointer',
        textAlign: 'center',
        background: drag ? '#f5f3ff' : 'var(--surface)',
        transition: 'all .15s',
      }}
    >
      <input ref={ref} type="file" accept={accept} style={{ display: 'none' }}
        onChange={e => e.target.files[0] && onChange(e.target.files[0])} />
      {file ? (
        <div>
          <div style={{ fontSize: 22 }}>📄</div>
          <div className="font-semibold" style={{ marginTop: 4 }}>{file.name}</div>
          <div className="text-secondary text-xs" style={{ marginTop: 2 }}>{(file.size / 1024).toFixed(0)} KB — click to replace</div>
        </div>
      ) : (
        <div>
          <div style={{ fontSize: 22, marginBottom: 6 }}>⬆️</div>
          <div className="font-semibold">{label}</div>
          <div className="text-secondary text-xs" style={{ marginTop: 2 }}>Drag & drop or click to upload PDF</div>
        </div>
      )}
    </div>
  )
}

function SkillChip({ text, variant = 'found' }) {
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 999, fontSize: 12, fontWeight: 500,
      background: variant === 'found' ? '#ecfdf5' : '#fff7ed',
      color: variant === 'found' ? '#059669' : '#ea580c',
      marginRight: 6, marginBottom: 6,
    }}>{text}</span>
  )
}

function StatCard({ label, value, accent }) {
  const colorMap = {
    purple: { bg: '#f5f3ff', text: '#4f46e5', label: '#7c3aed' },
    green:  { bg: '#ecfdf5', text: '#065f46', label: '#059669' },
    blue:   { bg: '#eff6ff', text: '#1e40af', label: '#3b82f6' },
    amber:  { bg: '#fffbeb', text: '#92400e', label: '#d97706' },
    red:    { bg: '#fef2f2', text: '#991b1b', label: '#dc2626' },
  }
  const c = colorMap[accent] || colorMap.purple
  return (
    <div className="card" style={{ padding: '14px 16px', background: c.bg }}>
      <div style={{ fontSize: 12, fontWeight: 500, color: c.label, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: c.text, lineHeight: 1 }}>
        {value ?? '—'}
      </div>
    </div>
  )
}

export default function Dashboard({ token }) {
  const [stats, setStats] = useState(null)
  const [resume, setResume] = useState(null)
  const [jd, setJd] = useState(null)
  const [role, setRole] = useState('Software Engineer')
  const [analysis, setAnalysis] = useState(null)
  const [tempFiles, setTempFiles] = useState(null)
  const [analyseLoading, setAnalyseLoading] = useState(false)
  const [analyseError, setAnalyseError] = useState('')

  const [email, setEmail] = useState('')
  const [meetingUrl, setMeetingUrl] = useState('')
  const [questionCount, setQuestionCount] = useState(12)
  const [delayMinutes, setDelayMinutes] = useState(30)
  const [scheduleLoading, setScheduleLoading] = useState(false)
  const [scheduled, setScheduled] = useState(null)
  const [scheduleError, setScheduleError] = useState('')

  const [questions, setQuestions] = useState(null)     // HR-reviewable plan (null = not generated yet)
  const [questionsLoading, setQuestionsLoading] = useState(false)
  const [questionsError, setQuestionsError] = useState('')
  const [newQ, setNewQ] = useState('')

  useEffect(() => {
    if (!token) return
    API.get('/api/hr/sessions', { headers: { authorization: `Bearer ${token}` } })
      .then(r => {
        const ss = Array.isArray(r.data) ? r.data : []
        const completed  = ss.filter(s => s.status === 'completed').length
        const scheduled  = ss.filter(s => s.status === 'scheduled').length
        const inProgress = ss.filter(s => s.status === 'in_progress').length
        setStats({ all: ss.length, completed, scheduled, inProgress, incomplete: ss.length - completed - scheduled - inProgress })
      })
      .catch(() => {})
  }, [token])

  async function handleAnalyse() {
    if (!resume && !jd) { setAnalyseError('Upload at least one document.'); return }
    setAnalyseLoading(true); setAnalyseError(''); setAnalysis(null); setScheduled(null)
    setQuestions(null); setQuestionsError('')
    try {
      const form = new FormData()
      if (resume) form.append('resume', resume)
      if (jd)     form.append('jd', jd)
      form.append('role', role)
      const { data } = await API.post('/api/analyse', form, {
        headers: { authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
      })
      setAnalysis(data.analysis)
      setTempFiles(data.tempFiles)
      if (data.analysis.candidateEmail) setEmail(data.analysis.candidateEmail)
      if (data.analysis.jobRole) setRole(data.analysis.jobRole)
    } catch (e) {
      const msg = e.response?.data?.detail
      setAnalyseError(typeof msg === 'string' ? msg : 'Analysis failed. Check server logs.')
    }
    setAnalyseLoading(false)
  }

  async function handleGenerateQuestions() {
    setQuestionsLoading(true); setQuestionsError('')
    try {
      const { data } = await API.post('/api/generate-questions', {
        analysis, role, questionCount: parseInt(questionCount), tempFiles,
      }, { headers: { authorization: `Bearer ${token}` } })
      setQuestions(Array.isArray(data.questions) ? data.questions : [])
    } catch (e) {
      const msg = e.response?.data?.detail
      setQuestionsError(typeof msg === 'string' ? msg : 'Could not generate the question plan. Check server logs.')
    }
    setQuestionsLoading(false)
  }

  function removeQuestion(idx) {
    setQuestions(qs => (qs || []).filter((_, i) => i !== idx))
  }

  function addQuestion() {
    const text = newQ.trim()
    if (!text) return
    setQuestions(qs => [...(qs || []), {
      question: text, topic: 'Custom (HR)', question_type: 'custom',
      depth: 'medium', target_skill: '', key_concepts: [],
    }])
    setNewQ('')
  }

  async function handleSchedule() {
    if (!email.trim()) { setScheduleError('Candidate email is required to send the invite.'); return }
    if (!meetingUrl.trim()) { setScheduleError('Meeting link is required.'); return }
    if (!questions || questions.length === 0) { setScheduleError('Generate and confirm the question plan first.'); return }
    setScheduleLoading(true); setScheduleError('')
    try {
      const { data } = await API.post('/api/schedule', {
        analysis, tempFiles, role,
        questionCount: parseInt(questionCount),
        questions,                              // HR-reviewed plan (server persists exactly these)
        confirmedEmail: email,
        manualMeetingLink: meetingUrl,
        delayMinutes: parseInt(delayMinutes),
      }, { headers: { authorization: `Bearer ${token}` } })
      setScheduled(data)
    } catch (e) {
      const msg = e.response?.data?.detail
      setScheduleError(typeof msg === 'string' ? msg : 'Scheduling failed. Check server logs.')
    }
    setScheduleLoading(false)
  }

  const a = analysis || {}

  return (
    <div className="page">
      <div className="page-title">Dashboard</div>

      {/* Stat cards */}
      {stats && (
        <div className="grid-5" style={{ marginBottom: 20 }}>
          <StatCard label="All"         value={stats.all}        accent="purple" />
          <StatCard label="Completed"   value={stats.completed}  accent="green" />
          <StatCard label="Scheduled"   value={stats.scheduled}  accent="blue" />
          <StatCard label="In Progress" value={stats.inProgress} accent="amber" />
          <StatCard label="Incomplete"  value={stats.incomplete} accent="red" />
        </div>
      )}

      {/* Upload + Analyse */}
      <div className="card" style={{ padding: 20, marginBottom: 20 }}>
        <div style={{ fontWeight: 600, marginBottom: 14 }}>New Interview</div>
        <div className="grid-2" style={{ marginBottom: 14 }}>
          <DropZone label="Resume (PDF)" file={resume} onChange={setResume} />
          <DropZone label="Job Description (PDF)" file={jd} onChange={setJd} />
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label>Role</label>
            <input
              type="text"
              list="role-list"
              value={role}
              onChange={e => setRole(e.target.value)}
              placeholder="e.g. Software Engineer"
            />
            <datalist id="role-list">
              {ROLE_SUGGESTIONS.map(r => <option key={r} value={r} />)}
            </datalist>
          </div>
          <button className="btn-primary" onClick={handleAnalyse} disabled={analyseLoading} style={{ height: 38, minWidth: 120 }}>
            {analyseLoading ? 'Analysing…' : 'Analyse'}
          </button>
        </div>
        {analyseError && <div className="text-danger text-sm" style={{ marginTop: 8 }}>{analyseError}</div>}
      </div>

      {/* Analysis Results */}
      {analysis && (
        <div className="card" style={{ padding: 20, marginBottom: 20 }}>
          <div style={{ fontWeight: 600, marginBottom: 14 }}>Analysis Results</div>
          <div className="grid-2" style={{ marginBottom: 14 }}>
            <div>
              <div className="text-secondary text-xs">Candidate</div>
              <div className="font-semibold">{a.candidateName || '—'}</div>
              {a.candidateEmail && <div className="text-secondary text-sm">{a.candidateEmail}</div>}
            </div>
            <div>
              <div className="text-secondary text-xs">JD Match</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="font-semibold" style={{ fontSize: 22 }}>{a.jdMatchScore ?? '—'}</span>
                {a.jdMatchScore != null && <span className="text-secondary text-sm">/ 100</span>}
              </div>
            </div>
            <div>
              <div className="text-secondary text-xs">Level Detected</div>
              <div className="font-semibold">{a.detectedLevel || '—'}</div>
              {a.levelReason && <div className="text-secondary text-xs">{a.levelReason}</div>}
            </div>
            <div>
              <div className="text-secondary text-xs">Job Role</div>
              <div className="font-semibold">{a.jobRole || role}</div>
            </div>
          </div>
          {a.analysisSummary && (
            <div className="text-secondary text-sm" style={{ marginBottom: 12, padding: '10px 12px', background: 'var(--bg)', borderRadius: 'var(--radius)' }}>
              {a.analysisSummary}
            </div>
          )}
          {(a.skills?.length > 0) && (
            <div style={{ marginBottom: 8 }}>
              <div className="text-xs text-secondary" style={{ marginBottom: 6 }}>Skills Found</div>
              <div>{(a.skills || []).map(s => <SkillChip key={s} text={s} variant="found" />)}</div>
            </div>
          )}
          {(a.missingSkills?.length > 0) && (
            <div>
              <div className="text-xs text-secondary" style={{ marginBottom: 6 }}>Missing / Gap</div>
              <div>{(a.missingSkills || []).map(s => <SkillChip key={s} text={s} variant="missing" />)}</div>
            </div>
          )}
        </div>
      )}

      {/* Schedule Form */}
      {analysis && !scheduled && (
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontWeight: 600, marginBottom: 14 }}>Schedule Interview</div>
          <div className="grid-2" style={{ marginBottom: 14 }}>
            <div>
              <label>Candidate Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="candidate@example.com" />
            </div>
            <div>
              <label>Meeting Link</label>
              <input value={meetingUrl} onChange={e => setMeetingUrl(e.target.value)} placeholder="https://teams.microsoft.com/meet/..." />
            </div>
            <div>
              <label>Questions</label>
              <input type="number" min={10} max={16} value={questionCount} onChange={e => setQuestionCount(e.target.value)} />
            </div>
            <div>
              <label>Bot joins in (minutes)</label>
              <input type="number" min={1} max={1440} value={delayMinutes} onChange={e => setDelayMinutes(e.target.value)} />
            </div>
          </div>

          {/* Step 1 — generate the plan for review (nothing is scheduled yet) */}
          {!questions && (
            <>
              {questionsError && <div className="text-danger text-sm" style={{ marginBottom: 10 }}>{questionsError}</div>}
              <button className="btn-primary" onClick={handleGenerateQuestions} disabled={questionsLoading}>
                {questionsLoading ? 'Generating plan…' : 'Generate Question Plan'}
              </button>
              <div className="text-secondary text-xs" style={{ marginTop: 8 }}>
                You'll review and edit the questions before the interview is scheduled.
              </div>
            </>
          )}

          {/* Step 2 — review / edit the plan, then confirm to schedule */}
          {questions && (
            <div style={{ marginTop: 4 }}>
              <div className="flex-between" style={{ marginBottom: 6 }}>
                <div style={{ fontWeight: 600 }}>Question Plan — review before scheduling ({questions.length})</div>
                <button className="btn-ghost btn-sm" onClick={handleGenerateQuestions} disabled={questionsLoading}>
                  {questionsLoading ? 'Regenerating…' : '↻ Regenerate'}
                </button>
              </div>
              <div className="text-secondary text-xs" style={{ marginBottom: 10 }}>
                Remove any question with ✕ or add your own with +. The interview will ask exactly these, in order.
              </div>

              {questions.map((q, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '8px 10px',
                                      border: '1px solid var(--border)', borderRadius: 'var(--radius)', marginBottom: 6 }}>
                  <div className="text-secondary text-sm" style={{ minWidth: 20, textAlign: 'right' }}>{i + 1}.</div>
                  <div style={{ flex: 1 }}>
                    <div className="text-sm">{q.question}</div>
                    <div className="text-xs text-secondary" style={{ marginTop: 2 }}>
                      {q.topic || 'General'}{q.depth ? ` · ${q.depth}` : ''}
                      {q.question_type === 'custom' ? ' · added by you' : ''}
                    </div>
                  </div>
                  <button className="btn-ghost btn-sm" title="Remove this question" onClick={() => removeQuestion(i)}
                          style={{ color: '#dc2626', fontWeight: 700, lineHeight: 1 }}>✕</button>
                </div>
              ))}

              {/* add a custom question */}
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <input value={newQ} onChange={e => setNewQ(e.target.value)} placeholder="Add a custom question…"
                       onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addQuestion() } }}
                       style={{ flex: 1 }} />
                <button className="btn-ghost" onClick={addQuestion} title="Add question"
                        style={{ minWidth: 70, fontWeight: 600 }}>+ Add</button>
              </div>

              {scheduleError && <div className="text-danger text-sm" style={{ marginTop: 12 }}>{scheduleError}</div>}
              <button className="btn-primary" onClick={handleSchedule}
                      disabled={scheduleLoading || questions.length === 0} style={{ marginTop: 12 }}>
                {scheduleLoading ? 'Scheduling…' : `Confirm & Schedule Interview (${questions.length} questions)`}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Confirmation */}
      {scheduled && (
        <div className="card" style={{ padding: 20, borderLeft: '4px solid var(--success)' }}>
          <div style={{ fontWeight: 600, color: 'var(--success)', marginBottom: 10 }}>Interview Scheduled</div>
          <div className="grid-2">
            <div>
              <div className="text-xs text-secondary">Session ID</div>
              <div style={{ fontFamily: 'monospace', fontSize: 13 }}>{scheduled.session_id}</div>
            </div>
            <div>
              <div className="text-xs text-secondary">Bot joins at</div>
              <div>{new Date(scheduled.scheduled_at + 'Z').toLocaleString()}</div>
            </div>
            <div>
              <div className="text-xs text-secondary">Questions</div>
              <div>{scheduled.questions_generated}</div>
            </div>
            <div>
              <div className="text-xs text-secondary">Email invite</div>
              <div className={scheduled.email_sent ? 'text-success' : 'text-danger'}>
                {scheduled.email_sent ? '✓ Sent' : '✗ Not sent (check email config in .env)'}
              </div>
            </div>
          </div>
          <button className="btn-ghost btn-sm" onClick={() => { setScheduled(null); setAnalysis(null); setResume(null); setJd(null); setEmail(''); setMeetingUrl(''); setQuestions(null); setNewQ('') }} style={{ marginTop: 14 }}>
            + Schedule another
          </button>
        </div>
      )}
    </div>
  )
}
