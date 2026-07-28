-- Role cards: a JD is uploaded ONCE per role. The 80% static question set is stored PER
-- experience level and reused for every candidate under the role; only the ~20% gap questions
-- are generated per candidate. Run this once in the Supabase SQL editor.

create table if not exists job_roles (
  id             uuid primary key default gen_random_uuid(),
  owner_id       uuid not null,                 -- HR user (Supabase auth uid)
  role_name      text not null,
  role_source    text not null default 'bank',  -- 'bank' | 'match' | 'llm'
  question_count int  not null default 12,      -- N questions per interview (clamped 10-16)
  jd_text        text,
  jd_analysis    jsonb,                          -- analyze_documents() output for the JD
  question_sets  jsonb,                          -- { "<level>": {opening:[], technical:[], closing:[], gap_count:int} }
  created_at     timestamptz not null default now()
);

create index if not exists job_roles_owner_idx on job_roles (owner_id, created_at desc);

-- The FastAPI backend uses the service_role key (bypasses RLS) and scopes by owner_id in queries.
-- If the frontend ever queries this table directly (anon key + user JWT), enable RLS instead:
-- alter table job_roles enable row level security;
-- create policy job_roles_owner on job_roles for all
--   using (owner_id = auth.uid()) with check (owner_id = auth.uid());
