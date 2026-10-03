import { useCallback, useRef, useState } from "react";

export function useToast() {
  const [toast, setToast] = useState({ text: "", show: false });
  const timer = useRef();
  const say = useCallback(text => {
    setToast({ text, show: true });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(t => ({ ...t, show: false })), 1800);
  }, []);
  return [toast, say];
}
