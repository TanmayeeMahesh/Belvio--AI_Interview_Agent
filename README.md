---
title: Belvio AI Interview Agent
emoji: 🎤
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# Belvio — AI Interview Agent

**Belvio is a multi-tenant, end-to-end automated technical-interview platform.** An organization signs in, creates job openings (role cards), uploads a candidate's résumé, reviews an AI-generated question plan, and schedules an interview. A voice bot then joins the meeting, conducts the interview autonomously, and the platform produces a scored report plus a post-interview **integrity/proctoring** review.

- **Backend:** FastAPI on Hugging Face Spaces (Docker) — `hf` (prod) + `hf-staging`
- **Frontend:** React + Vite on **Vercel** (auto-deploys from GitHub `main`)
- **Voice bot:** Recall.ai · **LLMs:** Gemini → Groq (fallback stack) + a fine-tuned Flan-T5 gap-question model · **DB & Auth:** Supabase (Postgres + Auth)

> **Current release: `v2.2.0`** (multi-tenant platform). Previous: `v2.1.0` (single-tenant model integration), `v2.0.0` (proctoring baseline).

---

## What's new in v2.2.0 (this release)

- **Multi-tenant RBAC:** `SUPER_ADMIN → ORG_ADMIN → HR`, organizations, and an invite-based registration flow (a user is seeded PENDING, then sets a password on first login → ACTIVE).
- **Role cards (job openings):** the JD is uploaded **once** per role; candidates then upload a résumé only, matched against that JD.
- **HR question-review flow (the v2.1 engine, preserved):** generate a plan → HR **reviews / edits / adds / removes** questions → confirm & schedule. 30 % opening/closing + 50 % technical (17-role bank) + 20 % gap (fine-tuned model), clamped to 10–16 questions, 4 experience levels (fresher / junior / mid / senior).
- **Role selection:** 17-role dropdown + "Other (specify)" → **match nearest bank role** or **generate with AI**.
- **New React frontend** (role-based dashboards, job openings, candidates, live interviews, reports).
- **Security overhaul:** Supabase JWT signature verification (ES256 via public JWKS, HS256 fallback, fail-closed); every `/api/hr/*` endpoint is now **tenant-scoped** (an org can only read its own sessions/reports/recordings).

Full module-level docs (concurrency model, live-interview engine, data model, diagrams): **[PROJECT_REPORT.md](PROJECT_REPORT.md)**.

---

## Architecture at a glance

```
Browser ──▶ Vercel (React/Vite)  ──HTTPS──▶  HF Space (FastAPI backend)
                                                 │
      Supabase (Postgres + Auth, JWKS) ◀────────┤ RBAC, orgs, job openings, candidates
      Recall.ai (bot + live transcription) ◀────┤ scheduler → bot → live interview loop
      Gemini→Groq LLM stack + Flan-T5 gap model ◀┤ analysis, question generation, scoring
      Local CV (YuNet/SFace/YOLOX, CPU) ◀────────┘ post-interview integrity/proctoring
```

The interview lifecycle (`sessions.status`): `scheduled → in_progress → completed` (or `no_show` / `capped` / `incomplete_no_response` / `stopped`). A background **stuck-session cleaner** (runs only where `SCHEDULER_ENABLED=true`) expires never-joined interviews to `no_show` after 30 min and closes orphaned in-progress sessions after 2 h.

---

## 1. Proctoring & Integrity Reporting

Post-interview **integrity analysis** (`proctor.py`, "Mode A") runs automatically in a **background thread** after each interview (gated by `PROCTORING_ENABLED`, default on). It is **fail-safe** — it never raises into the interview flow; on any error it saves a partial/`assessed:false` result and returns. Results are written to a **decoupled `integrity_reports` table** so there is no write race with the evaluator.

It produces **two independent signals, both framed as *flags for human review*, never automated verdicts:**

**1. Transcript authenticity (text)** — a Groq `llama-3.3-70b-versatile` pass over the candidate's answers, flagging responses that read like AI-generated text read aloud. Saved immediately (fast).

**2. Video integrity (fully local, CPU-only — candidate frames never leave the server):**
- **YuNet** (face detection) + **SFace** (face recognition), via OpenCV DNN → face **presence**, **second-person** detection, and **same-person** verification across the interview.
- **YOLOX-Nano** (onnxruntime) → **phone detection**.
- Each strong event carries a **timestamp** and an embedded **evidence thumbnail**. The slower video result updates the row when ready.
- CV libraries are imported **lazily** and the models (YuNet, SFace, YOLOX-Nano ONNX) are **baked into the Docker image** at build time, so boot never depends on them and there are no cloud calls for video.

**Tunable thresholds (env vars):** frame-sample interval (`PROCTOR_FRAME_SEC`, default 3s), phone-scan interval (`PROCTOR_PHONE_SEC`, 6s), SFace same-identity cosine cutoff (`PROCTOR_SFACE_COS`), phone confidence (`PROCTOR_PHONE_CONF`), persistence minimums for 2nd-person / different-person / missing-face events (ignore brief pass-bys), camera-off threshold (face seen in < 20 % of frames), and evidence-thumbnail cap. The CPU-bound scan is serialized with a lock for the 2-vCPU tier.

**What HR sees:** the report row carries `integrity_flag` (severity `minor` / `significant`, combined from the signals), a plain-language `summary`, transcript `flagged_answers`, and video stats (`face_present_pct`, `camera_off`). The frontend **Reports** page renders an **"Integrity Review"** panel with a severity badge, the summary, flagged answers, and the video assessment. HR can also **re-run** analysis on demand via `POST /api/hr/session/{id}/analyze-integrity`.

---

## 2. Features handled (platform / integration lead)

> *This section lists the work owned in this release. Adjust attribution as needed for your write-up.*

- **Multi-tenant backend & RBAC** — organizations + `organization_users` (roles `SUPER_ADMIN / ORG_ADMIN / HR`), membership resolution, and per-endpoint role guards (`_require_role` / `_require_membership` / `_org_of`). Endpoints: dashboards, org management, HR management, job openings, candidates, interviews, documents, admin create-user / invite-admin.
- **Invite & registration flow** — `check-email` → `complete-registration` (seeds PENDING → mints the Supabase Auth login → ACTIVE).
- **Question-generation engine integration** — the 30/50/20 plan, 17-role question bank, the **fine-tuned Flan-T5 gap-question model** (frozen encoder, exact training-prompt inference, quality filter), the 10–16 clamp, 4 experience levels, and the "always fill to N" guarantee. Wired so a candidate's plan is generated from the role card's JD + résumé at review time.
- **HR review-then-schedule flow** — generate → edit/add/remove → confirm; meeting-link validation (Zoom/Meet/Teams/Webex only), question-count bounds, and a post-schedule confirmation (session id, bot-joins-at, invite status).
- **Scheduling & lifecycle** — atomic claim so multiple schedulers can't double-deploy a bot, `SCHEDULER_ENABLED` kill-switch for shared-DB safety, and the stuck-session cleaner (no-show / stuck expiry).
- **Security hardening** — Supabase **JWT signature verification** (ES256 via JWKS, HS256 fallback, fail-closed) and **tenant scoping** of the legacy `/api/hr/*` endpoints; privilege guards on user deletion; UUID validation on document endpoints.
- **Release engineering** — staging→prod deploy flow, the **backend-only HF deploy** (frontend excluded because HF rejects committed binaries; Vercel serves the UI), and version tagging (`v2.2.0`).

---

## 3. Integration — bringing the parts together

This release stitched several independently built pieces into one coherent multi-tenant product:

- **The v2.1.0 interview engine** (question generation, live voice interview loop, evaluation, PDF report) — kept **byte-identical** where possible; only `extraction.py` evolved (4 experience levels + role-card support). The whole downstream pipeline (bot deploy → live interview → scoring → report → integrity) is the proven v2.1.0 code.
- **The fine-tuned gap-question model** — hosted on a private Hugging Face model repo, downloaded once at boot and cached; prewarmed in the background so the first HR request isn't slow.
- **The multi-tenant frontend** (role-based shell: login, dashboards, orgs, HR management, job openings, candidates, interviews) — adopted as the UI, wired to the backend contract, with the v2.1 question-review flow re-homed into the candidate scheduling modal and the richer **integrity-complete report view** kept.
- **Proctoring/integrity** (§1) — surfaced end-to-end: it runs automatically after every interview and its results now appear in the HR report UI.
- **Auth & tenancy** — one Supabase project backs all environments; the frontend authenticates via Supabase, and the backend verifies tokens against Supabase's JWKS, resolving each request to an organization for isolation.

**Deployment topology:** GitHub (`main`, source of truth) → **Vercel** rebuilds the frontend on merge; the backend is pushed to **HF Spaces** (staging then prod). HF is backend-only, so the deploy tree excludes `frontend/`.

---

## Quick start (local)

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate              # Windows  (source .venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
cp .env.example .env                # fill in keys (see PROJECT_REPORT.md)
ngrok http 8000                     # public URL for Recall webhooks → NGROK_URL
$env:SCHEDULER_ENABLED="false"      # local shares the prod DB — keep the scheduler off locally
python app_full.py                  # backend on :8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev    # dashboard on :3000 (VITE_API_URL=http://localhost:8000)
```

**Auth locally:** the backend verifies tokens via Supabase's JWKS using `SUPABASE_URL` — no secret needed. If you run without Supabase reachable, set `AUTH_ALLOW_UNVERIFIED=true` (local dev only).

## Deploy an update

```bash
# Frontend: merge to GitHub main via PR → Vercel auto-deploys
git push origin feature/<branch>          # open a PR → main (protected)

# Backend → Hugging Face (backend-only tree; HF rejects committed binaries, so exclude frontend/):
git checkout -B hf-deploy feature/<branch>
git reset --soft <last-release-tag>       # e.g. v2.2.0
git rm -r --cached frontend
git commit -m "deploy backend only"
git push hf-staging hf-deploy:main        # staging first
git push hf         hf-deploy:main        # then prod
```

Prod HF Space keeps `SCHEDULER_ENABLED` true/unset (it runs the scheduler + stuck-session cleaner); staging stays `false`. No JWT secret to set — `SUPABASE_URL` drives JWKS verification.

## License

MIT
