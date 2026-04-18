import { useCallback, useEffect, useRef, useState } from "react";
import type { RunRow, RunStatus, SeedanceJobStatus } from "./types";

const API = import.meta.env.VITE_API_URL ?? "";

type FetchJSONInit = RequestInit & { timeoutMs?: number };

async function fetchJSON<T>(path: string, init?: FetchJSONInit): Promise<T> {
  const { timeoutMs, ...rest } = init ?? {};
  const ctrl = timeoutMs ? new AbortController() : undefined;
  const tid =
    timeoutMs && ctrl
      ? window.setTimeout(() => ctrl.abort(), timeoutMs)
      : undefined;
  try {
    const r = await fetch(`${API}${path}`, {
      ...rest,
      signal: ctrl ? ctrl.signal : rest.signal,
      headers: {
        "Content-Type": "application/json",
        ...(rest.headers ?? {}),
      },
    });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(t || r.statusText);
    }
    return r.json() as Promise<T>;
  } finally {
    if (tid) window.clearTimeout(tid);
  }
}

/** Layer1 pending: draft or layer1_running with no layer1_output yet */
function isLayer1Pending(status: RunStatus, row: RunRow | null): boolean {
  if (status === "failed") return false;
  if (!row) return true;
  if (row.layer1_output) return false;
  return status === "draft" || status === "layer1_running";
}

function isDirectorPending(status: RunStatus, row: RunRow): boolean {
  if (status === "failed") return false;
  if (!row.layer1_output || row.layer2_output) return false;
  return status === "layer1_done" || status === "layer2_running";
}

function isMakeupPending(status: RunStatus, row: RunRow): boolean {
  if (status === "failed") return false;
  if (!row.layer2_output || row.makeup_output) return false;
  return status === "layer2_done" || status === "makeup_running";
}

function isLayer3Pending(status: RunStatus, row: RunRow): boolean {
  if (status === "failed") return false;
  if (!row.layer2_output || !row.makeup_output || row.layer3_output) return false;
  return status === "makeup_done" || status === "layer3_running";
}

function LayerSpinner({
  label,
  hint,
}: {
  label: string;
  hint?: string;
}) {
  return (
    <div className="layer-loading" role="status" aria-live="polite">
      <span className="layer-spinner" aria-hidden />
      <div className="layer-loading-text">
        <span className="layer-loading-label">{label}</span>
        {hint ? <span className="layer-loading-hint">{hint}</span> : null}
      </div>
    </div>
  );
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    draft: "Queued",
    layer1_running: "Writer · storyboard & script",
    layer1_done: "Writer done",
    makeup_running: "Makeup · ModelArk images",
    makeup_done: "Makeup done",
    layer2_running: "Director · multi-segment Seedance",
    layer2_done: "Director done",
    layer3_running: "Merge · render & stitch",
    done: "Done",
    failed: "Failed",
  };
  return map[s] ?? s;
}

export default function App() {
  const [drama, setDrama] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunRow | null>(null);
  const [note, setNote] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const pollRef = useRef<number | null>(null);

  const loadRun = useCallback(async (id: string) => {
    const row = await fetchJSON<RunRow>(`/api/runs/${id}`);
    setRun(row);
    if (row.status === "done" || row.status === "failed") {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    fetchJSON<{ product_note: string }>("/api/health")
      .then((h) => setNote(h.product_note))
      .catch(() => setNote(""));
  }, []);

  useEffect(() => {
    if (!runId) return;
    loadRun(runId).catch((e) => setErr(String(e.message)));
    pollRef.current = window.setInterval(() => {
      loadRun(runId).catch((e) => setErr(String(e.message)));
    }, 2000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [runId, loadRun]);

  async function submit() {
    setErr(null);
    setLoading(true);
    setRun(null);
    try {
      const res = await fetchJSON<{ id: string }>("/api/runs", {
        method: "POST",
        body: JSON.stringify({ drama }),
      });
      const id = res.id;
      setRunId(id);
      const steps: { path: string; timeoutMs: number }[] = [
        { path: `/api/runs/${id}/writer`, timeoutMs: 180_000 },
        { path: `/api/runs/${id}/director`, timeoutMs: 180_000 },
        { path: `/api/runs/${id}/makeup`, timeoutMs: 600_000 },
        { path: `/api/runs/${id}/seedance`, timeoutMs: 900_000 },
      ];
      for (const { path, timeoutMs } of steps) {
        if (path.endsWith("/seedance")) {
          const ctrl = new AbortController();
          const tid = window.setTimeout(() => ctrl.abort(), timeoutMs);
          try {
            const r = await fetch(`${API}${path}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              signal: ctrl.signal,
            });
            window.clearTimeout(tid);
            if (r.status === 202) {
              const j = (await r.json()) as { status_url: string };
              const rel = j.status_url.startsWith("/")
                ? j.status_url
                : `/${j.status_url}`;
              for (;;) {
                const st = await fetchJSON<SeedanceJobStatus>(rel);
                if (st.phase === "done") break;
                if (st.phase === "failed")
                  throw new Error(
                    String(st.error_message ?? st.error_code ?? "Seedance failed"),
                  );
                await new Promise((res) => setTimeout(res, 2500));
              }
            } else if (!r.ok) {
              const t = await r.text();
              throw new Error(t || r.statusText);
            } else {
              await r.json();
            }
          } finally {
            window.clearTimeout(tid);
          }
        } else {
          await fetchJSON(path, { method: "POST", timeoutMs });
        }
        await loadRun(id);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Submit failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shell">
      <header className="hero">
        <p className="eyebrow">Personal drama → Seedance</p>
        <h1 className="title">
          Writer / director / makeup
          <span className="title-accent"> multi-segment video</span>
        </h1>
        <p className="lede">
          The client calls writer → director → makeup → Seedance merge APIs in order; the server
          orchestrates Butterbase LLM, ModelArk image/video, ffmpeg, and Storage.
        </p>
        {note ? <p className="product-note">{note}</p> : null}
      </header>

      <section className="panel input-panel">
        <label className="label" htmlFor="drama">
          Personal drama
        </label>
        <textarea
          id="drama"
          className="drama"
          rows={8}
          value={drama}
          onChange={(e) => setDrama(e.target.value)}
          placeholder="Your story, mood, scene…"
        />
        <button
          type="button"
          className="cta"
          disabled={loading || !drama.trim()}
          onClick={() => void submit()}
        >
          {loading ? "Pipeline running…" : "Start"}
        </button>
        {err ? <p className="error">{err}</p> : null}
      </section>

      {runId ? (
        <div className="pipeline">
          {!run ? (
            <div className="panel layer-pending">
              <LayerSpinner
                label="Connecting"
                hint="Fetching run state (~1–2s)"
              />
            </div>
          ) : (
            <>
              <div className="status-bar">
                <span className="status-pill">{statusLabel(run.status)}</span>
                <span className="mono small">{run.id}</span>
              </div>

              {run.status === "failed" ? (
                <div className="panel fail">
                  <strong>{run.error_code}</strong>
                  <p>{run.error_message}</p>
                  <p className="small muted">
                    Check BUTTERBASE_APP_ID + BUTTERBASE_API_KEY, MAKEUP_IMAGE_MODEL, SEEDANCE_2_0_API,
                    local ffmpeg, and Storage quota; retry each step via{" "}
                    <span className="mono">POST /api/runs/&lt;id&gt;/writer</span> and the other three routes.
                  </p>
                </div>
              ) : null}

              {run.layer1_output ? (
                <article className="panel layer layer1">
                  <h2>Writer · storyboard & script</h2>
                  <div className="shots">
                    {run.layer1_output.storyboard.map((s, i) => (
                      <div
                        key={s.shot_id}
                        className="shot-card"
                        style={{ animationDelay: `${i * 0.06}s` }}
                      >
                        <span className="shot-id">{s.shot_id}</span>
                        <p>{s.visual}</p>
                        <span className="small muted">
                          ≈ {s.duration_hint_sec}s · {s.camera_notes ?? "—"}
                        </span>
                      </div>
                    ))}
                  </div>
                  <h3 className="subh">Script</h3>
                  <pre className="script-block">{run.layer1_output.script}</pre>
                  <h3 className="subh">Characters</h3>
                  <ul className="char-list">
                    {run.layer1_output.characters.map((c) => (
                      <li key={c.name}>
                        <strong>{c.name}</strong> — {c.description}
                      </li>
                    ))}
                  </ul>
                </article>
              ) : isLayer1Pending(run.status, run) ? (
                <article className="panel layer layer1 layer-pending">
                  <h2>Writer · storyboard & script</h2>
                  <LayerSpinner
                    label="Writer running"
                    hint={
                      run.status === "draft"
                        ? "Queued; calling LLM for storyboard and lines…"
                        : "Generating storyboard, script, characters, dialogue (~30s)…"
                    }
                  />
                </article>
              ) : null}

              {run.layer2_output ? (
                <article className="panel layer layer2">
                  <h2>Director · multi-segment Seedance plan</h2>
                  {run.layer2_output.director_notes ? (
                    <p className="small muted">{run.layer2_output.director_notes}</p>
                  ) : null}
                  {run.layer2_output.seedance_prompts.map((p) => (
                    <div key={p.segment_id} className="prompt-block">
                      <span className="mono small">{p.segment_id}</span>
                      {p.segment_goal ? (
                        <p className="small muted">Goal: {p.segment_goal}</p>
                      ) : null}
                      <p>{p.prompt}</p>
                      <p className="small muted">
                        {p.duration_sec != null ? `${p.duration_sec}s` : "—"} ·{" "}
                        {p.ratio ?? "—"} · {p.resolution ?? "—"}
                        {p.image_refs?.length
                          ? ` · refs [${p.image_refs.join(", ")}]`
                          : ""}
                      </p>
                    </div>
                  ))}
                </article>
              ) : isDirectorPending(run.status, run) ? (
                <article className="panel layer layer2 layer-pending">
                  <h2>Director · multi-segment Seedance plan</h2>
                  <LayerSpinner
                    label="Director running"
                    hint="Building English Seedance prompts and structured params from writer JSON…"
                  />
                </article>
              ) : null}

              {run.makeup_output ? (
                <article className="panel layer makeup">
                  <h2>定妆 · 真人向参考图</h2>
                  <div className="img-row">
                    {run.makeup_output.character_image_urls.map((u) => (
                      <a key={u} href={u} target="_blank" rel="noreferrer">
                        <img src={u} alt="makeup ref" className="ref-img" />
                      </a>
                    ))}
                  </div>
                  {run.makeup_output.makeup_prompts?.length ? (
                    <details className="small muted">
                      <summary>定妆英文 prompt</summary>
                      <ul>
                        {run.makeup_output.makeup_prompts.map((t, i) => (
                          <li key={i}>{t}</li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </article>
              ) : isMakeupPending(run.status, run) ? (
                <article className="panel layer makeup layer-pending">
                  <h2>定妆 · 真人向参考图</h2>
                  <LayerSpinner
                    label="定妆生成中"
                    hint="LLM 规划定妆 prompt 后，由 ModelArk 图像接口逐张出图，可能需要数十秒…"
                  />
                </article>
              ) : null}

              {run.layer3_output ? (
                <article className="panel layer layer3">
                  <h2>成片 · 拼接与上传</h2>
                  <video
                    className="video"
                    src={run.layer3_output.video_url}
                    controls
                    playsInline
                  />
                  <p className="small muted">
                    model {run.layer3_output.model}
                    {run.layer3_output.duration_sec != null
                      ? ` · ${run.layer3_output.duration_sec}s`
                      : ""}
                  </p>
                  {run.layer3_output.meta?.upload_error ? (
                    <p className="small error">
                      Storage：{run.layer3_output.meta.upload_error}
                    </p>
                  ) : null}
                  {run.layer3_output.meta?.product_note ? (
                    <p className="small">{run.layer3_output.meta.product_note}</p>
                  ) : null}
                </article>
              ) : isLayer3Pending(run.status, run) ? (
                <article className="panel layer layer3 layer-pending">
                  <h2>成片 · 拼接与上传</h2>
                  <LayerSpinner
                    label="多段 Seedance 渲染与拼接"
                    hint="逐段生成、本机 ffmpeg 拼接、上传 Butterbase Storage；总耗时常为数分钟…"
                  />
                </article>
              ) : null}
            </>
          )}
        </div>
      ) : null}

      <style>{`
        .shell {
          max-width: 920px;
          margin: 0 auto;
          padding: 3rem 1.5rem 5rem;
        }
        .hero {
          margin-bottom: 2.5rem;
        }
        .eyebrow {
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.28em;
          color: var(--accent);
          margin: 0 0 0.75rem;
        }
        .title {
          font-family: var(--font-display);
          font-size: clamp(2.4rem, 6vw, 3.6rem);
          font-weight: 400;
          line-height:1.05;
          margin: 0 0 1rem;
        }
        .title-accent {
          font-style: italic;
          color: var(--accent-dim);
        }
        .lede {
          color: var(--muted);
          max-width: 36rem;
          line-height: 1.55;
          margin: 0;
        }
        .product-note {
          margin-top: 1rem;
          font-size: 0.85rem;
          color: var(--muted);
          border-left: 3px solid var(--accent);
          padding-left: 1rem;
          max-width: 40rem;
        }
        .panel {
          background: var(--bg-elevated);
          border: 1px solid var(--line);
          border-radius: 2px;
          padding: 1.5rem;
          margin-bottom: 1.5rem;
          box-shadow: 0 0 0 1px var(--glow);
        }
        .input-panel {
          transform: rotate(-0.25deg);
        }
        .label {
          display: block;
          font-size: 0.7rem;
          letter-spacing: 0.2em;
          text-transform: uppercase;
          color: var(--muted);
          margin-bottom: 0.6rem;
        }
        .drama {
          width: 100%;
          resize: vertical;
          background: var(--bg);
          color: var(--ink);
          border: 1px solid var(--line);
          padding: 1rem;
          font-size: 1rem;
          line-height: 1.5;
          font-family: var(--font-ui);
          border-radius: 2px;
        }
        .drama:focus {
          outline: 1px solid var(--accent);
          outline-offset: 2px;
        }
        .cta {
          margin-top: 1rem;
          padding: 0.85rem 1.6rem;
          font-weight: 700;
          font-size: 0.9rem;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          border: none;
          background: linear-gradient(135deg, var(--accent), #ff8a65);
          color: #1a0f0c;
          cursor: pointer;
          border-radius: 2px;
          transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .cta:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 12px 28px var(--glow);
        }
        .cta:disabled {
          opacity: 0.45;
          cursor: not-allowed;
        }
        .error {
          color: #ff9a8b;
          margin-top: 0.75rem;
        }
        .pipeline {
          margin-top: 2rem;
        }
        .status-bar {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin-bottom: 1rem;
          flex-wrap: wrap;
        }
        .status-pill {
          background: var(--accent);
          color: #140a08;
          padding: 0.35rem 0.9rem;
          font-weight: 700;
          font-size: 0.75rem;
          letter-spacing: 0.08em;
        }
        .mono { font-family: ui-monospace, monospace; }
        .small { font-size: 0.8rem; }
        .muted { color: var(--muted); }
        .fail {
          border-color: var(--accent-dim);
        }
        .layer h2 {
          font-family: var(--font-display);
          font-weight: 400;
          font-size: 1.75rem;
          margin: 0 0 1.25rem;
        }
        .subh {
          font-size: 0.75rem;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: var(--muted);
          margin: 1.5rem 0 0.5rem;
        }
        .shots {
          display: grid;
          gap: 0.75rem;
        }
        .shot-card {
          border-left: 4px solid var(--accent);
          padding: 0.75rem 1rem;
          background: var(--bg);
          animation: rise 0.5s ease both;
        }
        @keyframes rise {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .shot-id {
          font-size: 0.65rem;
          letter-spacing: 0.15em;
          color: var(--accent);
        }
        .script-block {
          white-space: pre-wrap;
          font-family: var(--font-display);
          font-size: 1.05rem;
          line-height: 1.6;
          margin: 0;
          color: #d8cfc2;
        }
        .char-list {
          margin: 0;
          padding-left: 1.1rem;
          color: var(--muted);
        }
        .img-row {
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem;
          margin-bottom: 1rem;
        }
        .ref-img {
          max-height: 180px;
          border: 1px solid var(--line);
          border-radius: 2px;
        }
        .prompt-block {
          background: var(--bg);
          padding: 1rem;
          margin-top: 0.75rem;
          border-radius: 2px;
        }
        .video {
          width: 100%;
          max-height: 480px;
          background: #000;
          border-radius: 2px;
        }
        .layer-pending {
          border-style: dashed;
          border-color: var(--line);
          background: rgba(22, 19, 17, 0.65);
        }
        .layer-pending h2 {
          margin-bottom: 1rem;
        }
        .layer-loading {
          display: flex;
          align-items: flex-start;
          gap: 0.85rem;
          padding: 0.35rem 0;
        }
        .layer-spinner {
          flex-shrink: 0;
          width: 22px;
          height: 22px;
          margin-top: 2px;
          border: 2px solid var(--line);
          border-top-color: var(--accent);
          border-radius: 50%;
          animation: layerSpin 0.75s linear infinite;
        }
        @keyframes layerSpin {
          to { transform: rotate(360deg); }
        }
        .layer-loading-text {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
          min-width: 0;
        }
        .layer-loading-label {
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--ink);
        }
        .layer-loading-hint {
          font-size: 0.78rem;
          color: var(--muted);
          line-height: 1.45;
          max-width: 28rem;
        }
      `}</style>
    </div>
  );
}
