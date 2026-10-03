# Running and testing

Always run the app on **port 8000 only**: the frontend and the API on the same port. Do not start the Vite dev server on 5173 or any other port.

```bash
cd frontend && npm run build                                    # writes frontend/dist
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
```

The UI is at http://localhost:8000. FastAPI serves `frontend/dist` after its API routes. After a frontend change, run `npm run build` again and refresh the page; the backend picks up the new files without a restart.

# UI rules

- No coloured dots, swatches or neon tiles on chips, pickers or icons. Icons stay monochrome, and a picked chip shows as the solid ink fill.
