-- Multi-tenant direction: REUSE the existing job_openings table as the "role card"
-- (it already stores jd_text + jd_file_url per org). Add the columns our question-plan
-- feature needs. Run once in the Supabase SQL editor.
--
-- Supersedes 2026-07-24_job_roles.sql (do NOT run that one — job_openings is the role card).

alter table public.job_openings
  add column if not exists role_source    text  default 'bank',    -- 'bank' | 'match' | 'llm'
  add column if not exists question_count int   default 12,        -- N per interview (clamped 10-16)
  add column if not exists jd_analysis    jsonb,                    -- analyze_documents() output for the JD
  add column if not exists question_sets  jsonb;                    -- { "<level>": {opening,technical,closing,gap_count} }

-- Experience levels are the 4 bank tiers: fresher | junior (1-3) | mid (3-5) | senior (5+).
-- question_sets holds one static plan per level; each candidate's ~20% gap questions are
-- merged in at generation time. organization_id stays NOT NULL (multi-tenant).
