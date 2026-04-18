import { useCallback, useEffect, useRef, useState } from "react";
import type { RunRow } from "./types";

const API = import.meta.env.VITE_API_URL ?? "";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<T>;
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    draft: "排队中",
    layer1_running: "Layer1 分镜与脚本",
    layer1_done: "Layer1 完成",
    layer2_running: "Layer2 角色与提示词",
    layer2_done: "Layer2 完成",
    layer3_running: "Layer3 Seedance 成片",
    done: "完成",
    failed: "失败",
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
      setRunId(res.id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "提交失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shell">
      <header className="hero">
        <p className="eyebrow">Personal drama → Seedance</p>
        <h1 className="title">
          三层 Agent
          <span className="title-accent"> 流水线</span>
        </h1>
        <p className="lede">
          Layer1 分镜与台词 · Layer2 动漫参考与视频 prompt · Layer3 Seedance 2.0 成片
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
          placeholder="写下你的故事、情绪、场景……"
        />
        <button
          type="button"
          className="cta"
          disabled={loading || !drama.trim()}
          onClick={() => void submit()}
        >
          {loading ? "创建中…" : "开始生成"}
        </button>
        {err ? <p className="error">{err}</p> : null}
      </section>

      {run ? (
        <div className="pipeline">
          <div className="status-bar">
            <span className="status-pill">{statusLabel(run.status)}</span>
            <span className="mono small">{run.id}</span>
          </div>

          {run.status === "failed" ? (
            <div className="panel fail">
              <strong>{run.error_code}</strong>
              <p>{run.error_message}</p>
              <p className="small muted">
                可检查 BUTTERBASE_APP_ID + BUTTERBASE_API_KEY（Butterbase AI 网关）或
                OPENAI_API_KEY、以及 SEEDANCE_2_0_API 与网络；仅重跑需新增接口（当前为单次流水线）。
              </p>
            </div>
          ) : null}

          {run.layer1_output ? (
            <article className="panel layer layer1">
              <h2>Layer1 · 分镜与脚本</h2>
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
              <h3 className="subh">脚本</h3>
              <pre className="script-block">{run.layer1_output.script}</pre>
              <h3 className="subh">角色</h3>
              <ul className="char-list">
                {run.layer1_output.characters.map((c) => (
                  <li key={c.name}>
                    <strong>{c.name}</strong> — {c.description}
                  </li>
                ))}
              </ul>
            </article>
          ) : null}

          {run.layer2_output ? (
            <article className="panel layer layer2">
              <h2>Layer2 · 参考图与 Seedance prompt</h2>
              <div className="img-row">
                {run.layer2_output.character_image_urls.map((u) => (
                  <a key={u} href={u} target="_blank" rel="noreferrer">
                    <img src={u} alt="character ref" className="ref-img" />
                  </a>
                ))}
              </div>
              {run.layer2_output.seedance_prompts.map((p) => (
                <div key={p.segment_id} className="prompt-block">
                  <span className="mono small">{p.segment_id}</span>
                  <p>{p.prompt}</p>
                </div>
              ))}
            </article>
          ) : null}

          {run.layer3_output ? (
            <article className="panel layer layer3">
              <h2>Layer3 · 成片</h2>
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
              {run.layer3_output.meta?.product_note ? (
                <p className="small">{run.layer3_output.meta.product_note}</p>
              ) : null}
            </article>
          ) : null}
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
      `}</style>
    </div>
  );
}
