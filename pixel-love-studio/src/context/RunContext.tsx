import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, RunRow, RunStatus } from "@/lib/api";

interface RunContextValue {
  runId: string | null;
  run: RunRow | null;
  status: RunStatus | null;
  error: string | null;
  isSubmitting: boolean;
  submit: (drama: string) => Promise<void>;
}

const RunContext = createContext<RunContextValue | null>(null);

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [runId, setRunId] = useState<string | null>(() => sessionStorage.getItem("dss-run-id"));
  const [run, setRun] = useState<RunRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const pollRef = useRef<number | null>(null);

  const stopPoll = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const loadRun = useCallback(async (id: string) => {
    try {
      const row = await api.getRun(id);
      setRun(row);
      if (row.status === "done" || row.status === "failed") stopPoll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch run");
    }
  }, []);

  useEffect(() => {
    if (!runId) return;
    loadRun(runId);
    pollRef.current = window.setInterval(() => loadRun(runId), 2000);
    return stopPoll;
  }, [runId, loadRun]);

  const submit = async (drama: string) => {
    setError(null);
    setIsSubmitting(true);
    setRun(null);
    stopPoll();
    try {
      const res = await api.createRun(drama);
      sessionStorage.setItem("dss-run-id", res.id);
      setRunId(res.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed");
      throw e;
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <RunContext.Provider value={{ runId, run, status: run?.status ?? null, error, isSubmitting, submit }}>
      {children}
    </RunContext.Provider>
  );
}

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used inside RunProvider");
  return ctx;
}
