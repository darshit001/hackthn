import { useMemo, useState } from "react";
import { Header } from "./components/Header";
import { IconSprite } from "./components/Icon";
import { Resizer } from "./components/Resizer";
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
  const { jobs, refresh, patch } = useJobs();
  const [toast, say] = useToast();
  const [playing, setPlaying] = useState(null);

  // what a card can do; each one reports back with a toast and an immediate refresh
  const actions = useMemo(() => ({
    onPlay: setPlaying,
    onCopy: async (text, done) => { await navigator.clipboard.writeText(text); say(done); },
    onRedo: async (id, n) => {
      try { await api.redo(id, n); say(`Redoing scene ${n + 1}`); } catch { say("Could not redo that scene"); }
      refresh();
    },
    onSave: async (id, on) => {
      patch(id, { saved: on });
      try { await api.save(id, on); say(on ? "Saved" : "Removed from Saved"); }
      catch { patch(id, { saved: !on }); say("Could not save it, try again"); }
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
  }), [refresh, say, patch]);
  const open = playing && jobs.find(j => j.id === playing && j.result);  // follows the live job: a save or redo shows at once, a delete closes it

  return (
    <>
      <IconSprite />
      <Header />
      <main className="layout">
        <CreateForm presets={presets} onStarted={msg => { say(msg); refresh(); }} />
        <Resizer />
        <VideoList jobs={jobs} presets={presets} actions={actions} />
      </main>
      <PlayerDialog job={open} jobs={jobs} label={presets.label} actions={actions} onOpen={setPlaying} onClose={() => setPlaying(null)} />
      <Toast {...toast} />
    </>
  );
}
