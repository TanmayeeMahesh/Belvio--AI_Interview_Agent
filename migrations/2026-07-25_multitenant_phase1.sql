-- Multi-tenant Phase 1 — GUARANTEE the columns the RBAC / job-opening / candidate flow needs.
-- khush-frontend applied its schema directly in Supabase (there is no DDL file on that branch),
-- so this migration is defensive + idempotent: every statement is "add column if not exists".
-- Safe to run repeatedly; it never drops or rewrites existing data. Run once in the Supabase SQL editor.
--
-- Assumes the base tables (organizations, organization_users, job_openings, candidates,
-- sessions, scheduled_interviews) already exist. Supersedes nothing; complements
-- 2026-07-24_job_openings_questions.sql (re-declares those columns idempotently too).

-- organizations: per-org email template for invites/notifications
alter table public.organizations
  add column if not exists status         text default 'active',
  add column if not exists email_template text,
  add column if not exists created_at     timestamptz default now();

-- organization_users: the RBAC membership table (SUPER_ADMIN > ORG_ADMIN > HR/RECRUITER/INTERVIEWER)
alter table public.organization_users
  add column if not exists organization_id uuid,
  add column if not exists user_id         uuid,   -- Supabase Auth id; NULL while status = PENDING
  add column if not exists email           text,
  add column if not exists name            text,
  add column if not exists role            text,   -- SUPER_ADMIN | ORG_ADMIN | HR | RECRUITER | INTERVIEWER
  add column if not exists status          text default 'PENDING',  -- PENDING | ACTIVE
  add column if not exists created_at      timestamptz default now();

-- job_openings = the "role card": JD uploaded once, 80% static question set stored per level
alter table public.job_openings
  add column if not exists organization_id uuid,
  add column if not exists title           text,
  add column if not exists description     text,
  add column if not exists jd_text         text,
  add column if not exists status          text  default 'open',
  add column if not exists role_source     text  default 'bank',   -- 'bank' | 'match' | 'llm'
  add column if not exists question_count  int   default 12,       -- clamped 10-16 at generation
  add column if not exists jd_analysis     jsonb,                  -- analyze_documents() of the JD
  add column if not exists question_sets   jsonb,                  -- { "<level>": {opening,technical,closing,gap_count} }
  add column if not exists created_at      timestamptz default now();
-- question_sets is keyed by the 4 canonical levels: fresher | junior | mid | senior.

-- candidates: resume uploaded against a job opening; JD-match analysis stored as JSON
alter table public.candidates
  add column if not exists organization_id uuid,
  add column if not exists job_opening_id  uuid,
  add column if not exists name            text,
  add column if not exists email           text,
  add column if not exists role            text,
  add column if not exists resume_text     text,
  add column if not exists analysis        jsonb,   -- analyze_documents(jd, resume) incl. detectedLevel
  add column if not exists created_at      timestamptz default now();

-- sessions / scheduled_interviews: carry the tenant + candidate link for the multi-tenant flow
alter table public.sessions
  add column if not exists organization_id uuid;

alter table public.scheduled_interviews
  add column if not exists organization_id uuid,
  add column if not exists candidate_id    uuid;

-- Helpful indexes for the org-scoped list/count queries (no-op if they already exist)
create index if not exists idx_org_users_user   on public.organization_users (user_id);
create index if not exists idx_org_users_email   on public.organization_users (lower(email));
create index if not exists idx_job_openings_org  on public.job_openings (organization_id);
create index if not exists idx_candidates_org    on public.candidates (organization_id);
create index if not exists idx_candidates_job    on public.candidates (job_opening_id);
create index if not exists idx_sched_org         on public.scheduled_interviews (organization_id);
create index if not exists idx_sched_candidate   on public.scheduled_interviews (candidate_id);
