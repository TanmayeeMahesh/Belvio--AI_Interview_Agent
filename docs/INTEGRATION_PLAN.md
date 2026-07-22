# Model Integration Plan — Fine-tuned Flan-T5 Gap Questions

**Status:** Phase 1–3 code complete on branch `feature/model-integration` (off `v2.0.0`).
Model upload, staging deploy, and the static-role feature (Phase 4) are still pending.
**Last updated:** 2026-07-22.

This doc is the durable handoff (it replaces the never-persisted `CLAUDE_PROJECT_HANDOFF.md`).

---

## Rollback baseline

- Tag **`v2.0.0`** = commit `a6eff6a` = prod baseline before this integration.
- Roll back a Space: `git push --force hf a6eff6a:main` (and `hf-staging` likewise).
- Remotes / release flow: GitHub `origin` → staging `hf-staging` → prod `hf`. Staging deploys first.

## The model (what Mehak built)

- **Base:** `google/flan-t5-base` (~248 M params, encoder-decoder).
- **Fine-tuning:** encoder **frozen** (`requires_grad=False`); only decoder + LM head trained.
  → The model is **prompt-layout sensitive**: inference MUST use the exact training prompt.
- **Task:** (role, gap analysis, resume, JD) → **5** numbered gap-focused questions.
- **Data:** `cv_jd_gap_analysis_master.xlsx`, 2,384 rows (2,145 train / 239 val).
- **Training:** AdamW, lr 3e-4, batch 2, 15 epochs, `predict_with_generate`, best-by `eval_loss`.
  max input 640 tok, max target 220 tok.
- **Eval:** ROUGE-1 **0.639**, ROUGE-2 0.460, ROUGE-L 0.482, eval_loss 0.169.
- **Artifact:** `flan_t5_finetuned_frozen_encoder_local_save/` — `model.safetensors` **990 MB**
  (+ tokenizer/config). It is a HF model dir, **not** a `.pkl`. Gitignored.
- **Training notebook:** `frontend/Final_Model_Training.ipynb`.

## Question-plan design (in `extraction.generate_question_plan`)

For a plan of size `N` (clamped to **10–16** inside extraction — every endpoint respects it):

| Segment | Share | Source | Order |
|---|---|---|---|
| Opening (intro + project/responsibilities) | ~30% total | static pool | first |
| Technical | ~50% | `question_bank.md` (14 roles × levels, round-robin) | middle |
| Gap (candidate-specific) | ~20% (2–3) | fine-tuned Flan-T5 | after technical |
| Closing (career **or** Leadership & Growth, + candidate-questions) | (part of the 30%) | static pool | last |

- **Leadership & Growth** closing variant fires when `detectedLevel` ∈ {experienced, senior, lead}.
- Gap generation is best-effort: if the model/text is missing, technical backfills and `N` still holds.

## What changed in this integration

| File | Change |
|---|---|
| `extraction.py` | Gap prompt reproduces the **exact training template**; always generate 5 (beams=4, no_repeat_ngram=3, max_length=220), take top N. HF-repo model loader + `prewarm_gap_model()`. 10–16 clamp centralized. Leadership & Growth closing variant. |
| `api_routes.py` | Both callers use the new signature; **preview endpoint now receives resume/JD** (`tempFiles`). |
| `app_full.py` | Startup warms the model in a background thread. |
| `Dockerfile` | Installs the **CPU-only torch wheel** (~200 MB vs ~2 GB CUDA) before requirements. |
| `requirements.txt` | + transformers, torch, huggingface_hub, sentencepiece. |
| `.gitignore` | Never commit the model dir / `*.safetensors` / `*.zip`. |
| `frontend/src/pages/Dashboard.jsx` | Sends `tempFiles` to `/api/generate-questions`; question count input limited to **10–16**. |
| `scripts/upload_gap_model.py` | One-time upload of the model to a private HF repo. |

## Deployment steps (Phase 1 finish → Phase 5)

1. **Upload the model once** (needs HF login):
   `python scripts/upload_gap_model.py --repo tanmayee2025/belvio-gap-flan-t5`
2. **Set Space secrets** (staging + prod): `GAP_MODEL_REPO=tanmayee2025/belvio-gap-flan-t5`,
   `HF_TOKEN=<read token>`.
3. Deploy branch to **staging** (`hf-staging`), run a full end-to-end interview, confirm gap
   questions appear in the HR preview and read well.
4. Promote to **prod** (`hf`); tag `v2.1.0`.

## Open risks / to-verify

- **Model cache persistence:** on HF the HF cache may not persist across restarts → a cold boot
  re-downloads 990 MB. If that latency is unacceptable, enable Space persistent storage or bake the
  model into the image at build (HF token as a build secret).
- **CPU latency/RAM:** flan-t5-base CPU inference ≈ a few seconds/gen; verify the Space tier RAM.
- **Tests:** `tests/test_eval.py` and `tests/test_production.py` still call the old signature — update.
- **Frontend:** confirm `tempFiles` is populated (from `/api/analyse`) before "generate question plan".

## Deferred — Phase 4 (after this ships)

- **Static-once-per-role:** store the ~80% (intro + technical) plan on the **Job Role DB record** and
  reuse it for all applicants under that role; only the ~20% gap questions are generated per candidate.
  This is a DB + UI change not yet started.
