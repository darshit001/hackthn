import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the UI runs on :5173 and every API call goes to the FastAPI backend on :8000.
const API = "http://localhost:8000";
const proxy = Object.fromEntries(["/presets", "/suggest", "/plan", "/generate", "/jobs", "/out"].map(p => [p, API]));

export default defineConfig({
  plugins: [react()],
  server: { proxy },
});
