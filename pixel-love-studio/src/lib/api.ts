export type RunStatus =
  | "draft"
  | "layer1_running"
  | "layer1_done"
  | "makeup_running"
  | "makeup_done"
  | "layer2_running"
  | "layer2_done"
  | "layer3_running"
  | "done"
  | "failed";

export interface StoryboardShot {
  shot_id: string;
  visual: string;
  duration_hint_sec: number;
  camera_notes?: string;
}

export interface Layer1Output {
  storyboard: StoryboardShot[];
  script: string;
  characters: { name: string; description: string; voice_notes?: string }[];
  dialogue: { speaker: string; line: string; shot_ref?: string }[];
}

export interface MakeupOutput {
  character_image_urls: string[];
  makeup_prompts?: string[];
  scene_image_urls?: string[];
  scene_prompts?: string[];
  meta?: Record<string, unknown>;
}

export interface SeedancePromptSegment {
  segment_id: string;
  prompt: string;
  segment_goal?: string;
  camera_notes?: string;
  image_refs?: number[];
  image_roles?: string[];
  duration_sec?: number;
  ratio?: string;
  resolution?: string;
  generate_audio?: boolean;
  camera_fixed?: boolean;
  seed?: number;
}

export interface Layer2Output {
  director_notes?: string;
  character_image_urls: string[];
  seedance_prompts: SeedancePromptSegment[];
}

export interface Layer3Output {
  video_url: string;
  model: string;
  duration_sec?: number;
  meta?: {
    product_note?: string;
    segment_urls?: string[];
    storage_object_id?: string;
    upload_error?: string;
    upload_skipped?: boolean;
    merged_bytes?: number;
  };
}

export interface RunRow {
  id: string;
  status: RunStatus;
  drama_input: string;
  layer1_output: Layer1Output | null;
  makeup_output: MakeupOutput | null;
  layer2_output: Layer2Output | null;
  layer3_output: Layer3Output | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  /** Present while Seedance merge is running (backend JSON). */
  seedance_job?: Record<string, unknown> | null;
}

/** POST /writer | /director | /makeup success body */
export interface StepEnvelope {
  ok: boolean;
  run: RunRow;
}

export interface SeedanceAccepted {
  accepted: true;
  run_id: string;
  status_url: string;
  poll_hint: string;
}

export type SeedancePostResult = SeedanceAccepted | Record<string, unknown>;

export interface SeedanceStatusPayload {
  phase?: string;
  run_status?: string;
  video_url?: string;
  segment_urls?: string[];
  total_segments?: number;
  [key: string]: unknown;
}

/**
 * Empty: same-origin `/api/...` (Vite dev/preview proxy to backend).
 * Set `VITE_API_BASE_URL=http://127.0.0.1:8000` to call FastAPI directly (needs CORS on backend).
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export function buildApiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return API_BASE ? `${API_BASE}${p}` : p;
}

function apiUrl(path: string): string {
  return buildApiUrl(path);
}

function parseErrorBody(text: string, status: number): string {
  try {
    const j = JSON.parse(text) as { detail?: unknown };
    if (j?.detail !== undefined) {
      const d = j.detail;
      const msg = typeof d === "string" ? d : Array.isArray(d) ? JSON.stringify(d) : JSON.stringify(d);
      if (status === 404 && (msg === "Not Found" || msg === "not found")) {
        return (
          `${msg} — Wrong process on :8000 or bad path. Open http://127.0.0.1:8000/openapi.json and confirm writer/makeup/director/seedance routes exist; then run: uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 (see pixel-love-studio/.env.development for VITE_API_BASE_URL).`
        );
      }
      return msg;
    }
  } catch {
    /* fall through */
  }
  return text || `${status}`;
}

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const url = apiUrl(path);
  const r = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(parseErrorBody(t, r.status));
  }
  return r.json() as Promise<T>;
}

async function postStep(runId: string, step: "writer" | "director" | "makeup"): Promise<StepEnvelope> {
  return fetchJSON<StepEnvelope>(`/api/runs/${runId}/${step}`, { method: "POST" });
}

export const api = {
  health: () => fetchJSON<{ ok: boolean; product_note: string }>("/api/health"),
  createRun: (drama: string) =>
    fetchJSON<{ id: string; status: RunStatus }>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ drama }),
    }),
  getRun: (id: string) => fetchJSON<RunRow>(`/api/runs/${id}`),
  writer: (runId: string) => postStep(runId, "writer"),
  director: (runId: string) => postStep(runId, "director"),
  makeup: (runId: string) => postStep(runId, "makeup"),
  /** Returns 202 Accepted with polling hints (API.md). */
  seedance: async (runId: string): Promise<SeedancePostResult> => {
    const r = await fetch(apiUrl(`/api/runs/${runId}/seedance`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const text = await r.text();
    let data: SeedancePostResult = {};
    try {
      data = text ? (JSON.parse(text) as SeedancePostResult) : {};
    } catch {
      if (!r.ok) throw new Error(text || r.statusText);
    }
    if (r.status === 202) return data;
    if (!r.ok) {
      throw new Error(parseErrorBody(text, r.status));
    }
    return data;
  },
  seedanceStatus: (runId: string) =>
    fetchJSON<SeedanceStatusPayload>(`/api/runs/${runId}/seedance/status`),
};
