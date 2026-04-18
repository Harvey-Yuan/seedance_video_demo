# Seedance Backend HTTP API

This service exposes HTTP **only via FastAPI**. Butterbase Chat, BytePlus ModelArk (Seedream / Seedance), local ffmpeg, and Butterbase Storage are all invoked from **`backend/pipeline_agents.py`** inside the corresponding route handlers.

- **Swagger**: [`/docs`](http://127.0.0.1:8000/docs) · **OpenAPI JSON**: [`/openapi.json`](http://127.0.0.1:8000/openapi.json)

---

## Architecture (four decoupled steps + optional one-shot)

```mermaid
flowchart LR
  fe[frontend]
  r[POST /api/runs]
  w[POST .../writer]
  m[POST .../makeup]
  d[POST .../director]
  s[POST .../seedance]
  fe --> r --> w --> m --> d --> s
```

| Step | Route | Prerequisites | Main fields written |
|------|------|---------------|---------------------|
| Create | `POST /api/runs` | — | `draft` + `drama_input` |
| Writer | `POST /api/runs/{id}/writer` | `draft`, no `layer1_output` yet | `layer1_output`, `layer1_done` |
| Director | `POST /api/runs/{id}/director` | has `layer1_output` | `layer2_output`, `layer2_done` |
| Makeup | `POST /api/runs/{id}/makeup` | has `layer1_output` | `makeup_output`, `makeup_done` |
| Merge | `POST /api/runs/{id}/seedance` (**202** async) | has `layer2_output` **and** `makeup_output` | `seedance_job` in background; then `layer3_output` + `status=done` / `failed` |

**Recommended order**: writer → makeup → director → Seedance (visual stills before per-segment prompts; matches `pixel-love-studio`). Director **only** reads `layer1`; makeup **only** reads `layer1`; merge reads **director + makeup** and requires **non-empty** `makeup_output.character_image_urls` and `layer2_output.seedance_prompts`.

**Optional one-shot**: `POST /api/runs/{id}/pipeline` (when `draft` and all stage outputs empty) runs the four steps **in the background**, equivalent to four separate client calls.

---

## Common responses

### `GET /api/runs/{run_id}`

Returns the SQLite row as JSON (`status`, `layer*_output`, `makeup_output`, `error_*`, etc.).

### `POST .../writer|director|makeup`

Success or business failure both return **HTTP 200**, body like:

```json
{
  "ok": true,
  "run": { "...": "same shape as GET /api/runs/{id} ..." }
}
```

If a step calls `_fail`: `ok` is `false`, `run.status` is `failed`; see `run.error_code` / `run.error_message`.

### `POST .../seedance` (async)

- **Accepted**: **HTTP 202**, body includes `accepted`, `run_id`, `status_url` (e.g. `/api/runs/{id}/seedance/status`), `poll_hint`.
- **Poll**: `GET status_url` every 2–5s until `phase` is `done` or `failed`; sub-phases include `generating` (with per-segment `segment_urls`), `merging`, `uploading`.
- **Final**: after `phase=done`, **`GET /api/runs/{id}`** for the full row (including `layer3_output.video_url`, i.e. merged upload or fallback URL).
- **409**: `layer3_output` already exists, or a Seedance job is already running.

### Common HTTP errors

| HTTP | Case |
|------|------|
| `404` | `run_id` not found |
| `400` | Missing prerequisite (e.g. director before writer) |
| `409` | Duplicate call (e.g. `writer` when `layer1_output` exists); or Seedance already running / final video exists |

---

## 1. `GET /api/health`

Liveness + `product_note`.

---

## 2. `GET /api/meta`

Orchestration description and whether integrations are ready (**no secrets**). Includes `orchestration.steps` (four route paths).

---

## 3. `POST /api/runs`

**Body**: `{ "drama": "string" }` (1–32000 chars)

**Behavior**: creates a run only, `status=draft`, **does not** auto-run the four steps.

**Response**: `{ "id": "<uuid>", "status": "draft" }`

---

## 4. `POST /api/runs/{run_id}/writer`

Calls the LLM to produce `layer1_output` (storyboard / script / characters / dialogue).

---

## 5. `POST /api/runs/{run_id}/director`

Uses DB `layer1_output` + `drama_input` to produce `layer2_output.seedance_prompts` (**no** makeup images passed in; no `image_roles` required).

---

## 6. `POST /api/runs/{run_id}/makeup`

Uses `layer1_output`; LLM plans makeup prompts → ModelArk `images.generate` → `makeup_output.character_image_urls`.

---

## 7. `POST /api/runs/{run_id}/seedance`

Reads `layer2_output` + `makeup_output`: in **BackgroundTasks**, per-segment `generate_video` → download → **ffmpeg** concat → (if Butterbase configured) Storage upload, then `layer3_output`.

**HTTP**: **202 Accepted** (see `POST .../seedance` above); **do not** block this POST until the full video finishes.

### 7.1 `GET /api/runs/{run_id}/seedance/status`

Returns current `seedance_job` (with `run_status`); if DB already `status=done` with `layer3_output`, returns `phase: "done"` and `video_url` / `layer3` summary.

**Merge note**: to reduce Ark `InvalidParameter` risk, **`resolution` is not sent to Seedance** (model default).

---

## 8. `POST /api/runs/{run_id}/pipeline`

**When**: `status=draft` and `layer1_output` / `layer2_output` / `makeup_output` / `layer3_output` are all empty.

**Behavior**: `202` means accepted (JSON `accepted`); **BackgroundTasks** runs four steps; poll **`GET /api/runs/{id}`** for progress.

---

## Quick curl test

```bash
BASE=http://127.0.0.1:8000
R=$(curl -sS -X POST "$BASE/api/runs" -H "Content-Type: application/json" \
  -d '{"drama":"your story here"}')
ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -sS -m 300 -X POST "$BASE/api/runs/$ID/writer" | python3 -m json.tool
curl -sS -m 600 -X POST "$BASE/api/runs/$ID/makeup" | python3 -m json.tool
curl -sS -m 300 -X POST "$BASE/api/runs/$ID/director" | python3 -m json.tool
curl -sS -D - -o /tmp/sd.json -X POST "$BASE/api/runs/$ID/seedance"
# Expect first line HTTP/1.1 202; then poll:
while true; do
  P=$(curl -sS "$BASE/api/runs/$ID/seedance/status" | python3 -c "import sys,json; print(json.load(sys.stdin).get('phase',''))")
  echo "phase=$P"
  [ "$P" = "done" ] || [ "$P" = "failed" ] && break
  sleep 3
done
curl -sS "$BASE/api/runs/$ID" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('status'), (r.get('layer3_output') or {}).get('video_url'))"
```

---

## Security & deployment

- **No auth** today—use only on trusted networks.
- **CORS**: `CORS_ORIGINS` env var.
- **ffmpeg** must be on PATH or set `FFMPEG_PATH` (see `GET /api/meta` → `ffmpeg.available`).
