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
| 成片 | `POST /api/runs/{id}/seedance` | 已有 `layer2_output` **与** `makeup_output` | `layer3_output`，`done` / `failed` |

**推荐调度顺序**：编剧 → 导演 → 定妆 → Seedance（与前端默认一致）。导演 **仅** 消费 `layer1`；定妆 **仅** 消费 `layer1`；成片消费 **导演 + 定妆**。

**可选一键**：`POST /api/runs/{id}/pipeline`（`draft` 且无各阶段输出时）在 **后台** 顺序执行上述四步，行为与前端连调四次等价。

---

## 通用响应

### `GET /api/runs/{run_id}`

返回 SQLite 行 JSON（含 `status`、`layer*_output`、`makeup_output`、`error_*` 等）。

### 各 `POST .../writer|director|makeup|seedance`

成功或业务失败均返回 **HTTP 200**，body 形如：

```json
{
  "ok": true,
  "run": { "...": "与 GET /api/runs/{id} 相同 ..." }
}
```

若某步内部 `_fail`：`ok` 为 `false`，`run.status` 为 `failed`，见 `run.error_code` / `run.error_message`。

### 常见 HTTP 错误

| HTTP | 场景 |
|------|------|
| `404` | `run_id` 不存在 |
| `400` | 前置输出缺失（如未跑编剧就调导演） |
| `409` | 重复调用（如已有 `layer1_output` 再调 `writer`） |

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

读取 `layer2_output` + `makeup_output`：逐段 `generate_video` → 下载 → **ffmpeg** 拼接 →（若配置 Butterbase）上传 Storage。

**耗时**：与段数、每段时长、队列有关，请使用 **较长 HTTP 超时**（前端已对最后一步使用约 15 分钟 `timeout`）。

**成片阶段说明**：当前实现为降低 Ark `InvalidParameter` 风险，**不再向 Seedance 传 `resolution` 参数**（使用模型默认）。

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
curl -sS -m 900 -X POST "$BASE/api/runs/$ID/seedance" | python3 -m json.tool
```

---

## 安全与部署

- 当前 **无鉴权**，仅适合受信网络。
- **CORS**：`CORS_ORIGINS` 环境变量。
- 需本机 **ffmpeg** 在 PATH 或 `FFMPEG_PATH`（见 `GET /api/meta` → `ffmpeg.available`）。
