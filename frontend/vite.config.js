import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the UI runs on :8000 and every API call goes to the FastAPI backend on :9000.
const API = "http://localhost:9000";
const proxy = Object.fromEntries(["/presets", "/suggest", "/plan", "/photo", "/image", "/generate", "/jobs", "/out"].map(p => [p, API]));

export default defineConfig({
  plugins: [react()],
  server: { port: 8000, strictPort: true, proxy, allowedHosts: [".ngrok-free.app", ".ngrok-free.dev", ".ngrok.app"] },  // the ngrok tunnel to :8000
});
