# Seedance Backend HTTP API

本服务 **只通过 FastAPI** 暴露 HTTP；Butterbase Chat、BytePlus ModelArk（Seedream / Seedance）、本机 ffmpeg、Butterbase Storage 均由 **`backend/pipeline_agents.py`** 在对应路由处理函数内调用。

- **Swagger**：[`/docs`](http://127.0.0.1:8000/docs) · **OpenAPI JSON**：[`/openapi.json`](http://127.0.0.1:8000/openapi.json)

---

## 架构（四步解耦 + 可选一键）

```mermaid
flowchart LR
  fe[前端]
  r[POST /api/runs]
  w[POST .../writer]
  d[POST .../director]
  m[POST .../makeup]
  s[POST .../seedance]
  fe --> r --> w --> d --> m --> s
```

| 步骤 | 路由 | 依赖 | 写入的主要字段 |
|------|------|------|------------------|
| 创建 | `POST /api/runs` | — | `draft` + `drama_input` |
| 编剧 | `POST /api/runs/{id}/writer` | `draft`、尚无 `layer1_output` | `layer1_output`，`layer1_done` |
| 导演 | `POST /api/runs/{id}/director` | 已有 `layer1_output` | `layer2_output`，`layer2_done` |
| 定妆 | `POST /api/runs/{id}/makeup` | 已有 `layer1_output` | `makeup_output`，`makeup_done` |
| 成片 | `POST /api/runs/{id}/seedance`（**202** 异步） | 已有 `layer2_output` **与** `makeup_output` | 后台写入 `seedance_job`；完成后 `layer3_output` + `status=done` / `failed` |

**推荐调度顺序**：编剧 → 导演 → 定妆 → Seedance（与前端默认一致）。导演 **仅** 消费 `layer1`；定妆 **仅** 消费 `layer1`；成片消费 **导演 + 定妆**。

**可选一键**：`POST /api/runs/{id}/pipeline`（`draft` 且无各阶段输出时）在 **后台** 顺序执行上述四步，行为与前端连调四次等价。

---

## 通用响应

### `GET /api/runs/{run_id}`

返回 SQLite 行 JSON（含 `status`、`layer*_output`、`makeup_output`、`error_*` 等）。

### 各 `POST .../writer|director|makeup`

成功或业务失败均返回 **HTTP 200**，body 形如：

```json
{
  "ok": true,
  "run": { "...": "与 GET /api/runs/{id} 相同 ..." }
}
```

若某步内部 `_fail`：`ok` 为 `false`，`run.status` 为 `failed`，见 `run.error_code` / `run.error_message`。

### `POST .../seedance`（异步）

- **接受**：**HTTP 202**，body 含 `accepted`、`run_id`、`status_url`（如 `/api/runs/{id}/seedance/status`）、`poll_hint`。
- **轮询**：`GET status_url` 每 2～5 秒，直到 `phase` 为 `done` 或 `failed`；子阶段含 `generating`（含各段 `segment_urls`）、`merging`、`uploading`。
- **最终结果**：`phase=done` 后 **`GET /api/runs/{id}`** 取完整行（含 `layer3_output.video_url`，即拼接后上传或降级 URL）。
- **409**：已有 `layer3_output`，或 Seedance 任务已在跑。

### 常见 HTTP 错误

| HTTP | 场景 |
|------|------|
| `404` | `run_id` 不存在 |
| `400` | 前置输出缺失（如未跑编剧就调导演） |
| `409` | 重复调用（如已有 `layer1_output` 再调 `writer`）；或 Seedance 已在跑 / 已有成片 |

---

## 1. `GET /api/health`

探活 + `product_note`。

---

## 2. `GET /api/meta`

编排说明、各集成是否就绪（**不含密钥**）。字段含 `orchestration.steps`（四步路径列表）。

---

## 3. `POST /api/runs`

**Body**：`{ "drama": "string" }`（1～32000 字符）

**作用**：仅创建任务，`status=draft`，**不会**自动跑四步。

**响应**：`{ "id": "<uuid>", "status": "draft" }`

---

## 4. `POST /api/runs/{run_id}/writer`

调用 LLM 生成 `layer1_output`（分镜 / 脚本 / 角色 / 对白）。

---

## 5. `POST /api/runs/{run_id}/director`

输入 DB 中的 `layer1_output` + `drama_input`，生成 `layer2_output.seedance_prompts`（**不**传入定妆图；不要求 `image_roles`）。

---

## 6. `POST /api/runs/{run_id}/makeup`

输入 `layer1_output`，LLM 规划定妆 → ModelArk `images.generate`，写入 `makeup_output.character_image_urls`。

---

## 7. `POST /api/runs/{run_id}/seedance`

读取 `layer2_output` + `makeup_output`：在 **BackgroundTasks** 中逐段 `generate_video` → 下载 → **ffmpeg** 拼接 →（若配置 Butterbase）上传 Storage，并更新 `layer3_output`。

**HTTP**：**202 Accepted**（见上文「`POST .../seedance`（异步）」）；**不要**对本次 POST 挂超长读超时等待成片结束。

### 7.1 `GET /api/runs/{run_id}/seedance/status`

返回当前 `seedance_job`（合并 `run_status`）；若 DB 已为 `status=done` 且存在 `layer3_output`，则直接返回 `phase: "done"` 及 `video_url` / `layer3` 摘要。

**成片阶段说明**：为降低 Ark `InvalidParameter` 风险，**不再向 Seedance 传 `resolution` 参数**（使用模型默认）。

---

## 8. `POST /api/runs/{run_id}/pipeline`

**条件**：`status=draft` 且 `layer1_output` / `layer2_output` / `makeup_output` / `layer3_output` 均为空。

**作用**：`202` 语义上为已接受（实际返回 JSON `accepted`），在 **BackgroundTasks** 中顺序执行四步；进度仍通过 `GET /api/runs/{id}` 轮询。

---

## 快速自测（curl）

```bash
BASE=http://127.0.0.1:8000
R=$(curl -sS -X POST "$BASE/api/runs" -H "Content-Type: application/json" \
  -d '{"drama":"你的故事"}')
ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -sS -m 300 -X POST "$BASE/api/runs/$ID/writer" | python3 -m json.tool
curl -sS -m 300 -X POST "$BASE/api/runs/$ID/director" | python3 -m json.tool
curl -sS -m 600 -X POST "$BASE/api/runs/$ID/makeup" | python3 -m json.tool
curl -sS -D - -o /tmp/sd.json -X POST "$BASE/api/runs/$ID/seedance"
# 期望首行含 HTTP/1.1 202；然后轮询：
while true; do
  P=$(curl -sS "$BASE/api/runs/$ID/seedance/status" | python3 -c "import sys,json; print(json.load(sys.stdin).get('phase',''))")
  echo "phase=$P"
  [ "$P" = "done" ] || [ "$P" = "failed" ] && break
  sleep 3
done
curl -sS "$BASE/api/runs/$ID" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('status'), (r.get('layer3_output') or {}).get('video_url'))"
```

---

## 安全与部署

- 当前 **无鉴权**，仅适合受信网络。
- **CORS**：`CORS_ORIGINS` 环境变量。
- 需本机 **ffmpeg** 在 PATH 或 `FFMPEG_PATH`（见 `GET /api/meta` → `ffmpeg.available`）。
