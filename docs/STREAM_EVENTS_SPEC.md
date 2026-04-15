# Stream Events Specification (v2 — Workflow Visualisation)

Backend endpoint: `POST /task`
Response format: **NDJSON** (`application/x-ndjson`) — each line is a valid JSON object.

---

## Connection

```typescript
const response = await fetch('/task', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ task, business_id, task_id, extras })
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n');
  buffer = lines.pop()!; // keep incomplete line in buffer
  for (const line of lines) {
    if (!line.trim()) continue;
    const event = JSON.parse(line);
    handleEvent(event);
  }
}
```

---

## Top-Level Event Types

| `type`      | Description                    |
|-------------|--------------------------------|
| `progress`  | Workflow step update           |
| `heartbeat` | Keep-alive (every ~2s idle)    |
| `result`    | Final output (always last)     |

---

## Progress Events (`type: "progress"`)

### Common Fields (all progress events)

```typescript
{
  type: "progress";
  event: string;       // see table below
  message: string;     // human-readable Turkish message with emoji
  timestamp: string;   // ISO 8601
  agent_id?: string;   // e.g. "orchestrator_1", "image_agent_2"
  agent_name?: string; // e.g. "orchestrator", "image_agent"
  status?: string;     // node state — see State Machine below
}
```

### Event Types

| `event`       | When                                  | Key Fields                                                     |
|---------------|---------------------------------------|----------------------------------------------------------------|
| `agent_start` | Agent begins execution                | `agent_id`, `parent_agent_id`, `model`, `tools_available`      |
| `llm_start`   | LLM call begins (agent is thinking)   | `agent_id`                                                     |
| `llm_end`     | LLM call returns (agent decided)      | `agent_id`, `message`, `tool_calls_planned`, token counts      |
| `tool_start`  | Tool execution begins                 | `agent_id`, `tool`, `is_agent_call`, `input_prompt` or `input_preview`, `edge_label` |
| `tool_end`    | Tool execution succeeds               | `agent_id`, `tool`, `is_agent_call`, `output_preview`, `edge_label`, `duration_ms`   |
| `tool_error`  | Tool execution fails                  | `agent_id`, `tool`, `error_code`, `retryable`, `user_message_tr`, `duration_ms`      |
| `agent_end`   | Agent completes                       | `agent_id`, `parent_agent_id`, `output_preview`                |
| `handoff`     | Direct agent handoff (rare in this project) | `from_agent_id`, `from_agent_name`, `to_agent_name`      |

---

## Full TypeScript Interface

```typescript
interface StreamEvent {
  type: "progress" | "heartbeat" | "result";
  timestamp: string;

  // --- progress events ---
  event?:
    | "agent_start"
    | "llm_start"
    | "llm_end"
    | "tool_start"
    | "tool_end"
    | "tool_error"
    | "agent_end"
    | "handoff";
  message?: string;

  // --- Hierarchy ---
  agent_id?: string;          // unique per agent instance: "{name}_{counter}"
  parent_agent_id?: string;   // null for root orchestrator
  agent_name?: string;

  // --- Node state ---
  status?:
    | "idle"       // agent_start: just created
    | "thinking"   // llm_start: LLM is processing
    | "decided"    // llm_end: LLM returned, plan visible
    | "executing"  // tool_start: running a tool or sub-agent
    | "waiting"    // tool_end: waiting for next action
    | "completed"  // agent_end: done successfully
    | "error";     // tool_error: something failed

  // --- Agent metadata (agent_start) ---
  model?: string;             // e.g. "model: gpt-4o-mini"
  tools_available?: string[]; // ["fetch_business", "image_agent_tool", ...]

  // --- LLM decision (llm_end) ---
  // `message` field contains LLM's reasoning text (Turkish)
  tool_calls_planned?: Array<{
    call_id: string;
    tool: string;
    is_agent_call: boolean;   // true = sub-agent wrapper
  }>;
  total_input_tokens?: number;
  total_output_tokens?: number;

  // --- Tool execution (tool_start / tool_end / tool_error) ---
  tool?: string;
  is_agent_call?: boolean;
  input_prompt?: string;      // sub-agent brief (when is_agent_call=true)
  input_preview?: Record<string, string>; // tool params (when is_agent_call=false)
  output_preview?: string;
  edge_label?: string;        // short text for connection lines (max ~80 chars)
  duration_ms?: number;       // tool execution time in milliseconds

  // --- Error details (tool_error) ---
  error_code?: string;        // "RATE_LIMIT" | "SERVER_ERROR" | "CONTENT_POLICY" | ...
  retryable?: boolean;
  user_message_tr?: string;   // Turkish user-facing error message
  service?: string;           // "google_ai" | "kling" | "late_api" | "fal_ai" | "serper"

  // --- Handoff (handoff) ---
  from_agent_id?: string;
  from_agent_name?: string;
  to_agent_name?: string;

  // --- Final result (type="result") ---
  success?: boolean;
  output?: string;
  error?: string;
  log_path?: string;
}
```

---

## Node State Machine

Each agent node on the canvas should follow this state machine:

```
  agent_start        llm_start        llm_end         tool_start
 ┌──────────┐    ┌──────────────┐   ┌──────────┐   ┌────────────┐
 │   IDLE   │───▶│   THINKING   │──▶│ DECIDED  │──▶│ EXECUTING  │
 └──────────┘    └──────────────┘   └──────────┘   └─────┬──────┘
                                         ▲               │
                                         │   tool_end    │
                                         │ ┌──────────┐  │
                                         └─│ WAITING  │◀─┘
                                           └──────────┘
                                                │
                                           agent_end
                                           ┌──────────┐
                                           │COMPLETED │
                                           └──────────┘
```

An agent may go through `THINKING → DECIDED → EXECUTING → WAITING` **multiple times** (multi-turn).
On error: `EXECUTING → ERROR` (the tool_error event), then the agent may retry (back to THINKING).

---

## Agent Architecture (This Project)

```
orchestrator (gpt-4o-mini)
├── Tools: fetch_business, upload_file, list_files, delete_file,
│          get_document, save_document, query_documents,
│          post_on_instagram, post_carousel_on_instagram,
│          post_on_youtube, post_on_tiktok, post_carousel_on_tiktok,
│          post_on_linkedin, post_carousel_on_linkedin, report_error
│
├── image_agent_tool → spawns image_agent (gpt-4o)
│   └── Tools: generate_image
│
├── video_agent_tool → spawns video_agent (gpt-4o)
│   └── Tools: generate_video, generate_video_kling, add_audio_to_video
│
├── marketing_agent_tool → spawns marketing_agent (gpt-4o)
│   ├── Tools: create_weekly_plan, get_plans, get_todays_posts,
│   │          save_instagram_post, get_instagram_posts,
│   │          save_youtube_video, get_youtube_videos,
│   │          get_marketing_memory, update_marketing_memory, get_admin_notes
│   ├── image_agent_tool → spawns image_agent (nested!)
│   └── video_agent_tool → spawns video_agent (nested!)
│
└── analysis_agent_tool → spawns analysis_agent (gpt-4o)
    └── Tools: web_search, scrape_for_seo, scrape_competitors,
               check_serp_position, save_swot_report, save_seo_report,
               save_seo_keywords, save_seo_summary, get_seo_keywords,
               get_reports, save_instagram_report
```

**IMPORTANT:** `marketing_agent` can call `image_agent_tool` and `video_agent_tool` internally. This creates **3 levels of nesting**:

```
orchestrator_1
└── marketing_agent_2 (via marketing_agent_tool)
    └── image_agent_3 (via image_agent_tool, nested inside marketing)
        └── generate_image (actual tool)
```

Use `parent_agent_id` to build the tree correctly.

---

## Identifying Sub-Agent Calls vs Regular Tools

**Convention:** Any tool whose name ends with `_agent_tool` is a sub-agent wrapper.

```typescript
const isSubAgent = event.is_agent_call === true;
// OR: event.tool?.endsWith('_agent_tool')
```

When `is_agent_call` is true:
- `input_prompt` contains the brief/prompt passed to the sub-agent
- The next `agent_start` event with matching `parent_agent_id` is the sub-agent spawning
- The corresponding `tool_end` contains the sub-agent's final output in `output_preview`

---

## Example: Full Stream for "Logo olustur ve Instagram'da paylas"

```jsonl
{"type":"progress","event":"agent_start","agent_id":"orchestrator_1","parent_agent_id":null,"agent_name":"orchestrator","model":"model: gpt-4o-mini","tools_available":["image_agent_tool","video_agent_tool","marketing_agent_tool","analysis_agent_tool","fetch_business","upload_file","list_files","delete_file","get_document","save_document","query_documents","post_on_instagram","post_carousel_on_instagram","post_on_youtube","post_on_tiktok","post_carousel_on_tiktok","post_on_linkedin","post_carousel_on_linkedin","report_error"],"status":"idle","message":"🤖 orchestrator agent başladı","timestamp":"2026-03-29T13:00:00.000"}

{"type":"progress","event":"llm_start","agent_id":"orchestrator_1","agent_name":"orchestrator","status":"thinking","message":"💭 orchestrator düşünüyor...","timestamp":"2026-03-29T13:00:00.100"}

{"type":"progress","event":"llm_end","agent_id":"orchestrator_1","agent_name":"orchestrator","status":"decided","message":"Kullanıcı logo oluşturup Instagram'da paylaşmak istiyor. Önce business bilgilerini alacağım.","tool_calls_planned":[{"call_id":"call_001","tool":"fetch_business","is_agent_call":false}],"total_input_tokens":1250,"total_output_tokens":85,"timestamp":"2026-03-29T13:00:02.500"}

{"type":"progress","event":"tool_start","agent_id":"orchestrator_1","agent_name":"orchestrator","tool":"fetch_business","is_agent_call":false,"status":"executing","input_preview":{"business_id":"abc123"},"edge_label":"business_id=abc123","message":"🔧 fetch_business çalıştırılıyor...","timestamp":"2026-03-29T13:00:02.510"}

{"type":"progress","event":"tool_end","agent_id":"orchestrator_1","agent_name":"orchestrator","tool":"fetch_business","is_agent_call":false,"status":"waiting","output_preview":"{'name': 'Cafe Moda', 'sector': 'food_beverage', 'website': 'https://cafemoda.com'}","edge_label":"{'name': 'Cafe Moda', 'sector': 'food_beverage', 'website': 'https://cafemoda.…","duration_ms":320,"message":"✅ fetch_business tamamlandı","timestamp":"2026-03-29T13:00:02.830"}

{"type":"progress","event":"llm_start","agent_id":"orchestrator_1","agent_name":"orchestrator","status":"thinking","message":"💭 orchestrator düşünüyor...","timestamp":"2026-03-29T13:00:02.840"}

{"type":"progress","event":"llm_end","agent_id":"orchestrator_1","agent_name":"orchestrator","status":"decided","message":"Business bilgisi alındı. Şimdi image_agent_tool ile logo oluşturacağım.","tool_calls_planned":[{"call_id":"call_002","tool":"image_agent_tool","is_agent_call":true}],"total_input_tokens":2100,"total_output_tokens":210,"timestamp":"2026-03-29T13:00:04.200"}

{"type":"progress","event":"tool_start","agent_id":"orchestrator_1","agent_name":"orchestrator","tool":"image_agent_tool","is_agent_call":true,"status":"executing","input_prompt":"Cafe Moda markası için profesyonel minimalist logo. Kahve temalı, modern, sade tasarım. Renk paleti: kahverengi tonları ve krem.","edge_label":"Cafe Moda markası için profesyonel minimalist logo. Kahve temalı, modern, sad…","message":"🔧 image_agent_tool çalıştırılıyor...","timestamp":"2026-03-29T13:00:04.210"}

{"type":"progress","event":"agent_start","agent_id":"image_agent_2","parent_agent_id":"orchestrator_1","agent_name":"image_agent","model":"model: gpt-4o","tools_available":["generate_image"],"status":"idle","message":"🤖 image_agent agent başladı","timestamp":"2026-03-29T13:00:04.220"}

{"type":"progress","event":"llm_start","agent_id":"image_agent_2","agent_name":"image_agent","status":"thinking","message":"💭 image_agent düşünüyor...","timestamp":"2026-03-29T13:00:04.230"}

{"type":"progress","event":"llm_end","agent_id":"image_agent_2","agent_name":"image_agent","status":"decided","message":null,"tool_calls_planned":[{"call_id":"call_003","tool":"generate_image","is_agent_call":false}],"total_input_tokens":2800,"total_output_tokens":150,"timestamp":"2026-03-29T13:00:05.800"}

{"type":"progress","event":"tool_start","agent_id":"image_agent_2","agent_name":"image_agent","tool":"generate_image","is_agent_call":false,"status":"executing","input_preview":{"prompt":"A minimalist coffee shop logo...","business_id":"abc123"},"edge_label":"prompt=A minimalist coffee shop logo..., business_id=abc123","message":"🔧 generate_image çalıştırılıyor...","timestamp":"2026-03-29T13:00:05.810"}

{"type":"heartbeat","timestamp":"2026-03-29T13:00:07.810"}

{"type":"heartbeat","timestamp":"2026-03-29T13:00:09.810"}

{"type":"progress","event":"tool_end","agent_id":"image_agent_2","agent_name":"image_agent","tool":"generate_image","is_agent_call":false,"status":"waiting","output_preview":"https://storage.googleapis.com/bucket/images/abc123/logo_20260329.png","edge_label":"https://storage.googleapis.com/bucket/images/abc123/logo_20260329.png","duration_ms":5200,"message":"✅ generate_image tamamlandı","timestamp":"2026-03-29T13:00:11.010"}

{"type":"progress","event":"agent_end","agent_id":"image_agent_2","parent_agent_id":"orchestrator_1","agent_name":"image_agent","status":"completed","output_preview":"Logo başarıyla oluşturuldu ve kaydedildi.\nPath: images/abc123/logo_20260329.png\nURL: https://storage.googleapis.com/bucket/images/abc123/logo_20260329.png","message":"✅ image_agent agent tamamlandı","timestamp":"2026-03-29T13:00:12.500"}

{"type":"progress","event":"tool_end","agent_id":"orchestrator_1","agent_name":"orchestrator","tool":"image_agent_tool","is_agent_call":true,"status":"waiting","output_preview":"Logo başarıyla oluşturuldu ve kaydedildi.\nPath: images/abc123/logo_20260329.png\nURL: https://storage...","edge_label":"Logo başarıyla oluşturuldu ve kaydedildi.\nPath: images/abc123/logo_20260329.pn…","duration_ms":8290,"message":"✅ image_agent_tool tamamlandı","timestamp":"2026-03-29T13:00:12.500"}

{"type":"progress","event":"llm_start","agent_id":"orchestrator_1","agent_name":"orchestrator","status":"thinking","message":"💭 orchestrator düşünüyor...","timestamp":"2026-03-29T13:00:12.510"}

{"type":"progress","event":"llm_end","agent_id":"orchestrator_1","agent_name":"orchestrator","status":"decided","message":"Logo hazır. Şimdi Instagram'da paylaşacağım.","tool_calls_planned":[{"call_id":"call_004","tool":"post_on_instagram","is_agent_call":false}],"total_input_tokens":3500,"total_output_tokens":180,"timestamp":"2026-03-29T13:00:14.000"}

{"type":"progress","event":"tool_start","agent_id":"orchestrator_1","agent_name":"orchestrator","tool":"post_on_instagram","is_agent_call":false,"status":"executing","input_preview":{"instagram_id":"acc_xxxxx","image_url":"https://storage.../logo_20260329.png","caption":"☕ Cafe Moda..."},"edge_label":"instagram_id=acc_xxxxx, image_url=https://storage.../logo_20260329.png, capt…","message":"🔧 post_on_instagram çalıştırılıyor...","timestamp":"2026-03-29T13:00:14.010"}

{"type":"progress","event":"tool_end","agent_id":"orchestrator_1","agent_name":"orchestrator","tool":"post_on_instagram","is_agent_call":false,"status":"waiting","output_preview":"Post başarıyla paylaşıldı: https://instagram.com/p/abc123","edge_label":"Post başarıyla paylaşıldı: https://instagram.com/p/abc123","duration_ms":2100,"message":"✅ post_on_instagram tamamlandı","timestamp":"2026-03-29T13:00:16.110"}

{"type":"progress","event":"agent_end","agent_id":"orchestrator_1","parent_agent_id":null,"agent_name":"orchestrator","status":"completed","output_preview":"Logo oluşturuldu ve Instagram'da paylaşıldı.\n\nLogo: https://storage.../logo_20260329.png\nInstagram: https://instagram.com/p/abc123","message":"✅ orchestrator agent tamamlandı","timestamp":"2026-03-29T13:00:17.500"}

{"type":"result","success":true,"output":"Logo oluşturuldu ve Instagram'da paylaşıldı.\n\nLogo: https://storage.googleapis.com/bucket/images/abc123/logo_20260329.png\nInstagram Post: https://instagram.com/p/abc123","log_path":"logs/run-20260329-130000.log","timestamp":"2026-03-29T13:00:17.510"}
```

---

## Frontend Workflow Visualisation Guide

### Building the Tree

```typescript
interface WorkflowNode {
  id: string;           // agent_id (e.g. "orchestrator_1")
  name: string;         // agent_name
  model: string;
  status: NodeStatus;
  parent_id: string | null;
  tools_available: string[];
  children: WorkflowNode[];    // sub-agents
  actions: ActionEntry[];      // tools called by this agent
  llm_messages: string[];      // LLM reasoning texts
  output: string | null;
}

interface ActionEntry {
  tool: string;
  is_agent_call: boolean;
  status: 'executing' | 'completed' | 'error';
  input_prompt?: string;       // for sub-agent calls
  input_preview?: Record<string, string>; // for regular tools
  output_preview?: string;
  edge_label?: string;
  duration_ms?: number;
  error?: { code: string; retryable: boolean; message_tr: string };
  child_agent_id?: string;     // links to sub-agent node
}
```

### Mapping Events to UI Actions

```typescript
function handleEvent(event: StreamEvent) {
  if (event.type === 'heartbeat') return; // ignore
  if (event.type === 'result') { finalizeWorkflow(event); return; }

  switch (event.event) {
    case 'agent_start':
      // Create a new node on the canvas
      // Connect to parent if parent_agent_id exists
      // Show available tools as small badges
      createNode(event);
      break;

    case 'llm_start':
      // Show thinking animation on the node (pulsing brain icon)
      setNodeStatus(event.agent_id, 'thinking');
      break;

    case 'llm_end':
      // Show LLM's reasoning in a speech bubble
      // Show planned tool calls as ghost/preview nodes
      setNodeStatus(event.agent_id, 'decided');
      if (event.message) showThoughtBubble(event.agent_id, event.message);
      if (event.tool_calls_planned) showPlannedTools(event.agent_id, event.tool_calls_planned);
      break;

    case 'tool_start':
      // Create tool node (small), connect with edge
      // If is_agent_call: show prompt on edge, use agent icon
      // If regular tool: show params on edge, use gear icon
      createToolNode(event);
      animateEdge(event.agent_id, event.tool); // flowing dots
      break;

    case 'tool_end':
      // Mark tool node as completed (green check)
      // Show output on return edge
      // Show duration badge
      completeToolNode(event);
      break;

    case 'tool_error':
      // Mark tool node as error (red X)
      // Show error message, retryable badge
      errorToolNode(event);
      break;

    case 'agent_end':
      // Mark agent node as completed
      // Show final output preview
      completeNode(event);
      break;

    case 'handoff':
      // Draw arrow from one agent to another (rare in this project)
      drawHandoffEdge(event);
      break;
  }
}
```

### Visual Styling Guide

| Node Type       | Icon | Shape          | Color (active) | Color (done) |
|-----------------|------|----------------|----------------|--------------|
| Orchestrator    | 🎯   | Large rounded  | Blue           | Green        |
| Image Agent     | 🎨   | Medium rounded | Purple         | Green        |
| Video Agent     | 🎬   | Medium rounded | Orange         | Green        |
| Marketing Agent | 📱   | Medium rounded | Pink           | Green        |
| Analysis Agent  | 📊   | Medium rounded | Teal           | Green        |
| Regular Tool    | ⚙️   | Small pill     | Gray           | Green        |
| Error           | ❌   | Small pill     | Red            | Red          |

### Status Animations

| Status     | Animation                                      |
|------------|-------------------------------------------------|
| idle       | Static, slightly dimmed                         |
| thinking   | Pulsing glow / spinning brain icon              |
| decided    | Brief flash, speech bubble appears              |
| executing  | Flowing dots on edge / progress spinner         |
| waiting    | Static, full opacity                            |
| completed  | Green checkmark, subtle scale animation         |
| error      | Red shake animation, error badge                |
