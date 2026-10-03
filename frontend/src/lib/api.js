// Every call the UI makes to the FastAPI backend. Errors carry the server's message.
async function call(path, options) {
  const r = await fetch(path, options);
  if (!r.ok) {
    // FastAPI wraps an HTTPException message as {"detail": "..."}
    const text = await r.text();
    let detail;
    try { detail = JSON.parse(text).detail; } catch { /* not JSON */ }
    throw new Error(typeof detail === "string" ? detail : text);
  }
  return r.json();
}
const post = (path, body) => call(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body && JSON.stringify(body) });

export const api = {
  presets: () => call("/presets"),
  jobs: () => call("/jobs"),
  suggest: (community, language) => call(`/suggest?${new URLSearchParams({ community, language })}`),
  plan: opts => post("/plan", opts),
  generate: opts => post("/generate", opts),
  redo: (id, scene) => post(`/jobs/${id}/redo/${scene}`),
  stop: id => post(`/jobs/${id}/stop`),
  remove: id => call(`/jobs/${id}`, { method: "DELETE" }),
};
