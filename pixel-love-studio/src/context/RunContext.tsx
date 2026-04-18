import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, RunRow, RunStatus } from "@/lib/api";

/** localStorage: latest run input + server row (after each agent step). */
export const RUN_SNAPSHOT_KEY = "pixel-love-studio:run-snapshot";

interface RunSnapshot {
  drama: string;
  runId: string;
  run: RunRow;
  lastStep: "writer" | "director" | "makeup" | "seedance_done" | "failed";
  updatedAt: string;
}

function saveSnapshot(partial: Omit<RunSnapshot, "updatedAt"> & { updatedAt?: string }) {
  const snap: RunSnapshot = {
    ...partial,
    updatedAt: partial.updatedAt ?? new Date().toISOString(),
  };
  try {
    localStorage.setItem(RUN_SNAPSHOT_KEY, JSON.stringify(snap));
  } catch (e) {
    console.warn("[Seedance FE] localStorage save failed", e);
  }
  console.log("[Seedance FE] snapshot", snap.lastStep, { runId: snap.runId, status: snap.run.status });
}

interface RunContextValue {
  runId: string | null;
  run: RunRow | null;
  status: RunStatus | null;
  error: string | null;
  isSubmitting: boolean;
  isPipelineRunning: boolean;
  submit: (drama: string) => Promise<void>;
}

const RunContext = createContext<RunContextValue | null>(null);

const POLL_MS = 2000;
const SEEDANCE_POLL_MS = 3000;

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [runId, setRunId] = useState<string | null>(() => sessionStorage.getItem("dss-run-id"));
  const [run, setRun] = useState<RunRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const pollRef = useRef<number | null>(null);
  /** Only one in-flight chain; value is run_id being processed */
  const pipelineOwnerRef = useRef<string | null>(null);

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
    pollRef.current = window.setInterval(() => loadRun(runId), POLL_MS);
    return stopPoll;
  }, [runId, loadRun]);

  const runFourAgents = useCallback(
    async (id: string, drama: string) => {
      if (pipelineOwnerRef.current) {
        console.warn("[Seedance FE] pipeline already running", pipelineOwnerRef.current);
        return;
      }
      pipelineOwnerRef.current = id;
      setIsPipelineRunning(true);
      setError(null);

      const fail = (msg: string, row?: RunRow | null) => {
        setError(msg);
        if (row) {
          setRun(row);
          saveSnapshot({ drama, runId: id, run: row, lastStep: "failed" });
        }
        console.error("[Seedance FE] pipeline error", msg, row);
      };

      try {
        console.log("[Seedance FE] input (drama)", { runId: id, chars: drama.length, preview: drama.slice(0, 200) });

        // 1. Writer (layer1)
        console.log("[Seedance FE] agent: writer → POST /api/runs/:id/writer");
        const w = await api.writer(id);
        console.log("[Seedance FE] writer output", w);
        setRun(w.run);
        saveSnapshot({ drama, runId: id, run: w.run, lastStep: "writer" });
        if (!w.ok || w.run.status === "failed") {
          fail(w.run.error_message || "Writer step failed", w.run);
          return;
        }

        // 2. Makeup (character + scene stills) before director
        console.log("[Seedance FE] agent: makeup → POST /api/runs/:id/makeup");
        const m = await api.makeup(id);
        console.log("[Seedance FE] makeup output", m);
        setRun(m.run);
        saveSnapshot({ drama, runId: id, run: m.run, lastStep: "makeup" });
        if (!m.ok || m.run.status === "failed") {
          fail(m.run.error_message || "Makeup step failed", m.run);
          return;
        }

        const urls = m.run.makeup_output?.character_image_urls ?? [];
        if (urls.length === 0) {
          fail("Makeup did not return any character_image_urls", m.run);
          return;
        }

        // 3. Director (layer2 / Seedance prompts)
        console.log("[Seedance FE] agent: director → POST /api/runs/:id/director");
        const d = await api.director(id);
        console.log("[Seedance FE] director output", d);
        setRun(d.run);
        saveSnapshot({ drama, runId: id, run: d.run, lastStep: "director" });
        if (!d.ok || d.run.status === "failed") {
          fail(d.run.error_message || "Director step failed", d.run);
          return;
        }

        // 4. Seedance (202 + poll)
        console.log("[Seedance FE] agent: seedance → POST /api/runs/:id/seedance");
        const acc = await api.seedance(id);
        console.log("[Seedance FE] seedance accepted", acc);
        if ("accepted" in acc && acc.accepted && "status_url" in acc) {
          console.log("[Seedance FE] poll", (acc as { status_url: string }).status_url, `every ${SEEDANCE_POLL_MS}ms`);
        }

        for (;;) {
          await new Promise((r) => setTimeout(r, SEEDANCE_POLL_MS));
          const st = await api.seedanceStatus(id);
          console.log("[Seedance FE] seedance/status", st);
          const phase = st.phase;
          if (phase === "done" || phase === "failed") {
            const finalRow = await api.getRun(id);
            setRun(finalRow);
            saveSnapshot({
              drama,
              runId: id,
              run: finalRow,
              lastStep: phase === "failed" ? "failed" : "seedance_done",
            });
            if (phase === "failed" || finalRow.status === "failed") {
              fail(finalRow.error_message || "Seedance merge failed", finalRow);
            } else {
              console.log("[Seedance FE] pipeline complete", { video_url: finalRow.layer3_output?.video_url });
            }
            break;
          }
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        fail(msg);
        try {
          const row = await api.getRun(id);
          setRun(row);
          saveSnapshot({ drama, runId: id, run: row, lastStep: "failed" });
        } catch {
          /* ignore */
        }
      } finally {
        pipelineOwnerRef.current = null;
        setIsPipelineRunning(false);
      }
    },
    [],
  );

  const submit = async (drama: string) => {
    setError(null);
    setIsSubmitting(true);
    setRun(null);
    stopPoll();
    try {
      const res = await api.createRun(drama);
      sessionStorage.setItem("dss-run-id", res.id);
      setRunId(res.id);
      console.log("[Seedance FE] created run (input saved in sessionStorage dss-story + pipeline will persist each step)", res);
      void runFourAgents(res.id, drama);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed");
      throw e;
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <RunContext.Provider
      value={{ runId, run, status: run?.status ?? null, error, isSubmitting, isPipelineRunning, submit }}
    >
      {children}
    </RunContext.Provider>
  );
}

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used inside RunProvider");
  return ctx;
}
