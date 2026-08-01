

# Belvio — AI Interview Agent

An end-to-end automated technical interview platform. Upload a résumé and job description, and Belvio handles everything — candidate analysis, question generation, email invite, a live AI-conducted voice interview, scoring, and a PDF report — autonomously.

- **Backend:** FastAPI on Hugging Face Spaces (Docker)
- **Frontend:** React + Vite on Vercel
- **Voice bot:** Recall.ai · **LLMs:** Groq / Gemini / Claude · **DB & Auth:** Supabase

## 📄 Full documentation

**See [PROJECT_REPORT.md](PROJECT_REPORT.md)** for the complete report — architecture, how every module works, the concurrency model, the live interview engine, scoring, the deployment history (what we tested and why we changed it), the data model, environment variables, run/deploy steps, and diagrams.

## Quick start (local)

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate              # Windows  (source .venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
cp .env.example .env                # fill in keys (see PROJECT_REPORT.md §13)
ngrok http 8000                     # public URL for Recall webhooks → NGROK_URL
python app_full.py                  # backend on :8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev    # dashboard on :3000
```

## Deploy an update

```bash
git add <files> && git commit -m "..."
git push origin main                # GitHub (source of truth)
git push hf main                    # Hugging Face (auto-rebuilds the container)
# Vercel auto-deploys the frontend on push
```

## License

MIT
