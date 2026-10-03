import { useMemo, useState } from "react";
import { Header } from "./components/Header";
import { IconSprite } from "./components/Icon";
import { PlayerDialog } from "./components/PlayerDialog";
import { Toast } from "./components/Toast";
import { VideoList } from "./components/VideoList";
import { CreateForm } from "./components/create/CreateForm";
import { useJobs } from "./hooks/useJobs";
import { usePresets } from "./hooks/usePresets";
import { useToast } from "./hooks/useToast";
import { api } from "./lib/api";

export default function App() {
  const presets = usePresets();
  const { jobs, refresh } = useJobs();
  const [toast, say] = useToast();
  const [playing, setPlaying] = useState(null);

  const making = jobs.filter(j => j.status === "queued" || j.status === "running").length;
  const ready = jobs.filter(j => j.status === "done").length;

  // what a card can do; each one reports back with a toast and an immediate refresh
  const actions = useMemo(() => ({
    onPlay: setPlaying,
    onCopy: async (text, done) => { await navigator.clipboard.writeText(text); say(done); },
    onRedo: async (id, n) => {
      try { await api.redo(id, n); say(`Redoing scene ${n + 1}`); } catch { say("Could not redo that scene"); }
      refresh();
    },
    onDelete: async id => {
      try { await api.remove(id); } catch { say("Delete failed, try again"); return false; }
      say("Video deleted");
      refresh();
      return true;
    },
    onStop: async id => {
      try { await api.stop(id); say("Video stopped"); } catch { say("Could not stop it, it may have just finished"); }
      refresh();
    },
    onRetry: async j => {
      await api.generate({ topics: [j.topic], community: j.community, language: j.language, duration: j.duration, style: j.style || "photo" }).catch(() => say("Could not start it again"));
      refresh();
    },
  }), [refresh, say]);

  return (
    <>
      <IconSprite />
      <Header making={making} ready={ready} />
      <main className="layout">
        <CreateForm presets={presets} onStarted={msg => { say(msg); refresh(); }} />
        <VideoList jobs={jobs} presets={presets} actions={actions} />
      </main>
      <PlayerDialog video={playing} onClose={() => setPlaying(null)} />
      <Toast {...toast} />
    </>
  );
}
