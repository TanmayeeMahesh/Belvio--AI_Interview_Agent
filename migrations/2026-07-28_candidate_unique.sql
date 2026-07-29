-- Enforce ONE scheduled interview per candidate (authoritative DB backstop for the app's
-- candidate_has_interview pre-check — closes the check-then-insert race). Idempotent; safe to
-- run repeatedly. Run once in the Supabase SQL editor.
--
-- Legacy single-tenant rows have candidate_id = NULL (scheduled via /api/schedule); those are
-- left alone — the index is PARTIAL (NULLs are allowed and don't collide).

-- 1) Dedupe existing non-null duplicates: keep the most-recent row per candidate, detach the rest
--    (set candidate_id = NULL) so the unique index can be created. Non-destructive — rows remain.
WITH ranked AS (
  SELECT id,
         ROW_NUMBER() OVER (
           PARTITION BY candidate_id
           ORDER BY created_at DESC NULLS LAST, scheduled_for DESC NULLS LAST
         ) AS rn
  FROM public.scheduled_interviews
  WHERE candidate_id IS NOT NULL
)
UPDATE public.scheduled_interviews s
SET candidate_id = NULL
FROM ranked r
WHERE s.id = r.id AND r.rn > 1;

-- 2) One interview per candidate (NULLs excluded → legacy rows unaffected, multiple NULLs allowed).
CREATE UNIQUE INDEX IF NOT EXISTS uq_scheduled_interviews_candidate
  ON public.scheduled_interviews (candidate_id)
  WHERE candidate_id IS NOT NULL;
