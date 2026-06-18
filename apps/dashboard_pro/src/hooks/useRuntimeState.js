import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { runtimeApi } from "../api/runtimeApi";

const RuntimeContext = createContext(null);

export function RuntimeProvider({ children }) {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function reload({ silent = false } = {}) {
    if (!silent) setLoading(true);
    try {
      const payload = await runtimeApi.state();
      setState(payload);
      setError("");
    } catch (exc) {
      setError(exc.message || String(exc));
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  const hasActiveJob = (state?.jobs || []).some((job) => ["queued", "starting", "running", "pause_requested", "resume_requested", "cancelling", "retrying"].includes(String(job.status || "").toLowerCase()));
  useEffect(() => {
    if (!hasActiveJob) return undefined;
    const timer = window.setInterval(() => reload({ silent: true }), 4000);
    return () => window.clearInterval(timer);
  }, [hasActiveJob]);

  const value = useMemo(() => ({ state, loading, error, reload, setState }), [state, loading, error]);
  return React.createElement(RuntimeContext.Provider, { value }, children);
}

export function useRuntimeState() {
  const context = useContext(RuntimeContext);
  if (!context) throw new Error("useRuntimeState must be used inside RuntimeProvider");
  return context;
}
