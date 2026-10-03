# Running and testing

Run the frontend on **port 8000** and the backend on **port 9000**, and point ngrok at 8000. The Vite dev server proxies every API route to :9000 (`frontend/vite.config.js`).

```bash
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 9000
cd frontend && npm run dev                                      # Vite on :8000
ngrok http 8000
```

The UI is at http://localhost:8000 or the ngrok URL. Frontend changes reload on their own. The public URL changes every time ngrok restarts.

# UI rules

- No coloured dots, swatches or neon tiles on chips, pickers or icons. Icons stay monochrome, and a picked chip shows as the solid ink fill.
