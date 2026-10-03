import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

const busy = j => j.status === "queued" || j.status === "running";

// Polls /jobs: fast while something is being made, slow otherwise so jobs started from another tab or the API still show up.
export function useJobs() {
  const [jobs, setJobs] = useState([]);
  const timer = useRef();

  const refresh = useCallback(async () => {
    clearTimeout(timer.current);
    let next = null;
    try {
      next = await api.jobs();
      setJobs(next);
    } catch {
      /* server restarting: try again shortly */
    }
    timer.current = setTimeout(refresh, !next ? 4000 : next.some(busy) ? 2000 : 8000);
  }, []);

  useEffect(() => {
    refresh();
    return () => clearTimeout(timer.current);
  }, [refresh]);

  return { jobs, refresh };
}
