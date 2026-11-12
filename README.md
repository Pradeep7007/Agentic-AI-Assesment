# Agentic AI assessment: integrate the Document Agent

A working AI agent you run on **your own computer** with **your own free Groq API key**. It chats, uses tools
(SQL, charts, web, OpenML), reads documents you upload (PDF, DOCX, text, scans), answers with citations, and sends
logs, metrics and traces to Grafana. Your job: **finish the integration** (nine tasks), then push to GitHub. Automated tests grade your work.

```
Gradio UI :7860 --> FastAPI agent :8000 --> Groq (LLM) · Qdrant (vectors) · SQLite · MCP notes and tasks server
                          |
                          +--> OpenTelemetry Collector --> Tempo (traces) · Prometheus (metrics) · Loki (logs) --> Grafana :3000
```

## What you have to do
Nine tasks, in order, 34 points: **[docs/TASK.md](docs/TASK.md)** (what to do, which files, how it is graded). Submit with **[docs/SUBMIT.md](docs/SUBMIT.md)**
before **12 Nov 2026, 23:59 IST**. You write only the integration; the hard parts are provided. This README is the setup guide.

**Please also try your agent with your own Groq key.** The autograder runs a scripted model and never calls Groq, so it cannot tell you how your agent behaves for real. Run it with your key (`docker compose up`, then the UI at http://localhost:7860) and chat with it: upload a document, ask for an outline, add a task. That is for your own benefit and is not graded. **The final grade is the score of the CI run only; there is no manual review of your code.**

**About the red cross:** the GitHub run turns red until all 34 checks pass. That is intended. It still records your score (open the run's **Summary** tab); submit it anyway, partial points count and your best attempt is kept (see [docs/SUBMIT.md](docs/SUBMIT.md)).

## What you need on your computer
| Tool | Check | Install |
|---|---|---|
| Docker (with Compose) | `docker --version` | https://www.docker.com/products/docker-desktop/ |
| uv (Python manager) | `uv --version` | https://docs.astral.sh/uv/getting-started/installation/ |
| Git | `git --version` | https://git-scm.com/ |
| A Groq API key (free) | opens a page | https://console.groq.com/keys (sign up, **Create API Key**, copy it) |

About 4 GB of free RAM and 5 GB of disk. Windows: use **WSL 2** (Docker Desktop's default) and run the commands in the WSL terminal.
macOS / Linux: any terminal.

### About the Groq key
- The free tier is enough. Limits you will notice: a few thousand tokens per request and a daily token cap.
  If you see "rate limited" in the chat, wait a minute (the agent tells you how long).
- The key stays on **your** machine in `.env` (git ignores it). **Never commit it, never paste it in the submission form.**
- The autograder on GitHub **does not use your key**: it runs your code with a scripted model. So your key only powers your own experiments.

## Set it up (about 15 minutes, once)
```bash
# 1. your copy of the project: on GitHub press "Use this template" > "Create a new repository" (Private, your own account)
git clone https://github.com/<you>/<your-repo>
cd <your-repo>

# 2. install the local safety hooks (they stop you editing locked files); installs only pre-commit, about a second
uv run --only-group hooks pre-commit install

# 3. add your Groq key
cp .env.example .env            # then open .env and paste your key after GROQ_API_KEY=

# 4. check everything is ready (Docker running, key valid, ports free)
bash scripts/check_setup.sh

# 5. start it (the first build downloads models: 5-10 minutes)
docker compose up --build -d
```
Open **http://localhost:7860** (the chat UI) and **http://localhost:3000** (Grafana, dashboard *Agent - API, tokens, models, tools*).
Stop everything with `docker compose down`.

If port 6333 is taken on your machine: `QDRANT_PORT=6335 docker compose up -d`.

### Try it (5 minutes)
0. After task 5 the UI asks you to **register and log in** (Account box, right side); before that it works anonymously.
1. In the UI, upload `samples/attention-is-all-you-need.pdf` and wait about a minute (it reads, splits into sections, embeds).
2. Ask *"How does multi-head attention work?"*: the answer cites `[document › section, page]`.
3. Ask *"Top 5 artists in the Chinook database as a bar chart"*: SQL + chart, no document search (see the **Steps** and **Chart** tabs).
4. Upload `samples/react-reasoning-and-acting-scanned.pdf` (an image-only PDF): the knowledge base tab shows *OCR pages*.
5. Open Grafana: API hits, tokens per model, tool calls, ingest latency, logs. Click a log line's `trace_id` to jump to the trace.

## Where things are
- You edit **nine files under `src/app/`** (listed in `docs/TASK.md`, one column per task), plus new files in `src/app/migrations/` and `src/app/dashboards/`, this README and `.gitignore`.
- `src/app/users.py`, `src/app/mcp_server/taskstore.py`, `src/app/kb/store.py` are provided building blocks: read their docstrings.
- Everything else is **locked**, including the rest of `src/app/` (fake model, telemetry, debug routes), tests, Docker files, observability config and UI. Changing it makes your submission invalid.

## Your development loop
```bash
# edit src/app/...
docker compose up -d --build api notes-mcp   # rebuild and restart the API and the MCP server (about 20 s once images are cached)
docker compose logs -f api             # JSON logs; Ctrl-C to leave
curl localhost:8000/debug/telemetry    # metrics and recent log events your code recorded (what the grader reads)
bash scripts/local_eval.sh             # the full autograder on your machine, exactly like GitHub (builds 2 images; a few minutes)
```
`local_eval.sh` prints your score with one PASS/FAIL line per check. Fix, re-run, then push.

## Submit
Push to `main`, wait for the GitHub Action, and submit the run URL: see **[docs/SUBMIT.md](docs/SUBMIT.md)**.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `check_setup.sh` says Groq key rejected | copy the key again from console.groq.com/keys; no quotes or spaces in `.env` |
| Chat says "rate limited" / "too large" | wait the time it says; start a new session in the UI for "too large" |
| `all predefined address pools have been fully subnetted` | a VPN confuses Docker: disconnect it, or run `docker network prune` |
| Port already in use | `docker compose down`, or stop the other program (`check_setup.sh` names the port) |
| Commit blocked: "Locked files differ" | you changed a locked file; the message shows the `git restore` command |
| Ingestion is slow | a scanned page takes about 10-15 s (OCR); text PDFs take seconds. Use the small `samples/` files |
| Grafana is empty | send some chat messages first; metrics appear within 10-20 s |
| Task or note tools fail with `UNAUTHENTICATED` | log in first; then check the interceptor forwards the token (task 9) and `docker compose ps` shows `notes-mcp` running |
| `/login` or MCP says a table does not exist | the migration did not run: `docker compose run --rm migrate` and look at its output |

Use this file for your own notes: how you solved each task, a screenshot of your Grafana panel. It is not graded, but graders may read it.

## Implementation Notes

### Task 1: Define the Agent (`src/app/agent.py`)
- Registered all tools in `build_agent`: `S1_TOOLS`, `build_kb_tools(kb)`, `await mcp_tools()`, and `build_custom_tools(kb)`.
- Implemented `@dynamic_prompt` returning `SYSTEM_PROMPT` plus `kb.prompt_block(kb_id)` dynamically on each model invocation, where `kb_id` is resolved from `request.runtime.context.user_id` or `session_id`.
- Passed `middleware=[dynamic_kb_prompt, ShrinkOldToolResults()]`, `context_schema=Ctx`, and `checkpointer=checkpointer` to `create_agent`.

### Task 2: Make the Tools Async (`src/app/tools_s1.py`, `src/app/kb/tools.py`)
- Converted `get_weather`, `web_fetch`, `sql_query`, and `search_knowledge_base` to `async def`.
- In `web_fetch`, used `httpx.AsyncClient` with non-blocking extraction via `asyncio.to_thread(trafilatura.extract, ...)`.
- In `sql_query`, encapsulated sqlite execution in a helper function invoked via `asyncio.to_thread`.
- In `search_knowledge_base`, called `kb.search` and `kb.resolve_doc_name` via `asyncio.to_thread`.

### Task 3: Chat Memory in SQLite (`src/app/persistence.py`, `src/app/main.py`)
- Replaced `InMemorySaver` with `AsyncSqliteSaver.from_conn_string` inside `open_checkpointer` async context manager, ensuring the checkpoint directory exists.
- Updated `main.py` lifespan to open the checkpointer at startup and hold it open for the app lifecycle.

### Task 4: Alembic Migration (`src/app/migrations/0001_create_users.py`)
- Created revision `0001_create_users` defining tables `users`, `tokens`, and `threads` with all required columns.
- Implemented `upgrade` to create the tables and `downgrade` to drop them in reverse dependency order.

### Task 5: User Accounts and Auth (`src/app/main.py`)
- Added `POST /users` (returns 201 with `user_id`, 409 if taken, 422 if credentials invalid).
- Added `POST /login` (returns 200 with `token` and `user_id`, 401 on failure).
- Added `get_current_user` FastAPI dependency validating `Authorization: Bearer <token>` via `UserStore.user_for_token`.
- Added `GET /me`, `POST /logout` (revoking the active token), and `DELETE /users/me`.

### Task 6: One Knowledge Base per User (`src/app/context.py`, `src/app/agent.py`, `src/app/kb/tools.py`, `src/app/main.py`)
- Extended `Ctx` with `user_id` and `token`.
- Protected `/agent` and `/upload` with `get_current_user` and thread ownership checking via `claim_thread` (answering 403 on conflict).
- Switched knowledge base indexing, querying, and dynamic prompting to key on `user_id`.
- Wired `DELETE /users/me` to call `kb.reset(user_id)`.

### Task 7: Two Tools with Observability (`src/app/custom_tools.py`, `src/app/dashboards/outline.json`)
- Implemented `kb_stats(top_keywords=5)` validating `1 <= top_keywords <= 20` (raising `ERROR[INVALID_INPUT]`), recording counter `kbstats.calls` and logging `kb_stats_done`.
- Implemented `document_outline(doc_name)` resolving document name, retrieving sections, formatting outline with page numbers, recording counter `outline.calls` and logging `document_outline_done`.
- Created Grafana dashboard `src/app/dashboards/outline.json` for outline metrics and logs.

### Task 8: Manage Knowledge Base with Tools (`src/app/custom_tools.py`)
- Implemented `delete_document(doc_name)` deleting the user's document via `kb.delete_document` and returning remaining count.
- Implemented `update_document(doc_name, source)` resolving upload, ingesting the new version under the existing name first, and deleting the old document only upon success.

### Task 9: Notes and Tasks MCP Server with Per-User Auth (`src/app/mcp_server/server.py`, `src/app/agent.py`)
- In `server.py`, registered all 8 tools (`add_note`, `list_notes`, `delete_note`, `add_task`, `list_tasks`, `set_task_status`, `delete_task`, `task_summary`).
- Extracted caller identity using `ctx.request_context.request.headers` via `current_user_id`, raising `ToolError("ERROR[UNAUTHENTICATED]: ...")` if unauthorized.
- In `agent.py`, implemented `mcp_auth_interceptor` forwarding `Authorization: Bearer <runtime.context.token>` to the MCP server.
