// Every call the UI makes to the FastAPI backend. Errors carry the server's message.
async function call(path, options) {
  const r = await fetch(path, options);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
const post = (path, body) => call(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body && JSON.stringify(body) });

export const api = {
  presets: () => call("/presets"),
  jobs: () => call("/jobs"),
  suggest: (community, language, trendsOnly = false) =>
    call(`/suggest?${new URLSearchParams({ community, language, ...(trendsOnly && { trends_only: 1 }) })}`),
  plan: opts => post("/plan", opts),
  generate: opts => post("/generate", opts),
  redo: (id, scene) => post(`/jobs/${id}/redo/${scene}`),
  remove: id => call(`/jobs/${id}`, { method: "DELETE" }),
};
