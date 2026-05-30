"""
api/server.py
--------------
JOSEPH REST API — Phase 8.

Full FastAPI server that exposes Joseph's capabilities
as HTTP endpoints. This enables:
- Mobile app integration
- Browser extension
- Third-party integrations
- Remote access (local network)

Endpoints:
  GET  /health          — Health check
  POST /chat            — Send a message, get a response
  POST /voice/text      — Process transcribed voice text
  GET  /memory/status   — Memory system status
  GET  /memory/facts    — All stored facts
  POST /memory/save     — Save a memory
  GET  /notes           — List notes
  POST /notes           — Add a note
  GET  /tasks           — List tasks
  POST /tasks           — Add a task
  GET  /weather         — Current weather
  GET  /calendar        — Upcoming events
  GET  /emails          — Recent emails
  POST /automation/run  — Run an automation command
  GET  /system/status   — Full system status

Run with:
    python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
"""

import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from configs.settings import settings
from hyper.bootstrap import (
    enhance_response,
    finalize_hyper_turn,
    get_context_enhancement,
    get_hyper_dashboard_data,
    prepare_hyper_turn,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# App instance
# ------------------------------------------------------------------ #

app = FastAPI(
    title="JOSEPH AI Assistant API",
    description="Local AI assistant REST API — Phase 8",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
# Global state (injected by main.py when server starts)
# ------------------------------------------------------------------ #

_state = {
    "llm": None,
    "memory": None,
    "personality": None,
    "weather": None,
    "notes": None,
    "scheduler": None,
    "google": None,
    "tool_dispatcher": None,
    "hyper": None,
    "started_at": datetime.now().isoformat(),
}


def inject_services(**kwargs) -> None:
    """Inject services into the API state. Called from main.py."""
    _state.update(kwargs)
    logger.info(f"API services injected: {list(kwargs.keys())}")


# ------------------------------------------------------------------ #
# Request/Response Models
# ------------------------------------------------------------------ #

class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    include_memory: bool = True


class ChatResponse(BaseModel):
    response: str
    model: str
    timestamp: str
    was_automated: bool = False


class MemorySaveRequest(BaseModel):
    content: str
    tags: Optional[list[str]] = None


class NoteRequest(BaseModel):
    content: str
    category: str = "general"


class TaskRequest(BaseModel):
    title: str
    priority: int = 2
    due_date: Optional[str] = None


class AutomationRequest(BaseModel):
    command: str


class ReminderRequest(BaseModel):
    message: str
    at_time: Optional[str] = None
    in_minutes: Optional[int] = None
    in_hours: Optional[float] = None


# ------------------------------------------------------------------ #
# Health & Status
# ------------------------------------------------------------------ #

@app.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "ok",
        "assistant": settings.JOSEPH_NAME,
        "version": "2.0.0",
        "phase": 8,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/system/status")
async def system_status():
    """Full system status."""
    status = {
        "assistant": settings.JOSEPH_NAME,
        "model": settings.OLLAMA_MODEL,
        "started_at": _state["started_at"],
        "services": {
            "llm": _state["llm"] is not None,
            "memory": _state["memory"] is not None,
            "weather": _state["weather"] is not None,
            "notes": _state["notes"] is not None,
            "scheduler": _state["scheduler"] is not None,
            "google": _state["google"] is not None and _state["google"].is_available if _state["google"] else False,
            "tool_dispatcher": _state["tool_dispatcher"] is not None,
            "hyper": _state["hyper"] is not None,
        },
    }

    if _state["memory"]:
        status["memory_stats"] = _state["memory"].get_status()

    return status


# ------------------------------------------------------------------ #
# Chat
# ------------------------------------------------------------------ #

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to Joseph and get a response.

    Handles both regular chat and automation commands.
    """
    if not _state["llm"]:
        raise HTTPException(status_code=503, detail="LLM not available")

    llm = _state["llm"]
    memory = _state["memory"]
    personality = _state["personality"]
    if _state.get("hyper") and memory and hasattr(_state["hyper"], "set_session_context"):
        _state["hyper"].set_session_context(getattr(memory, "session_id", None))

    # Try automation first
    was_automated = False
    response_text = ""
    turn_started = time.perf_counter()

    if _state["tool_dispatcher"]:
        dispatcher = _state["tool_dispatcher"]
        dispatcher.attach_llm(llm)
        response_text, was_automated = dispatcher.dispatch(request.message)

    # Fall back to LLM chat
    if not was_automated:
        try:
            from brain.prompts import get_system_prompt

            messages = []
            memory_context = ""

            if memory and request.include_memory:
                memory.add_user_message(request.message)
                messages = memory.get_conversation_history()
                memory_context = memory.get_context_for_llm(query=request.message)
                hyper_packet = prepare_hyper_turn(_state.get("hyper"), request.message, memory=memory)
                if hyper_packet.get("system_context"):
                    memory_context = (
                        f"{memory_context}\n\n{hyper_packet['system_context']}"
                        if memory_context
                        else hyper_packet["system_context"]
                    )
                extra_context = get_context_enhancement(_state.get("hyper"), request.message)
                if extra_context:
                    memory_context = f"{memory_context}\n\n{extra_context}" if memory_context else extra_context

            system_prompt = get_system_prompt(
                user_name=settings.USER_NAME,
                memory_context=memory_context,
            )

            response_text = llm.chat(
                messages=messages,
                system_prompt=system_prompt,
            )

            response_text = enhance_response(
                _state.get("hyper"),
                request.message,
                response_text,
                context={"mode": "api"},
            )

            if memory:
                memory.add_assistant_message(response_text)
            finalize_hyper_turn(
                _state.get("hyper"),
                request.message,
                response_text,
                elapsed_seconds=time.perf_counter() - turn_started,
                memory=memory,
            )

        except Exception as e:
            logger.error(f"API chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        response=response_text,
        model=settings.OLLAMA_MODEL,
        timestamp=datetime.now().isoformat(),
        was_automated=was_automated,
    )


@app.get("/system/diagnostics")
async def system_diagnostics():
    """Return hyper-layer diagnostics when available."""
    hyper = _state.get("hyper")
    if not hyper:
        return {"available": False, "message": "Hyper layer not enabled"}
    try:
        monitor = getattr(hyper, "_system_monitor", None)
        gpu = getattr(hyper, "_gpu_manager", None)
        learning = getattr(hyper, "_learning_engine", None)
        web = getattr(hyper, "_web_intelligence", None)
        planner = getattr(hyper, "_task_planner", None)
        return {
            "available": True,
            "hyper": hyper.get_status(),
            "monitor": monitor.get_diagnostics() if monitor else None,
            "gpu": gpu.get_status() if gpu else None,
            "learning": learning.get_stats() if learning else None,
            "web_cache_entries": web.get_cache_size() if web else 0,
            "plans": planner.get_active_plans() if planner else [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard")
async def dashboard():
    """Serve a simple real-time diagnostics dashboard."""
    return HTMLResponse("""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>JOSEPH Hyper Diagnostics</title>
      <style>
        :root { color-scheme: dark; --bg:#101214; --panel:#171a1f; --card:#1f2430; --text:#e8eef7; --muted:#8a94a6; --accent:#6fb2ff; --good:#53d18b; --warn:#ffcc66; --bad:#ff7b7b; }
        body { margin:0; font-family: Segoe UI, system-ui, sans-serif; background: linear-gradient(180deg, #0c0f14, #11151b 35%, #0c0f14); color:var(--text); }
        .wrap { max-width: 1280px; margin: 0 auto; padding: 24px; }
        h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: .5px; }
        .sub { color: var(--muted); margin-bottom: 20px; }
        .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:16px; }
        .card { background: rgba(31,36,48,.92); border: 1px solid rgba(111,178,255,.18); border-radius: 16px; padding: 16px; box-shadow: 0 20px 50px rgba(0,0,0,.2); }
        .card h2 { margin: 0 0 12px; font-size: 14px; text-transform: uppercase; letter-spacing: 1.2px; color: var(--accent); }
        .row { display:flex; justify-content:space-between; gap:12px; padding:6px 0; border-bottom: 1px solid rgba(255,255,255,.05); }
        .row:last-child { border-bottom: 0; }
        .k { color: var(--muted); }
        .v { text-align:right; overflow-wrap:anywhere; }
        .status { display:inline-block; padding:4px 10px; border-radius:999px; background: rgba(83,209,139,.15); color: var(--good); font-weight:600; }
        .warn { color: var(--warn); }
        .bad { color: var(--bad); }
        .trace { font-family: Consolas, monospace; font-size: 12px; white-space: pre-wrap; color:#d9e7ff; max-height: 220px; overflow:auto; }
        .footer { margin-top: 18px; color: var(--muted); font-size: 12px; }
      </style>
    </head>
    <body>
      <div class="wrap">
        <h1>JOSEPH Hyper Diagnostics</h1>
        <div class="sub">Real-time status for the hyper layer, memory, agents, GPU, and research cache.</div>
        <div class="grid">
          <section class="card"><h2>System Status</h2><div id="system"></div></section>
          <section class="card"><h2>Performance</h2><div id="performance"></div></section>
          <section class="card"><h2>Agent Activity</h2><div id="agents"></div></section>
          <section class="card"><h2>Memory</h2><div id="memory"></div></section>
          <section class="card"><h2>Research</h2><div id="research"></div></section>
          <section class="card"><h2>GPU</h2><div id="gpu"></div></section>
          <section class="card"><h2>Self-Improvement</h2><div id="improvement"></div></section>
        </div>
        <div class="footer">Auto-refreshing every 2 seconds from <code>/dashboard/data</code>.</div>
      </div>
      <script>
        const fmt = v => (v === null || v === undefined || v === '') ? '—' : String(v);
        function rows(obj) {
          return Object.entries(obj || {}).map(([k, v]) => `<div class="row"><div class="k">${k}</div><div class="v">${fmt(v)}</div></div>`).join('');
        }
        function nested(title, obj) {
          if (Array.isArray(obj)) return `<div class="trace">${obj.map((v,i)=>`${i+1}. ${typeof v === 'object' ? JSON.stringify(v, null, 2) : v}`).join('\n\n')}</div>`;
          if (typeof obj === 'object' && obj !== null) return rows(obj);
          return `<div class="v">${fmt(obj)}</div>`;
        }
        async function refresh() {
          try {
            const res = await fetch('/dashboard/data');
            const data = await res.json();
            document.getElementById('system').innerHTML = rows(data.system || {});
            document.getElementById('performance').innerHTML = rows(data.performance || {});
            document.getElementById('agents').innerHTML = nested('agents', data.agent_activity || {});
            document.getElementById('memory').innerHTML = rows(data.memory || {});
            document.getElementById('research').innerHTML = rows(data.research || {});
            document.getElementById('gpu').innerHTML = rows(data.gpu || {});
            document.getElementById('improvement').innerHTML = `<div class="trace">${JSON.stringify(data.self_improvement || {}, null, 2)}</div>`;
          } catch (e) {
            console.error(e);
          }
        }
        refresh(); setInterval(refresh, 2000);
      </script>
    </body>
    </html>
    """)


@app.get("/dashboard/data")
async def dashboard_data():
    """Return structured diagnostics data for the dashboard."""
    hyper = _state.get("hyper")
    if not hyper:
        return {"system": {"hyper_enabled": False}, "performance": {}, "agent_activity": {}, "memory": {}, "research": {}, "gpu": {}, "self_improvement": {}}
    return get_hyper_dashboard_data(hyper)


# ------------------------------------------------------------------ #
# Memory
# ------------------------------------------------------------------ #

@app.get("/memory/status")
async def memory_status():
    """Get memory system status."""
    if not _state["memory"]:
        raise HTTPException(status_code=503, detail="Memory not available")
    return _state["memory"].get_status()


@app.get("/memory/facts")
async def get_facts():
    """Get all stored user facts."""
    if not _state["memory"]:
        raise HTTPException(status_code=503, detail="Memory not available")
    return _state["memory"].long_term.get_all_facts()


@app.post("/memory/save")
async def save_memory(request: MemorySaveRequest):
    """Save a memory explicitly."""
    if not _state["memory"]:
        raise HTTPException(status_code=503, detail="Memory not available")
    _state["memory"].save_explicit_memory(request.content, tags=request.tags)
    return {"status": "saved", "content": request.content}


@app.get("/memory/recent")
async def get_recent_memories(limit: int = 10):
    """Get recent memories."""
    if not _state["memory"]:
        raise HTTPException(status_code=503, detail="Memory not available")
    return _state["memory"].long_term.get_recent_memories(limit=limit)


# ------------------------------------------------------------------ #
# Notes & Tasks
# ------------------------------------------------------------------ #

@app.get("/notes")
async def get_notes(limit: int = 20):
    """Get recent notes."""
    if not _state["notes"]:
        raise HTTPException(status_code=503, detail="Notes not available")
    return _state["notes"].get_recent_notes(limit=limit)


@app.post("/notes")
async def add_note(request: NoteRequest):
    """Add a new note."""
    if not _state["notes"]:
        raise HTTPException(status_code=503, detail="Notes not available")
    note_id = _state["notes"].add_note(request.content, request.category)
    return {"status": "saved", "id": note_id, "content": request.content}


@app.get("/tasks")
async def get_tasks():
    """Get pending tasks."""
    if not _state["notes"]:
        raise HTTPException(status_code=503, detail="Tasks not available")
    return _state["notes"].get_pending_tasks()


@app.post("/tasks")
async def add_task(request: TaskRequest):
    """Add a new task."""
    if not _state["notes"]:
        raise HTTPException(status_code=503, detail="Tasks not available")
    task_id = _state["notes"].add_task(
        request.title,
        priority=request.priority,
        due_date=request.due_date,
    )
    return {"status": "added", "id": task_id, "title": request.title}


@app.put("/tasks/{task_id}/complete")
async def complete_task(task_id: int):
    """Mark a task as complete."""
    if not _state["notes"]:
        raise HTTPException(status_code=503, detail="Tasks not available")
    _state["notes"].complete_task(task_id)
    return {"status": "completed", "id": task_id}


# ------------------------------------------------------------------ #
# Weather
# ------------------------------------------------------------------ #

@app.get("/weather")
async def get_weather():
    """Get current weather."""
    if not _state["weather"]:
        raise HTTPException(status_code=503, detail="Weather not available")
    weather = _state["weather"].get_weather()
    if not weather:
        raise HTTPException(status_code=503, detail="Could not fetch weather")
    return weather


# ------------------------------------------------------------------ #
# Calendar & Email (Google)
# ------------------------------------------------------------------ #

@app.get("/calendar")
async def get_calendar(days: int = 7):
    """Get upcoming calendar events."""
    if not _state["google"] or not _state["google"].is_available:
        return {"events": [], "message": "Google Calendar not configured"}
    events = _state["google"].get_upcoming_events(days=days)
    return {"events": events, "count": len(events)}


@app.get("/emails")
async def get_emails(max_results: int = 10, unread_only: bool = True):
    """Get recent emails."""
    if not _state["google"] or not _state["google"].is_available:
        return {"emails": [], "message": "Gmail not configured"}
    emails = _state["google"].get_recent_emails(
        max_results=max_results,
        unread_only=unread_only,
    )
    return {"emails": emails, "count": len(emails)}


# ------------------------------------------------------------------ #
# Reminders
# ------------------------------------------------------------------ #

@app.post("/reminders")
async def add_reminder(request: ReminderRequest):
    """Schedule a reminder."""
    if not _state["scheduler"]:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    job_id = _state["scheduler"].add_reminder(
        message=request.message,
        at_time=request.at_time,
        in_minutes=request.in_minutes,
        in_hours=request.in_hours,
    )

    if not job_id:
        raise HTTPException(status_code=400, detail="Could not schedule reminder")

    return {"status": "scheduled", "job_id": job_id, "message": request.message}


@app.get("/reminders")
async def get_reminders():
    """Get all scheduled reminders."""
    if not _state["scheduler"]:
        raise HTTPException(status_code=503, detail="Scheduler not available")
    return {"reminders": _state["scheduler"].get_jobs()}


# ------------------------------------------------------------------ #
# Automation
# ------------------------------------------------------------------ #

@app.post("/automation/run")
async def run_automation(request: AutomationRequest):
    """Run an automation command."""
    if not _state["tool_dispatcher"]:
        raise HTTPException(status_code=503, detail="Automation not available")

    dispatcher = _state["tool_dispatcher"]
    if _state["llm"]:
        dispatcher.attach_llm(_state["llm"])

    response, was_handled = dispatcher.dispatch(request.command)

    return {
        "response": response,
        "was_handled": was_handled,
        "command": request.command,
    }
