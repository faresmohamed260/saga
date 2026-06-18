import { useCallback, useEffect, useRef, useState } from "react";

export function useAsync(loader, deps = [], options = {}) {
  const [data, setData] = useState(options.initialData ?? null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const alive = useRef(true);

  const run = useCallback(async () => {
    setLoading(true);
    try {
      const result = await loader();
      if (alive.current) {
        setData(result);
        setError("");
      }
      return result;
    } catch (exc) {
      if (alive.current) setError(exc.message || String(exc));
      return null;
    } finally {
      if (alive.current) setLoading(false);
    }
  }, deps);

  useEffect(() => {
    alive.current = true;
    run();
    return () => {
      alive.current = false;
    };
  }, [run]);

  return { data, value: data, loading, error, reload: run, setData };
}
