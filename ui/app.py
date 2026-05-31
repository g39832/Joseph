"""
ui/app.py
----------
JOSEPH Desktop UI - Polished production-quality dark interface using customtkinter.

Layout:
  +--------------------------------------------------+
  |  JOSEPH                    [status]  [HH:MM:SS]  |  <- Header (52px)
  +---------------------------+----------------------+
  |                           |  M E M O R Y        |
  |   Chat Area               |  ---------------    |
  |   (scrollable)            |  S E S S I O N      |
  |                           |  ---------------    |
  |                           |  Q U I C K  A C T   |
  +---------------------------+----------------------+
  |  [mic]  [ Type a message...          ] [ Send ]  |  <- Input (80px)
  |  Enter to send . Shift+Enter newline . / cmds    |
  +--------------------------------------------------+
"""

import logging
import json
import os
import queue
import asyncio
import re
import threading
import time
import webbrowser
from datetime import datetime
from typing import Optional

from ui.phase5 import Phase5Integration
from ui.phase6 import Phase6Integration
from ui.phase7 import Phase7Integration
from ui.phase8 import Phase8Integration
from ui.phase9 import Phase9Integration
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk

import customtkinter as ctk
import tkinter as tk

from configs.settings import settings
from hyper.bootstrap import (
    enhance_response,
    finalize_hyper_turn,
    get_context_enhancement,
    prepare_hyper_turn,
    shutdown_hyper,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Color Palette
# ------------------------------------------------------------------ #
THEMES = {
    "dark": {
        "bg": "#141414", "panel": "#1e1e1e", "card": "#252525",
        "card_hover": "#2f2f2f", "card_user": "#2c2c2c",
        "border": "#333333", "border_light": "#404040",
        "accent": "#4d9de0", "accent_hover": "#3d8dd0", "accent_dim": "#2a5a8a",
        "text": "#ececec", "text_dim": "#7a7a7a", "text_muted": "#555555",
        "text_joseph": "#4d9de0", "text_user": "#d0d0d0",
        "success": "#3dba7a", "error": "#d95f5f", "warning": "#d4924a",
        "input_bg": "#1a1a1a", "scrollbar": "#333333", "thinking": "#8b5cf6", "sash": "#2a2a2a",
    },
    "light": {
        "bg": "#f5f5f5", "panel": "#ffffff", "card": "#ebebeb",
        "card_hover": "#e0e0e0", "card_user": "#e3f2fd",
        "border": "#d0d0d0", "border_light": "#bfbfbf",
        "accent": "#1976d2", "accent_hover": "#1565c0", "accent_dim": "#64b5f6",
        "text": "#1a1a1a", "text_dim": "#6a6a6a", "text_muted": "#9a9a9a",
        "text_joseph": "#1976d2", "text_user": "#1a1a1a",
        "success": "#2e7d32", "error": "#c62828", "warning": "#e65100",
        "input_bg": "#ffffff", "scrollbar": "#cccccc", "thinking": "#7c4dff", "sash": "#cccccc",
    },
}

FONTS = {
    "title":     ("Segoe UI", 16, "bold"),
    "subtitle":  ("Segoe UI", 10),
    "body":      ("Segoe UI", 13),
    "body_sm":   ("Segoe UI", 11),
    "mono":      ("Consolas", 11),
    "name":      ("Segoe UI Semibold", 11, "bold"),
    "time":      ("Segoe UI", 9),
    "sidebar":   ("Segoe UI", 10),
    "sidebar_h": ("Segoe UI", 9, "bold"),
    "input":     ("Segoe UI", 13),
    "btn":       ("Segoe UI Semibold", 12, "bold"),
}


class JosephApp(ctk.CTk):
    """
    Main application window for JOSEPH.

    Runs the UI on the main thread.
    LLM calls run on background threads to keep the UI responsive.
    Results are passed back via a thread-safe queue.
    """

    def __init__(
        self, llm, memory, personality,
        hyper_engine=None, router=None,
        activity_tracker=None, project_awareness=None,
        insight_engine=None, research_workspace=None,
        followup_engine=None, ambient_intel=None,
        workspace_manager=None, project_commander=None,
        roadmap_engine=None, weekly_review=None,
        briefing_v2=None, project_memory=None,
        research_pipeline=None, learning_companion=None,
        decision_history=None, continuity_engine=None,
        consolidation_engine=None,
        document_intelligence=None, vision_engine=None,
        paper_analyzer=None, screen_awareness=None,
        code_vision=None, diagram_analyzer=None,
        multimodal_memory=None,
        background_research=None,
        cognitive_router=None,
        memory_relevance=None,
        smart_cache=None,
    ):
        super().__init__()

        self.llm = llm
        self.memory = memory
        self.personality = personality
        self._hyper = hyper_engine
        self._phase6_router = router

        # Thread-safe queue for streaming chunks from background thread
        self._response_queue: queue.Queue = queue.Queue()
        self._is_responding = False
        self._current_response = ""

        # Voice controller (initialized after UI is built)
        self._voice: Optional[object] = None
        self._voice_enabled = False

        # Automation router (initialized lazily)
        self._router: Optional[object] = None
        self._tool_dispatcher: Optional[object] = None

        # Phase 4 agents
        self._memory_agent: Optional[object] = None
        self._task_agent: Optional[object] = None
        self._planner: Optional[object] = None

        # Phase 5 services
        self._weather = None
        self._notes = None
        self._scheduler = None
        self._briefing = None
        self._context_awareness = None

        # Phase 7 services
        self._vision = None
        self._file_manager = None
        self._advanced_personality = None
        self._autonomous_agent = None

        # Phase 7 (new): capability enhancement engines
        self._activity_tracker = activity_tracker
        self._project_awareness = project_awareness
        self._insight_engine = insight_engine
        self._research_workspace = research_workspace
        self._followup_engine = followup_engine
        self._ambient_intel = ambient_intel
        if self._ambient_intel and self._activity_tracker:
            self._ambient_intel.set_tracker(self._activity_tracker)
        self._project_context_cache = ""
        self._last_user_text = ""
        self._last_followups = []

        # Phase 8: Personal Operating System
        self._workspace_manager = workspace_manager
        self._project_commander = project_commander
        self._roadmap_engine = roadmap_engine
        self._weekly_review = weekly_review
        self._briefing_v2 = briefing_v2
        self._project_memory = project_memory
        self._research_pipeline = research_pipeline
        self._learning_companion = learning_companion
        self._decision_history = decision_history
        self._continuity_engine = continuity_engine
        self._consolidation_engine = consolidation_engine
        self._project_store = None  # set lazily by Phase 5

        # Phase 9: Vision, Document Intelligence, Computer Awareness
        self._document_intelligence = document_intelligence
        self._vision_engine = vision_engine
        self._paper_analyzer = paper_analyzer
        self._screen_awareness = screen_awareness
        self._code_vision = code_vision
        self._diagram_analyzer = diagram_analyzer
        self._multimodal_memory = multimodal_memory
        self._background_research = background_research

        # Phase X: Cognitive Architecture
        self._cognitive_router = cognitive_router
        self._memory_relevance = memory_relevance
        self._smart_cache = smart_cache

        # Phase 8 services
        self._google = None
        self._hotkey_daemon = None
        self._api_server_thread = None

        # Phase 9 services
        self._notifications = None
        self._system_tray = None
        self._proactive_engine = None
        self._multi_model_router = None
        self._plugin_system = None
        self._conversation_search = None
        self._hyper_turn_packet: dict = {}
        self._pending_attachments: list[dict] = []
        self._llm_busy = threading.Event()
        self._ui_settings = {
            "hyper_enabled": bool(hyper_engine),
            "research_sources": 3,
            "refresh_interval_ms": 15000,
            "density": "comfortable",
            "animations": True,
            "compact_panels": False,
        }
        self._command_center_widgets: dict[str, object] = {}
        self._command_center_refresh_job = None
        self._graph_zoom = 1.0
        self._graph_positions: dict[str, tuple[float, float]] = {}
        self._selected_memory_id: Optional[int] = None
        self._selected_graph_node: Optional[str] = None
        self._selected_improvement = None
        self._last_turn_summary = {}
        self._page_frames: dict[str, object] = {}
        self._nav_buttons: dict[str, object] = {}
        self._active_page = "Chat"
        self._layout_state = self._load_layout_state()
        self._nav_visible = self._layout_state.get("nav_visible", True)
        self._context_visible = self._layout_state.get("context_visible", True)
        self._nav_width = int(self._layout_state.get("nav_width", 232))
        self._context_width = int(self._layout_state.get("context_width", 320))
        self._theme_mode = self._normalize_theme_mode(self._layout_state.get("theme_mode", "dark"))
        self._layout_density = self._layout_state.get("density", "comfortable")
        self._font_scale = float(self._layout_state.get("font_scale", 1.0))
        mode_key = self._theme_mode if self._theme_mode in THEMES else "dark"
        self.colors = dict(THEMES[mode_key])
        self._graph_pan_offset_x = 0
        self._graph_pan_offset_y = 0
        self._graph_pan_start_pos = None
        self._graph_drag_start = None

        # Phase 10 services
        self._clipboard_monitor = None
        self._custom_commands = None
        self._personality_learning = None

        # Phase 11 services
        self._spotify = None
        self._focus_mode = None
        self._email_triage = None

        # Configure customtkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._ttk_style = ttk.Style()
        try:
            self._ttk_style.configure("Responsive.TPanedwindow", background=self.colors["bg"])
        except Exception:
            pass

        self._setup_window()
        self._build_ui()
        # Phase 5: Engineering Assistant, Tools Framework, Project Manager
        try:
            Phase5Integration.hook_into(self)
        except Exception as e:
            logger.warning(f"Phase 5 integration skipped: {e}")

        # Phase 6: Assistant Router + Explainability Panel
        try:
            Phase6Integration.hook_into(self)
        except Exception as e:
            logger.warning(f"Phase 6 integration skipped: {e}")

        # Phase 7: Activity Timeline, Insights, Research, Suggestions
        try:
            Phase7Integration.hook_into(self)
        except Exception as e:
            logger.warning(f"Phase 7 integration skipped: {e}")

        # Phase 8: Personal Operating System
        try:
            Phase8Integration.hook_into(self)
        except Exception as e:
            logger.warning(f"Phase 8 integration skipped: {e}")

        # Phase 9: Vision, Document Intelligence, Computer Awareness
        try:
            Phase9Integration.hook_into(self)
        except Exception as e:
            logger.warning(f"Phase 9 integration skipped: {e}")

        self._start_session()

        # Start polling the response queue
        self._poll_response_queue()

        # Initialize voice system after UI is ready
        self.after(1000, self._init_voice)

    # ------------------------------------------------------------------ #
    # Window Setup
    # ------------------------------------------------------------------ #

    def _setup_window(self):
        """Configure the main window."""
        self.title("JOSEPH - Personal AI Assistant")
        self.geometry("1360x820")
        self.minsize(980, 660)
        self.configure(fg_color=self.colors["bg"])

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1360) // 2
        y = (self.winfo_screenheight() - 820) // 2
        self.geometry(f"1360x820+{x}+{y}")

        # Handle close button
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Hotkeys
        self.bind("<F2>", lambda e: self._toggle_voice())
        self.bind("<Escape>", self._on_escape_key)

        # Grid layout: header row + main row + input row
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _layout_state_path(self) -> Path:
        """Return the persisted UI layout state path."""
        return settings.DATA_DIR / "ui_layout_state.json"

    def _load_layout_state(self) -> dict:
        """Load responsive layout state if it exists."""
        path = self._layout_state_path()
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug(f"Layout state load skipped: {e}")
        return {}

    def _save_layout_state(self) -> None:
        """Persist UI layout preferences."""
        try:
            data = {
                "nav_visible": self._nav_visible,
                "context_visible": self._context_visible,
                "nav_width": self._nav_width,
                "context_width": self._context_width,
                "theme_mode": self._theme_mode,
                "density": self._layout_density,
                "font_scale": self._font_scale,
                "active_page": self._active_page,
            }
            path = self._layout_state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Layout state save skipped: {e}")

    # ------------------------------------------------------------------ #
    # UI Construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        """Build all UI components."""
        self._build_header()
        self._build_main_area()
        self._build_input_bar()

    def _build_header(self):
        """Top header bar with title, status indicator, and live clock."""
        header = ctk.CTkFrame(
            self,
            height=52,
            fg_color=self.colors["panel"],
            corner_radius=0,
        )
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        # Thin accent line at bottom of header
        accent_line = ctk.CTkFrame(header, height=1, fg_color=self.colors["accent"])
        accent_line.place(relx=0, rely=1.0, anchor="sw", relwidth=1.0)

        # Left: Logo + name
        logo_frame = ctk.CTkFrame(header, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=0, sticky="w")

        ctk.CTkLabel(
            logo_frame,
            text="◈",
            font=("Segoe UI", 18),
            text_color=self.colors["accent"],
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            logo_frame,
            text="JOSEPH",
            font=FONTS["title"],
            text_color=self.colors["text"],
        ).pack(side="left")

        ctk.CTkLabel(
            logo_frame,
            text="Personal AI Assistant",
            font=FONTS["subtitle"],
            text_color=self.colors["text_dim"],
        ).pack(side="left", padx=(10, 0))

        self._layout_actions_frame = ctk.CTkFrame(header, fg_color="transparent")
        self._layout_actions_frame.grid(row=0, column=1, padx=8, pady=0, sticky="e")

        self._nav_toggle_button = ctk.CTkButton(
            self._layout_actions_frame,
            text="Hide Nav",
            width=76,
            height=26,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._toggle_navigation_panel,
        )
        self._nav_toggle_button.pack(side="left", padx=(0, 6))

        self._context_toggle_button = ctk.CTkButton(
            self._layout_actions_frame,
            text="Hide Ctx",
            width=76,
            height=26,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._toggle_context_panel,
        )
        self._context_toggle_button.pack(side="left", padx=(0, 6))

        self._reset_layout_button = ctk.CTkButton(
            self._layout_actions_frame,
            text="Reset",
            width=58,
            height=26,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._reset_panel_widths,
        )
        self._reset_layout_button.pack(side="left")

        # Right: Status indicator + clock
        self._status_frame = ctk.CTkFrame(header, fg_color="transparent")
        self._status_frame.grid(row=0, column=2, padx=20, pady=0, sticky="e")

        # Live clock
        self._clock_label = ctk.CTkLabel(
            self._status_frame,
            text=datetime.now().strftime("%H:%M"),
            font=("Segoe UI", 13, "bold"),
            text_color=self.colors["text_dim"],
        )
        self._clock_label.pack(side="right", padx=(16, 0))
        self._update_clock()

        # Status label
        self._status_label = ctk.CTkLabel(
            self._status_frame,
            text=f"Connected  {settings.OLLAMA_MODEL}",
            font=FONTS["body_sm"],
            text_color=self.colors["text_dim"],
        )
        self._status_label.pack(side="right", padx=(0, 6))

        # Pulsing status dot
        self._status_dot = ctk.CTkLabel(
            self._status_frame,
            text="●",
            font=("Segoe UI", 12),
            text_color=self.colors["success"],
        )
        self._status_dot.pack(side="right", padx=(0, 4))
        self._dot_bright = True
        self._pulse_dot()

    def _update_clock(self):
        """Update the clock label every second."""
        self._clock_label.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._update_clock)

    def _pulse_dot(self):
        """Animate the status dot between bright and dim when idle."""
        if not self._is_responding:
            color = self.colors["success"] if self._dot_bright else "#1e6640"
            self._status_dot.configure(text_color=color)
            self._dot_bright = not self._dot_bright
        self.after(1200, self._pulse_dot)

    def _build_main_area(self):
        """Main content area with responsive nav, workspace, and context panel."""
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self._main_pane = ttk.Panedwindow(
            main,
            orient="horizontal",
            style="Responsive.TPanedwindow",
        )
        self._main_pane.grid(row=0, column=0, sticky="nsew")
        self._main_pane.bind("<ButtonRelease-1>", lambda _e: self._capture_layout_state())

        self._nav_host = ctk.CTkFrame(main, fg_color=self.colors["panel"], corner_radius=0)
        self._workspace_host = ctk.CTkFrame(main, fg_color=self.colors["bg"], corner_radius=0)
        self._context_host = ctk.CTkFrame(main, fg_color=self.colors["panel"], corner_radius=0)

        self._main_pane.add(self._nav_host, weight=0)
        self._main_pane.add(self._workspace_host, weight=1)
        self._main_pane.add(self._context_host, weight=0)

        self._build_navigation_panel(self._nav_host)
        self._build_workspace_panel(self._workspace_host)
        self._build_context_panel(self._context_host)

        self._apply_layout_state()
        self._show_page(self._layout_state.get("active_page", "Chat"))
        self._schedule_command_center_refresh()

    def _build_navigation_panel(self, parent):
        """Build the collapsible left navigation panel."""
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self._nav_panel = ctk.CTkFrame(parent, fg_color="transparent")
        self._nav_panel.grid(row=0, column=0, sticky="nsew")
        self._nav_panel.grid_rowconfigure(1, weight=1)
        self._nav_panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self._nav_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Command Center",
            font=FONTS["title"],
            text_color=self.colors["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="Hide",
            width=56,
            height=26,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._toggle_navigation_panel,
        ).grid(row=0, column=1, sticky="e")

        self._nav_buttons_frame = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
            corner_radius=0,
        )
        self._nav_buttons_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 8))
        self._nav_buttons_frame.grid_columnconfigure(0, weight=1)

        self._nav_status_label = ctk.CTkLabel(
            self._nav_panel,
            text="Ready",
            font=FONTS["sidebar"],
            text_color=self.colors["text_dim"],
        )
        self._nav_status_label.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 12))

        self._nav_buttons.clear()
        for page in [
            "Chat",
            "Dashboard",
            "Knowledge Graph",
            "Memory",
            "Agents",
            "Diagnostics",
            "Improvements",
            "Settings",
        ]:
            button = ctk.CTkButton(
                self._nav_buttons_frame,
                text=page,
                height=34,
                font=FONTS["sidebar"],
                fg_color=self.colors["card"],
                hover_color=self.colors["border_light"],
                text_color=self.colors["text"],
                corner_radius=8,
                anchor="w",
                command=lambda p=page: self._show_page(p),
            )
            button.pack(fill="x", pady=4)
            self._nav_buttons[page] = button

    def _build_workspace_panel(self, parent):
        """Build the central content stack."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self._workspace_stack = ctk.CTkFrame(parent, fg_color=self.colors["bg"], corner_radius=0)
        self._workspace_stack.grid(row=0, column=0, sticky="nsew")
        self._workspace_stack.grid_rowconfigure(0, weight=1)
        self._workspace_stack.grid_columnconfigure(0, weight=1)

        for page in [
            "Chat",
            "Dashboard",
            "Knowledge Graph",
            "Memory",
            "Agents",
            "Diagnostics",
            "Improvements",
            "Settings",
        ]:
            frame = ctk.CTkFrame(self._workspace_stack, fg_color=self.colors["bg"], corner_radius=0)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_rowconfigure(0, weight=1)
            frame.grid_columnconfigure(0, weight=1)
            self._page_frames[page] = frame

        self._build_chat_area(self._page_frames["Chat"])
        self._build_dashboard_tab(self._page_frames["Dashboard"])
        self._build_graph_tab(self._page_frames["Knowledge Graph"])
        self._build_memory_tab(self._page_frames["Memory"])
        self._build_agents_tab(self._page_frames["Agents"])
        self._build_diagnostics_tab(self._page_frames["Diagnostics"])
        self._build_improvements_tab(self._page_frames["Improvements"])
        self._build_settings_tab(self._page_frames["Settings"])

    def _build_context_panel(self, parent):
        """Build the optional right context panel."""
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self._context_panel = ctk.CTkFrame(parent, fg_color="transparent")
        self._context_panel.grid(row=0, column=0, sticky="nsew")
        self._context_panel.grid_rowconfigure(1, weight=1)
        self._context_panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self._context_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Context",
            font=FONTS["title"],
            text_color=self.colors["text"],
        ).grid(row=0, column=0, sticky="w")

        btn_row = ctk.CTkFrame(header, fg_color="transparent")
        btn_row.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            btn_row,
            text="Hide",
            width=56,
            height=26,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._toggle_context_panel,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_row,
            text="Wide",
            width=56,
            height=26,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._reset_panel_widths,
        ).pack(side="left")

        self._context_stack = ctk.CTkScrollableFrame(
            self._context_panel,
            fg_color="transparent",
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
            corner_radius=0,
        )
        self._context_stack.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 8))
        self._context_stack.grid_columnconfigure(0, weight=1)

        self._context_cards = {}
        context_specs = [
            ("Current Turn", "turn"),
            ("Agent Activity", "agents"),
            ("Research", "research"),
            ("Memory", "memory"),
            ("Diagnostics", "diagnostics"),
        ]
        for title, key in context_specs:
            card = ctk.CTkFrame(
                self._context_stack,
                fg_color=self.colors["panel"],
                corner_radius=12,
                border_width=1,
                border_color=self.colors["border"],
            )
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(card, text=title, font=FONTS["name"], text_color=self.colors["accent"]).pack(anchor="w", padx=12, pady=(10, 6))
            box = ctk.CTkTextbox(
                card,
                height=120 if key != "turn" else 150,
                font=FONTS["body_sm"],
                fg_color=self.colors["input_bg"],
                text_color=self.colors["text"],
                border_color=self.colors["border"],
                border_width=1,
                corner_radius=8,
                wrap="word",
            )
            box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            box.insert("end", "Loading...")
            box.configure(state="disabled")
            self._context_cards[key] = box

    def _apply_layout_state(self):
        """Apply saved panel visibility and widths."""
        try:
            self._nav_visible = bool(self._layout_state.get("nav_visible", self._nav_visible))
            self._context_visible = bool(self._layout_state.get("context_visible", self._context_visible))
            self._nav_width = int(self._layout_state.get("nav_width", self._nav_width))
            self._context_width = int(self._layout_state.get("context_width", self._context_width))
            self._theme_mode = self._layout_state.get("theme_mode", self._theme_mode)
            self._theme_mode = self._normalize_theme_mode(self._theme_mode)
            ctk.set_appearance_mode(self._theme_mode)
            self._apply_theme()
        except Exception:
            pass

        if not hasattr(self, "_main_pane"):
            return

        try:
            if self._nav_visible:
                if str(self._nav_host) not in self._main_pane.panes():
                    self._main_pane.insert(0, self._nav_host, weight=0)
            else:
                if str(self._nav_host) in self._main_pane.panes():
                    self._main_pane.forget(self._nav_host)

            if self._context_visible:
                if str(self._context_host) not in self._main_pane.panes():
                    self._main_pane.insert(len(self._main_pane.panes()), self._context_host, weight=0)
            else:
                if str(self._context_host) in self._main_pane.panes():
                    self._main_pane.forget(self._context_host)
        except Exception:
            pass
        self._sync_panel_controls()
        self.after_idle(self._restore_pane_sizes)

    def _toggle_navigation_panel(self):
        """Collapse or restore the left navigation panel."""
        self._nav_visible = not self._nav_visible
        if self._nav_visible:
            try:
                if str(self._nav_host) not in self._main_pane.panes():
                    self._main_pane.insert(0, self._nav_host, weight=0)
            except Exception:
                pass
        else:
            try:
                self._main_pane.forget(self._nav_host)
            except Exception:
                pass
        self._sync_panel_controls()
        self.after_idle(self._restore_pane_sizes)
        self._save_layout_state()

    def _toggle_context_panel(self):
        """Collapse or restore the right context panel."""
        self._context_visible = not self._context_visible
        if self._context_visible:
            try:
                if str(self._context_host) not in self._main_pane.panes():
                    self._main_pane.insert(len(self._main_pane.panes()), self._context_host, weight=0)
            except Exception:
                pass
        else:
            try:
                self._main_pane.forget(self._context_host)
            except Exception:
                pass
        self._sync_panel_controls()
        self.after_idle(self._restore_pane_sizes)
        self._save_layout_state()

    def _reset_panel_widths(self):
        """Reset panels to a balanced default width."""
        self._nav_width = 232
        self._context_width = 320
        self._save_layout_state()
        self._apply_layout_state()

    def _capture_layout_state(self):
        """Persist the current pane sizes after a manual resize."""
        if not hasattr(self, "_main_pane"):
            return
        try:
            if self._nav_visible and self._nav_host.winfo_ismapped():
                self._nav_width = max(180, int(self._nav_host.winfo_width()))
            if self._context_visible and self._context_host.winfo_ismapped():
                self._context_width = max(260, int(self._context_host.winfo_width()))
            self._save_layout_state()
        except Exception:
            pass

    def _normalize_theme_mode(self, mode: str) -> str:
        """Map saved appearance modes into CustomTkinter modes."""
        value = str(mode or "dark").strip().lower()
        if value in {"auto", "system"}:
            return "system"
        if value in {"light", "dark"}:
            return value
        return "dark"


    def _apply_theme(self):
        """Apply current theme to all runtime colors."""
        self.colors.update(THEMES[self._theme_mode])
        self.configure(fg_color=self.colors["bg"])
        self._apply_theme_to_widgets()

    def _apply_theme_to_widgets(self):
        """Propagate theme to existing widgets."""
        try:
            for f in self._page_frames.values():
                try:
                    f.configure(fg_color=self.colors["bg"])
                except Exception:
                    pass
            if self._chat_scroll:
                self._chat_scroll.configure(fg_color=self.colors["bg"])
            for d in [self._context_cards, self._dashboard_boxes, self._diagnostics_boxes]:
                for box in d.values():
                    try:
                        box.configure(fg_color=self.colors["input_bg"], text_color=self.colors["text"], border_color=self.colors["border"])
                    except Exception:
                        pass
            if hasattr(self, "_research_progress_frame"):
                self._research_progress_frame.configure(fg_color=self.colors["panel"])
                self._research_progress_bar.configure(fg_color=self.colors["border"])
            self._refresh_context_panel()
            self._update_sidebar()
        except Exception:
            pass

    def _sync_panel_controls(self):
        """Keep header controls aligned with panel visibility."""
        try:
            if hasattr(self, "_nav_toggle_button"):
                self._nav_toggle_button.configure(
                    text="Show Nav" if not self._nav_visible else "Hide Nav",
                )
            if hasattr(self, "_context_toggle_button"):
                self._context_toggle_button.configure(
                    text="Show Ctx" if not self._context_visible else "Hide Ctx",
                )
        except Exception:
            pass

    def _restore_pane_sizes(self):
        """Apply saved sash positions after the layout changes."""
        if not hasattr(self, "_main_pane"):
            return
        try:
            self.update_idletasks()
            panes = list(self._main_pane.panes())
            if len(panes) == 3 and self._nav_visible and self._context_visible:
                total = max(self._main_pane.winfo_width(), 1)
                nav = max(180, min(self._nav_width, max(180, total - 520 - 260)))
                ctx = max(260, min(self._context_width, max(260, total - nav - 320)))
                self._main_pane.sashpos(0, nav)
                self._main_pane.sashpos(1, max(nav + 320, total - ctx))
            elif len(panes) == 2 and self._nav_visible and not self._context_visible:
                self._main_pane.sashpos(0, max(180, self._nav_width))
            elif len(panes) == 2 and not self._nav_visible and self._context_visible:
                total = max(self._main_pane.winfo_width(), 1)
                self._main_pane.sashpos(0, max(320, total - max(260, self._context_width)))
        except Exception:
            pass

    def _show_page(self, page: str):
        """Raise the selected workspace page."""
        if page not in self._page_frames:
            return
        self._active_page = page
        frame = self._page_frames[page]
        frame.tkraise()
        for name, button in self._nav_buttons.items():
            try:
                button.configure(
                    fg_color=self.colors["accent"] if name == page else self.colors["card"],
                    text_color="#ffffff" if name == page else self.colors["text"],
                )
            except Exception:
                pass
        if hasattr(self, "_nav_status_label"):
            self._nav_status_label.configure(text=f"Viewing {page}")
        self._refresh_context_panel()
        self._save_layout_state()

    def _refresh_context_panel(self):
        """Refresh the right-side context panel."""
        if not hasattr(self, "_context_cards"):
            return

        packet = self._hyper_turn_packet or {}
        trace = packet.get("trace") or {}
        research_bundle = packet.get("research_bundle") or {}
        sources = research_bundle.get("sources") or []
        memory_bundle = packet.get("memory_bundle") or {}
        perf = {}
        diagnostics = {}
        hyper = self._active_hyper_engine()
        if hyper and getattr(hyper, "_system_monitor", None):
            try:
                perf = hyper._system_monitor.get_metrics_snapshot()
                diagnostics = hyper._system_monitor.get_health_summary()
            except Exception:
                pass

        turn_lines = [
            f"Page: {self._active_page}",
            f"Hyper: {'on' if packet.get('enabled') else 'off'}",
            f"Research: {'yes' if packet.get('research') else 'no'}",
            f"Planning: {'yes' if packet.get('planning') else 'no'}",
            f"Reasoning: {'yes' if packet.get('reasoning') else 'no'}",
            f"Memory hits: {len(memory_bundle.get('semantic_results', [])) + len(memory_bundle.get('keyword_results', [])) if isinstance(memory_bundle, dict) else 0}",
        ]
        if packet.get("system_context"):
            turn_lines.extend(["", packet["system_context"][:1200]])
        self._set_textbox_content(self._context_cards.get("turn"), "\n".join(turn_lines))

        agent_lines = []
        if trace:
            active = [name for name, enabled in trace.items() if enabled]
            agent_lines.append(f"Active agents: {', '.join(active) if active else 'Idle'}")
        if packet.get("coordinator"):
            agent_lines.append(f"Coordinator duration: {packet['coordinator'].get('duration_ms', 0)} ms")
        agent_lines.append(f"Latest response time: {perf.get('response_time_ms', 0)} ms")
        self._set_textbox_content(self._context_cards.get("agents"), "\n".join(agent_lines))

        research_lines = [
            f"Sources: {len(sources)}",
            f"Confidence: {int((research_bundle.get('confidence', 0) or 0) * 100)}%",
        ]
        for source in sources[:3]:
            research_lines.append(f"- {source.get('title') or source.get('url', 'source')}")
        self._set_textbox_content(self._context_cards.get("research"), "\n".join(research_lines))

        mem_status = self.memory.get_status()
        memory_lines = [
            f"Short-term: {mem_status.get('short_term_messages', 0)}/{mem_status.get('short_term_limit', 0)}",
            f"Long-term memories: {mem_status.get('long_term_memories', 0)}",
            f"Facts: {mem_status.get('long_term_facts', 0)}",
            f"Vector store: {mem_status.get('vector_memories', 0)}",
        ]
        self._set_textbox_content(self._context_cards.get("memory"), "\n".join(memory_lines))

        diagnostic_lines = [
            f"CPU: {perf.get('cpu_usage', 0)}%",
            f"RAM: {perf.get('memory_usage', 0)}%",
            f"GPU: {perf.get('gpu_usage', 0)}%",
            f"Latency: {perf.get('api_latency_ms', 0)} ms",
            f"Warnings: {', '.join(diagnostics.get('warnings') or []) or 'None'}",
        ]
        self._set_textbox_content(self._context_cards.get("diagnostics"), "\n".join(diagnostic_lines))

    def _build_chat_area(self, parent):
        """Scrollable chat message area with search bar."""
        chat_container = ctk.CTkFrame(
            parent,
            fg_color=self.colors["bg"],
            corner_radius=0,
        )
        chat_container.grid(row=0, column=0, sticky="nsew")
        chat_container.grid_rowconfigure(2, weight=1)
        chat_container.grid_columnconfigure(0, weight=1)

        # ── Search bar ───────────────────────────────────────
        search_bar = ctk.CTkFrame(chat_container, fg_color=self.colors["panel"], height=38, corner_radius=0)
        search_bar.grid(row=0, column=0, sticky="ew")
        search_bar.grid_propagate(False)
        search_bar.grid_columnconfigure(0, weight=1)

        search_row = ctk.CTkFrame(search_bar, fg_color="transparent")
        search_row.pack(fill="x", padx=12, pady=5)
        search_row.grid_columnconfigure(0, weight=1)

        self._search_box = ctk.CTkEntry(
            search_row,
            placeholder_text="🔍  Search conversations...",
            font=FONTS["body_sm"],
            height=28,
            fg_color=self.colors["input_bg"],
            border_color=self.colors["border"],
            border_width=1,
            text_color=self.colors["text"],
            placeholder_text_color=self.colors["text_muted"],
            corner_radius=6,
        )
        self._search_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._search_box.bind("<Return>", lambda e: self._do_search())

        ctk.CTkButton(
            search_row,
            text="Search",
            font=FONTS["sidebar"],
            width=60,
            height=28,
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._do_search,
        ).grid(row=0, column=1)

        # Bottom border under search bar
        ctk.CTkFrame(chat_container, height=1, fg_color=self.colors["border"]).grid(
            row=0, column=0, sticky="ews", pady=(37, 0)
        )

        # ── Scrollable messages ──────────────────────────────
        panel = ctk.CTkFrame(
            chat_container,
            fg_color=self.colors["panel"],
            corner_radius=10,
            border_width=1,
            border_color=self.colors["border"],
        )
        panel.grid(row=1, column=0, sticky="ew", padx=14, pady=(10, 8))
        panel.grid_columnconfigure(0, weight=1)

        tool_row = ctk.CTkFrame(panel, fg_color="transparent")
        tool_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        tool_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tool_row,
            text="Command Center",
            font=FONTS["name"],
            text_color=self.colors["accent"],
        ).pack(side="left")

        self._turn_detail_toggle = ctk.CTkButton(
            tool_row,
            text="Collapse",
            width=84,
            height=24,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._toggle_turn_details,
        )
        self._turn_detail_toggle.pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            tool_row,
            text="Attach",
            width=60,
            height=24,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._attach_files,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            tool_row,
            text="Image",
            width=58,
            height=24,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._attach_image,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            tool_row,
            text="Export",
            width=60,
            height=24,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._export_conversation,
        ).pack(side="right", padx=(6, 0))

        details_row = ctk.CTkFrame(panel, fg_color="transparent")
        details_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        for idx in range(4):
            details_row.grid_columnconfigure(idx, weight=1)

        self._turn_agents_label = self._create_stat_card(details_row, 0, "Agents", "Idle")
        self._turn_sources_label = self._create_stat_card(details_row, 1, "Sources", "0")
        self._turn_memories_label = self._create_stat_card(details_row, 2, "Memories", "0")
        self._turn_reasoning_label = self._create_stat_card(details_row, 3, "Reasoning", "Waiting")

        self._turn_detail_box = ctk.CTkTextbox(
            panel,
            height=82,
            font=FONTS["body_sm"],
            fg_color=self.colors["input_bg"],
            text_color=self.colors["text"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=8,
            wrap="word",
        )
        self._turn_detail_box.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._turn_detail_box.insert("end", "Turn details will appear here after each response.")
        self._turn_detail_box.configure(state="disabled")

        self._chat_scroll = ctk.CTkScrollableFrame(
            chat_container,
            fg_color=self.colors["bg"],
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
            corner_radius=0,
        )
        self._chat_scroll.grid(row=2, column=0, sticky="nsew")
        self._chat_scroll.grid_columnconfigure(0, weight=1)

        # ── Research progress bar (hidden by default) ──────────
        self._research_progress_frame = ctk.CTkFrame(
            chat_container,
            fg_color=self.colors["panel"],
            height=32,
            corner_radius=0,
        )
        self._research_progress_frame.grid(row=3, column=0, sticky="ew")
        self._research_progress_frame.grid_columnconfigure(0, weight=1)
        self._research_progress_frame.grid_propagate(False)

        self._research_progress_label = ctk.CTkLabel(
            self._research_progress_frame,
            text="",
            font=("Segoe UI", 10),
            text_color=self.colors["accent"],
            anchor="w",
        )
        self._research_progress_label.grid(row=0, column=0, sticky="w", padx=(14, 4), pady=0)

        self._research_progress_bar = ctk.CTkProgressBar(
            self._research_progress_frame,
            width=120,
            height=10,
            fg_color=self.colors["border"],
            progress_color=self.colors["accent"],
            corner_radius=4,
            mode="determinate",
        )
        self._research_progress_bar.grid(row=0, column=1, sticky="e", padx=(4, 14), pady=0)
        self._research_progress_bar.set(0)

        self._research_progress_frame.grid_remove()

        self._message_row = 0

    def _build_sidebar(self, parent):
        """Right sidebar — clean, minimal, functional."""
        sidebar = ctk.CTkFrame(
            parent,
            fg_color=self.colors["panel"],
            corner_radius=0,
            width=260,
        )
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(0, weight=1)

        # Left border
        ctk.CTkFrame(sidebar, width=1, fg_color=self.colors["border"]).place(
            x=0, y=0, relheight=1
        )

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
            corner_radius=0,
        )
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        c = ctk.CTkFrame(scroll, fg_color="transparent")
        c.pack(fill="both", expand=True, padx=14, pady=10)

        # ── Status ──────────────────────────────────────────
        self._add_sidebar_section(c, "STATUS")
        self._mem_conversation = self._add_sidebar_stat(c, "Messages", "0 / 20")
        self._mem_memories     = self._add_sidebar_stat(c, "Memories", "0")
        self._mem_facts        = self._add_sidebar_stat(c, "Facts", "0")
        self._mem_semantic     = self._add_sidebar_stat(c, "Search", "Active")
        self._sess_id          = self._add_sidebar_stat(c, "Session", "—")
        self._sess_model       = self._add_sidebar_stat(c, "Model", settings.OLLAMA_MODEL.split(":")[0])
        self._sess_started     = self._add_sidebar_stat(c, "Started", datetime.now().strftime("%H:%M"))

        self._add_divider(c)

        # ── Services ─────────────────────────────────────────
        self._add_sidebar_section(c, "SERVICES")
        self._svc_weather   = self._add_sidebar_stat(c, "Weather", "—")
        self._svc_tasks     = self._add_sidebar_stat(c, "Tasks", "—")
        self._svc_notes     = self._add_sidebar_stat(c, "Notes", "—")
        self._svc_scheduler = self._add_sidebar_stat(c, "Reminders", "—")

        self._add_divider(c)

        # ── Actions ──────────────────────────────────────────
        self._add_sidebar_section(c, "ACTIONS")

        btn = dict(
            font=FONTS["sidebar"],
            height=28,
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            anchor="w",
        )

        actions = [
            ("⌫  Clear Chat",     self._cmd_clear),
            ("◎  Facts",          self._cmd_show_facts),
            ("◈  Memory",         self._cmd_memory_status),
            ("⏰  Reminders",      self._cmd_reminders),
            ("✓  Tasks",          self._cmd_tasks),
            ("📝  Notes",          self._cmd_notes),
        ]
        for label, cmd in actions:
            ctk.CTkButton(c, text=label, command=cmd, **btn).pack(fill="x", pady=1)

        self._add_divider(c)

        # ── Version ──────────────────────────────────────────
        ctk.CTkLabel(
            c,
            text="JOSEPH v1.0",
            font=("Segoe UI", 9),
            text_color=self.colors["text_muted"],
        ).pack(anchor="center", pady=(2, 6))

    def _build_input_bar(self):
        """Bottom input bar with text field, voice button, and send button."""
        input_bar = ctk.CTkFrame(
            self,
            height=80,
            fg_color=self.colors["panel"],
            corner_radius=0,
        )
        input_bar.grid(row=2, column=0, sticky="ew")
        input_bar.grid_columnconfigure(0, weight=1)
        input_bar.grid_propagate(False)

        # Top border line (slightly lighter for subtle gradient feel)
        border_top = ctk.CTkFrame(input_bar, height=2, fg_color=self.colors["border_light"])
        border_top.pack(fill="x", side="top")

        # Input row
        row = ctk.CTkFrame(input_bar, fg_color="transparent")
        row.pack(fill="x", expand=False, padx=16, pady=(8, 2))
        row.grid_columnconfigure(1, weight=1)

        # Voice button (circular push-to-talk)
        self._voice_btn = ctk.CTkButton(
            row,
            text="🎤",
            font=("Segoe UI", 17),
            width=42,
            height=42,
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text_dim"],
            corner_radius=21,
            command=self._toggle_voice,
        )
        self._voice_btn.grid(row=0, column=0, padx=(0, 10), sticky="w")

        # Text input
        self._input_box = ctk.CTkEntry(
            row,
            placeholder_text=f"Message {settings.JOSEPH_NAME}...",
            font=FONTS["input"],
            height=46,
            fg_color=self.colors["input_bg"],
            border_color=self.colors["border"],
            border_width=1,
            text_color=self.colors["text"],
            placeholder_text_color=self.colors["text_muted"],
            corner_radius=12,
        )
        self._input_box.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self._input_box.bind("<Return>", self._on_enter_key)
        self._input_box.bind("<Shift-Return>", lambda e: None)
        self._input_box.focus()

        # Send button
        self._send_btn = ctk.CTkButton(
            row,
            text="Send  ▶",
            font=FONTS["btn"],
            width=110,
            height=46,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color="#ffffff",
            corner_radius=12,
            command=self._send_message,
        )
        self._send_btn.grid(row=0, column=2)

        # Hint text + voice state label row
        hint_row = ctk.CTkFrame(input_bar, fg_color="transparent")
        hint_row.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkLabel(
            hint_row,
            text="Enter to send  ·  F2 for voice  ·  / for commands",
            font=("Segoe UI", 9),
            text_color=self.colors["text_muted"],
        ).pack(side="left")

        # Voice speed slider
        speed_frame = ctk.CTkFrame(hint_row, fg_color="transparent")
        speed_frame.pack(side="right")

        ctk.CTkLabel(
            speed_frame,
            text="Speed",
            font=("Segoe UI", 9),
            text_color=self.colors["text_muted"],
        ).pack(side="left", padx=(0, 4))

        self._speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=0.6,
            to=1.6,
            number_of_steps=10,
            width=80,
            height=14,
            button_color=self.colors["accent"],
            button_hover_color=self.colors["accent_hover"],
            progress_color=self.colors["accent_dim"],
            fg_color=self.colors["border"],
            command=self._on_speed_change,
        )
        self._speed_slider.set(1.0)
        self._speed_slider.pack(side="left")

        self._voice_state_label = ctk.CTkLabel(
            hint_row,
            text="",
            font=FONTS["body_sm"],
            text_color=self.colors["text_dim"],
        )
        # voice_state_label goes between hint and speed
        self._voice_state_label.pack(side="left", padx=(12, 0))

    def _active_hyper_engine(self):
        """Return the active hyper engine if UI runtime toggles allow it."""
        if not self._ui_settings.get("hyper_enabled", True):
            return None
        return self._hyper

    def _create_stat_card(self, parent, column: int, label: str, value: str):
        """Create a compact metric card for tab dashboards."""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors["card"],
            corner_radius=10,
            border_width=1,
            border_color=self.colors["border"],
        )
        card.grid(row=0, column=column, sticky="ew", padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=label,
            font=FONTS["sidebar_h"],
            text_color=self.colors["text_dim"],
        ).pack(anchor="w", padx=10, pady=(8, 0))
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=FONTS["body"],
            text_color=self.colors["text"],
        )
        value_label.pack(anchor="w", padx=10, pady=(2, 8))
        return value_label

    def _set_textbox_content(self, textbox, content: str) -> None:
        """Replace a textbox's content without exposing editing."""
        try:
            textbox.configure(state="normal")
            textbox.delete("1.0", "end")
            textbox.insert("end", content or "")
            textbox.configure(state="disabled")
        except Exception:
            pass

    def _toggle_turn_details(self):
        """Show or hide the chat intelligence panel."""
        if not hasattr(self, "_turn_detail_box"):
            return
        if self._turn_detail_box.winfo_ismapped():
            self._turn_detail_box.grid_remove()
            self._turn_detail_toggle.configure(text="Expand")
        else:
            self._turn_detail_box.grid()
            self._turn_detail_toggle.configure(text="Collapse")

    def _attach_files(self):
        """Attach one or more files to the next message."""
        paths = filedialog.askopenfilenames(title="Attach files to Joseph")
        if not paths:
            return
        for path in paths:
            self._pending_attachments.append({"type": "file", "path": path})
        self._add_system_message(
            f"Attached {len(paths)} file(s). They will be included with the next message.",
            self.colors["accent"],
        )

    def _attach_image(self):
        """Attach an image to the next message."""
        path = filedialog.askopenfilename(
            title="Attach image to Joseph",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self._pending_attachments.append({"type": "image", "path": path})
        self._add_system_message(
            "Image attached. It will be analyzed if vision is available.",
            self.colors["accent"],
        )

    def _export_conversation(self):
        """Export the current conversation to markdown and JSON."""
        try:
            settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            md_path = settings.EXPORTS_DIR / f"conversation_{stamp}.md"
            json_path = settings.EXPORTS_DIR / f"conversation_{stamp}.json"

            messages = self.memory.get_conversation_history()
            lines = [
                f"# {settings.JOSEPH_NAME} Conversation Export",
                f"- Exported: {datetime.now().isoformat()}",
                f"- Session: {getattr(self.memory, 'session_id', 'unknown')}",
                "",
            ]
            for msg in messages:
                role = msg.get("role", "unknown").title()
                content = msg.get("content", "")
                lines.append(f"## {role}")
                lines.append(content)
                lines.append("")

            md_path.write_text("\n".join(lines), encoding="utf-8")
            json_path.write_text(json.dumps(messages, indent=2, ensure_ascii=False), encoding="utf-8")
            self._add_system_message(
                f"Conversation exported to {md_path.name} and {json_path.name}",
                self.colors["success"],
            )
        except Exception as e:
            self._add_system_message(f"Export failed: {e}", self.colors["error"])

    def _format_attachment_context(self) -> str:
        """Build prompt context from pending attachments."""
        if not self._pending_attachments:
            return ""

        parts = ["Attached context:"]
        for item in self._pending_attachments:
            path = item.get("path", "")
            kind = item.get("type", "file")
            name = os.path.basename(path)
            if kind == "image":
                image_context = ""
                try:
                    if self._vision and hasattr(self._vision, "_analyze_with_vision_model"):
                        from PIL import Image
                        image = Image.open(path)
                        image_context = self._vision._analyze_with_vision_model(
                            image,
                            f"Analyze this uploaded image for {settings.JOSEPH_NAME}.",
                        )
                    elif self._vision and hasattr(self._vision, "ask_about_screen"):
                        image_context = f"Image uploaded: {name}"
                except Exception as e:
                    image_context = f"Image analysis failed for {name}: {e}"
                parts.append(f"- Image: {name}")
                if image_context:
                    parts.append(image_context[:1200])
            else:
                preview = ""
                try:
                    if path and os.path.isfile(path):
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            preview = f.read(3000)
                except Exception:
                    preview = ""
                parts.append(f"- File: {name}")
                if preview:
                    parts.append("```")
                    parts.append(preview[:3000])
                    parts.append("```")
        return "\n".join(parts)

    def _consume_pending_attachments(self) -> str:
        """Return attachment context and clear the queue."""
        context = self._format_attachment_context()
        self._pending_attachments.clear()
        return context

    def _update_turn_panel(self):
        """Refresh the summary cards and detail box for the latest turn."""
        packet = self._hyper_turn_packet or {}
        trace = packet.get("trace") or {}
        research_bundle = packet.get("research_bundle") or {}
        sources = research_bundle.get("sources") or []
        memory_bundle = packet.get("memory_bundle") or {}
        research_text = packet.get("research") or ""
        reasoning_text = packet.get("reasoning") or ""
        planning_text = packet.get("planning") or ""
        coordinator = packet.get("coordinator") or {}

        agents = [name for name, active in trace.items() if active]
        self._turn_agents_label.configure(text=", ".join(agents) if agents else "Idle")
        self._turn_sources_label.configure(text=str(len(sources)))
        memory_count = 0
        if isinstance(memory_bundle, dict):
            memory_count = len(memory_bundle.get("semantic_results", [])) + len(memory_bundle.get("keyword_results", []))
        self._turn_memories_label.configure(text=str(memory_count))
        summary_text = reasoning_text or planning_text or coordinator.get("final_response") or "Waiting"
        self._turn_reasoning_label.configure(text=summary_text[:80] or "Waiting")

        details = [
            f"Hyper layer: {'enabled' if packet.get('enabled') else 'disabled'}",
            f"Research: {'yes' if research_text else 'no'}",
            f"Planning: {'yes' if planning_text else 'no'}",
            f"Reasoning: {'yes' if reasoning_text else 'no'}",
            f"Memory context: {'yes' if memory_bundle else 'no'}",
        ]
        if sources:
            details.append("")
            details.append("Sources:")
            for src in sources[:5]:
                title = src.get("title") or src.get("url") or "source"
                details.append(f"- {title}")
        if packet.get("memory_context"):
            details.append("")
            details.append("Memory context snapshot:")
            details.append(packet.get("memory_context", "")[:1000])
        self._set_textbox_content(self._turn_detail_box, "\n".join(details).strip())

    def _schedule_command_center_refresh(self):
        """Refresh the command center at a conservative cadence."""
        interval = int(self._ui_settings.get("refresh_interval_ms", 15000))
        if self._command_center_refresh_job:
            try:
                self.after_cancel(self._command_center_refresh_job)
            except Exception:
                pass
        self._command_center_refresh_job = self.after(interval, self._refresh_command_center)

    def _refresh_command_center(self):
        """Refresh command-center tabs. Only heavy-refreshes the visible tab."""
        try:
            active = self._active_page

            # Always update lightweight panels
            self._update_turn_panel()
            self._refresh_context_panel()
            self._refresh_settings_tab()

            # Only heavy-refresh the visible tab
            if active == "Dashboard":
                self._refresh_dashboard_tab()
            elif active in ("Knowledge Graph", "Graph"):
                self._refresh_graph_tab()
            elif active == "Memory":
                self._refresh_memory_tab()
            elif active == "Agents":
                self._refresh_agents_tab()
            elif active == "Diagnostics":
                self._refresh_diagnostics_tab()
            elif active == "Improvements":
                self._refresh_improvements_tab()
        finally:
            self._schedule_command_center_refresh()

    def _build_dashboard_tab(self, parent):
        """Build the main dashboard tab."""
        tab = ctk.CTkScrollableFrame(
            parent,
            fg_color=self.colors["bg"],
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
        )
        tab.grid(row=0, column=0, sticky="nsew")
        tab.grid_columnconfigure(0, weight=1)
        self._dashboard_tab = tab
        self._dashboard_boxes = {}

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="AI Command Center",
            font=FONTS["title"],
            text_color=self.colors["text"],
        ).pack(side="left")
        ctk.CTkButton(
            header,
            text="Open Browser Dashboard",
            width=170,
            height=28,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=lambda: webbrowser.open(f"http://{settings.API_HOST}:{settings.API_PORT}/dashboard"),
        ).pack(side="right")

        cards = [
            ("AI Status", "system"),
            ("Intelligence Status", "agents"),
            ("GPU Information", "gpu"),
            ("Knowledge System", "knowledge"),
        ]
        for row, (title, key) in enumerate(cards, start=1):
            card = ctk.CTkFrame(
                tab,
                fg_color=self.colors["panel"],
                corner_radius=12,
                border_width=1,
                border_color=self.colors["border"],
            )
            card.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card,
                text=title,
                font=FONTS["name"],
                text_color=self.colors["accent"],
            ).pack(anchor="w", padx=12, pady=(10, 6))
            box = ctk.CTkTextbox(
                card,
                height=140,
                font=FONTS["body_sm"],
                fg_color=self.colors["input_bg"],
                text_color=self.colors["text"],
                border_color=self.colors["border"],
                border_width=1,
                corner_radius=8,
                wrap="word",
            )
            box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            box.insert("end", "Loading...")
            box.configure(state="disabled")
            self._dashboard_boxes[key] = box

        self._refresh_dashboard_tab()

    def _refresh_dashboard_tab(self):
        """Refresh dashboard cards from live hyper data."""
        if not hasattr(self, "_dashboard_boxes"):
            return
        data = {}
        hyper = self._active_hyper_engine()
        if hyper and hasattr(hyper, "get_dashboard_data"):
            try:
                data = hyper.get_dashboard_data()
            except Exception:
                data = {}

        system = data.get("system") or {}
        perf = data.get("performance") or {}
        agents = data.get("agent_activity") or {}
        memory = data.get("memory") or {}
        research = data.get("research") or {}
        gpu = data.get("gpu") or {}

        self._set_textbox_content(
            self._dashboard_boxes.get("system"),
            "\n".join(
                [
                    f"Hyper Layer: {'Enabled' if system.get('hyper_enabled') else 'Disabled'}",
                    f"Model: {system.get('model', settings.OLLAMA_MODEL)}",
                    f"Session: {system.get('session_id', getattr(self.memory, 'session_id', '—'))}",
                    f"Uptime: {round(float(system.get('uptime_seconds', 0) or 0), 1)} sec",
                    f"Running: {system.get('running', False)}",
                    f"Initialized: {system.get('initialized', False)}",
                ]
            ),
        )
        self._set_textbox_content(
            self._dashboard_boxes.get("agents"),
            "\n".join(
                [
                    f"Active agents: {', '.join(agents.get('active_agents') or []) or 'None'}",
                    f"Decision trace count: {len(agents.get('decisions') or [])}",
                    f"Execution durations: {agents.get('execution_times') or []}",
                    f"Task queue depth: {len(agents.get('task_queue') or [])}",
                ]
            ),
        )
        self._set_textbox_content(
            self._dashboard_boxes.get("gpu"),
            "\n".join(
                [
                    f"Backend: {(gpu or {}).get('backend', 'cpu')}",
                    f"GPU: {(gpu or {}).get('device_name', 'Unavailable')}",
                    f"VRAM: {(gpu or {}).get('vram_used_mb', 0)} / {(gpu or {}).get('vram_total_mb', 0)} MB",
                    f"Load: {(gpu or {}).get('gpu_usage', 0)}%",
                    f"Temperature: {(gpu or {}).get('temperature_c', 'N/A')}",
                ]
            ),
        )
        self._set_textbox_content(
            self._dashboard_boxes.get("knowledge"),
            "\n".join(
                [
                    f"Memory count: {(memory.get('stats') or {}).get('long_term_memories', memory.get('vector_cache_entries', 0))}",
                    f"Vector entries: {memory.get('vector_cache_entries', 0)}",
                    f"Graph nodes: {(memory.get('knowledge_graph') or {}).get('nodes', 0)}",
                    f"Graph edges: {(memory.get('knowledge_graph') or {}).get('edges', 0)}",
                    f"Recent research sources: {len((research.get('source_rankings') or []))}",
                ]
            ),
        )

    def _build_diagnostics_tab(self, parent):
        """Build the diagnostics tab."""
        tab = ctk.CTkScrollableFrame(
            parent,
            fg_color=self.colors["bg"],
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
        )
        tab.grid(row=0, column=0, sticky="nsew")
        tab.grid_columnconfigure(0, weight=1)
        self._diagnostics_tab = tab
        self._diagnostics_boxes = {}

        for row, (title, key) in enumerate([
            ("Performance Metrics", "performance"),
            ("AI Metrics", "ai"),
            ("Error Monitoring", "errors"),
            ("System Health", "health"),
        ], start=0):
            card = ctk.CTkFrame(
                tab,
                fg_color=self.colors["panel"],
                corner_radius=12,
                border_width=1,
                border_color=self.colors["border"],
            )
            card.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
            ctk.CTkLabel(
                card,
                text=title,
                font=FONTS["name"],
                text_color=self.colors["accent"],
            ).pack(anchor="w", padx=12, pady=(10, 6))
            box = ctk.CTkTextbox(
                card,
                height=138,
                font=FONTS["body_sm"],
                fg_color=self.colors["input_bg"],
                text_color=self.colors["text"],
                border_color=self.colors["border"],
                border_width=1,
                corner_radius=8,
                wrap="word",
            )
            box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            box.insert("end", "Loading...")
            box.configure(state="disabled")
            self._diagnostics_boxes[key] = box

        self._refresh_diagnostics_tab()

    def _refresh_diagnostics_tab(self):
        """Refresh diagnostics metrics from the hyper layer."""
        if not hasattr(self, "_diagnostics_boxes"):
            return
        hyper = self._active_hyper_engine()
        data = {}
        if hyper and hasattr(hyper, "get_dashboard_data"):
            try:
                data = hyper.get_dashboard_data()
            except Exception:
                data = {}

        perf = data.get("performance") or {}
        ai = {
            "tokens": perf.get("tokens_per_second", 0),
            "response_time_ms": perf.get("response_time_ms", 0),
            "api_latency_ms": perf.get("api_latency_ms", 0),
            "tool_failures": perf.get("tool_failures", 0),
        }
        errors = []
        health = {}
        if hyper and getattr(hyper, "_system_monitor", None):
            try:
                diag = hyper._system_monitor.get_diagnostics()
                health = diag.get("health") or {}
                errors = diag.get("tool_failures") or []
            except Exception:
                pass

        self._set_textbox_content(
            self._diagnostics_boxes.get("performance"),
            "\n".join(
                [
                    f"CPU Usage: {perf.get('cpu_usage', 0)}%",
                    f"RAM Usage: {perf.get('memory_usage', 0)}%",
                    f"GPU Usage: {perf.get('gpu_usage', 0)}%",
                    f"VRAM Usage: {perf.get('vram_usage', 0)}%",
                    f"Response Time: {perf.get('response_time_ms', 0)} ms",
                    f"Tokens / sec: {perf.get('tokens_per_second', 0)}",
                    f"API Latency: {perf.get('api_latency_ms', 0)} ms",
                ]
            ),
        )
        self._set_textbox_content(
            self._diagnostics_boxes.get("ai"),
            "\n".join(
                [
                    f"Tokens generated: {ai['tokens']}",
                    f"Average response time: {ai['response_time_ms']} ms",
                    f"Memory retrieval rate: {'enabled' if (data.get('memory') or {}).get('stats') else 'unknown'}",
                    f"Search frequency: {len((data.get('research') or {}).get('source_rankings') or [])}",
                    f"Agent participation: {len((data.get('agent_activity') or {}).get('active_agents') or [])}",
                ]
            ),
        )
        self._set_textbox_content(
            self._diagnostics_boxes.get("errors"),
            "\n".join(
                [
                    f"Warnings: {', '.join((health.get('warnings') or []) or ['None'])}",
                    f"Tool failures: {perf.get('tool_failures', 0)}",
                    f"Recent failures: {len(errors)}",
                ]
            ),
        )
        self._set_textbox_content(
            self._diagnostics_boxes.get("health"),
            json.dumps(data.get("system") or {}, indent=2, ensure_ascii=False),
        )

    def _build_graph_tab(self, parent):
        """Build the knowledge graph visualizer."""
        tab = ctk.CTkFrame(parent, fg_color=self.colors["bg"])
        tab.grid(row=0, column=0, sticky="nsew")
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=3)
        tab.grid_columnconfigure(1, weight=1)
        self._graph_tab = tab
        self._graph_hitboxes = {}

        controls = ctk.CTkFrame(tab, fg_color=self.colors["panel"], corner_radius=0)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew")
        controls.grid_columnconfigure(1, weight=1)

        self._graph_search_box = ctk.CTkEntry(
            controls,
            placeholder_text="Search graph nodes...",
            height=28,
            font=FONTS["body_sm"],
        )
        self._graph_search_box.grid(row=0, column=0, padx=12, pady=10, sticky="w")
        ctk.CTkButton(
            controls,
            text="Refresh",
            width=66,
            height=28,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._refresh_graph_tab,
        ).grid(row=0, column=2, padx=(0, 12), pady=10, sticky="e")

        self._graph_zoom_slider = ctk.CTkSlider(
            controls,
            from_=0.7,
            to=1.8,
            number_of_steps=11,
            width=160,
            command=lambda value: self._set_graph_zoom(value),
        )
        self._graph_zoom_slider.set(self._graph_zoom)
        self._graph_zoom_slider.grid(row=0, column=1, padx=12, pady=10, sticky="ew")

        canvas_card = ctk.CTkFrame(
            tab,
            fg_color=self.colors["panel"],
            corner_radius=12,
            border_width=1,
            border_color=self.colors["border"],
        )
        canvas_card.grid(row=1, column=0, sticky="nsew", padx=(6, 4), pady=8)
        canvas_card.grid_rowconfigure(0, weight=1)
        canvas_card.grid_columnconfigure(0, weight=1)
        self._graph_canvas = tk.Canvas(
            canvas_card,
            highlightthickness=0,
            bg=self.colors["bg"],
        )
        self._graph_canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._graph_canvas.bind("<Button-1>", self._on_graph_click)
        self._graph_canvas.bind("<MouseWheel>", self._on_graph_scroll)
        self._graph_canvas.bind("<ButtonPress-3>", self._on_graph_pan_start)
        self._graph_canvas.bind("<B3-Motion>", self._on_graph_pan_move)

        side = ctk.CTkFrame(
            tab,
            fg_color=self.colors["panel"],
            corner_radius=12,
            border_width=1,
            border_color=self.colors["border"],
        )
        side.grid(row=1, column=1, sticky="nsew", padx=(4, 6), pady=8)
        side.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(side, text="Node Inspection", font=FONTS["name"], text_color=self.colors["accent"]).pack(anchor="w", padx=12, pady=(10, 6))
        self._graph_detail_box = ctk.CTkTextbox(
            side,
            height=260,
            font=FONTS["body_sm"],
            fg_color=self.colors["input_bg"],
            text_color=self.colors["text"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=8,
            wrap="word",
        )
        self._graph_detail_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._set_textbox_content(self._graph_detail_box, "Select a node to inspect it here.")
        self._refresh_graph_tab()

    def _set_graph_zoom(self, value: float):
        self._graph_zoom = float(value)
        self._refresh_graph_tab()

    def _on_graph_scroll(self, event):
        """Mouse wheel zoom for knowledge graph."""
        delta = event.delta / 120 * 0.1
        self._graph_zoom = max(0.3, min(3.0, self._graph_zoom + delta))
        try:
            self._graph_zoom_slider.set(self._graph_zoom)
        except Exception:
            pass
        self._refresh_graph_tab()

    def _on_graph_pan_start(self, event):
        """Right-click pan start."""
        self._graph_pan_start_pos = (event.x, event.y)

    def _on_graph_pan_move(self, event):
        """Right-click pan move."""
        if self._graph_pan_start_pos:
            dx = event.x - self._graph_pan_start_pos[0]
            dy = event.y - self._graph_pan_start_pos[1]
            self._graph_pan_offset_x += dx
            self._graph_pan_offset_y += dy
            self._graph_pan_start_pos = (event.x, event.y)
            self._refresh_graph_tab()

    def _refresh_graph_tab(self):
        """Redraw the knowledge graph canvas with layout caching."""
        if not hasattr(self, "_graph_canvas"):
            return
        engine = self._active_hyper_engine()
        graph_engine = getattr(engine, "_knowledge_graph", None) if engine else None
        graph = getattr(graph_engine, "graph", None)
        self._graph_canvas.delete("all")
        self._graph_hitboxes = {}

        if not graph or graph.number_of_nodes() == 0:
            self._graph_canvas.create_text(
                300, 220,
                text="No knowledge graph data yet.",
                fill=self.colors["text_dim"],
                font=("Segoe UI", 14, "bold"),
            )
            self._set_textbox_content(self._graph_detail_box, "No graph data available.")
            return

        search = self._graph_search_box.get().strip().lower() if hasattr(self, "_graph_search_box") else ""
        nodes = []
        for node_id, data in graph.nodes(data=True):
            label = str(data.get("label", node_id))
            if search and search not in label.lower() and search not in node_id.lower():
                continue
            nodes.append((node_id, data))
        if not nodes:
            nodes = list(graph.nodes(data=True))[:25]
        sub_nodes = [node_id for node_id, _ in nodes]
        subgraph = graph.subgraph(sub_nodes).copy()

        # Cache layout: only recompute when node set or search changes
        node_hash = hash(frozenset(sub_nodes) | frozenset([search]))
        if (not hasattr(self, "_graph_node_hash") or
                self._graph_node_hash != node_hash):
            self._graph_node_hash = node_hash
            try:
                import networkx as nx
                self._graph_positions = nx.spring_layout(subgraph, seed=42)
            except Exception:
                self._graph_positions = {node_id: (idx / max(1, len(sub_nodes)), 0.5) for idx, node_id in enumerate(sub_nodes)}

        width = max(640, int(self._graph_canvas.winfo_width() or 640))
        height = max(420, int(self._graph_canvas.winfo_height() or 420))
        scale = 0.38 * self._graph_zoom
        center_x = width / 2 + getattr(self, '_graph_pan_offset_x', 0)
        center_y = height / 2 + getattr(self, '_graph_pan_offset_y', 0)
        positions = {}
        for node_id, (x, y) in self._graph_positions.items():
            positions[node_id] = (
                center_x + x * width * scale,
                center_y + y * height * scale,
            )

        for source, target, data in subgraph.edges(data=True):
            if source not in positions or target not in positions:
                continue
            x1, y1 = positions[source]
            x2, y2 = positions[target]
            self._graph_canvas.create_line(x1, y1, x2, y2, fill=self.colors["accent_dim"], width=2)
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            relation = str(data.get("relation", "related"))
            self._graph_canvas.create_text(mid_x, mid_y, text=relation, fill=self.colors["text_dim"], font=("Segoe UI", 8))

        for node_id, data in subgraph.nodes(data=True):
            x, y = positions.get(node_id, (center_x, center_y))
            label = str(data.get("label", node_id))
            importance = float(data.get("importance", 0.5))
            radius = 18 + importance * 8
            fill = self.colors["accent"] if node_id == self._selected_graph_node else self.colors["card"]
            item = self._graph_canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline=self.colors["border_light"], width=1.5)
            text_item = self._graph_canvas.create_text(x, y, text=label[:18], fill=self.colors["text"], font=("Segoe UI", 9, "bold"))
            self._graph_hitboxes[item] = node_id
            self._graph_hitboxes[text_item] = node_id

        details = self._graph_selected_node_details(graph)
        self._set_textbox_content(self._graph_detail_box, details)

    def _graph_selected_node_details(self, graph) -> str:
        """Build a readable details block for the selected graph node."""
        selected = self._selected_graph_node
        if not selected or selected not in graph:
            return "Click a node to inspect relationships."
        data = graph.nodes[selected]
        lines = [
            f"Node: {data.get('label', selected)}",
            f"Type: {data.get('node_type', 'topic')}",
            f"Importance: {data.get('importance', 0.5)}",
            f"Properties: {json.dumps(data.get('properties') or {}, ensure_ascii=False)}",
            "",
            "Related nodes:",
        ]
        for neighbor in list(graph.successors(selected))[:6]:
            nd = graph.nodes[neighbor]
            lines.append(f"- {nd.get('label', neighbor)}")
        return "\n".join(lines)

    def _on_graph_click(self, event):
        """Select the clicked graph node."""
        if not getattr(self, "_graph_hitboxes", None):
            return
        closest = self._graph_canvas.find_closest(event.x, event.y)
        if not closest:
            return
        item_id = closest[0]
        node_id = self._graph_hitboxes.get(item_id)
        if node_id:
            self._selected_graph_node = node_id
            self._refresh_graph_tab()

    def _build_memory_tab(self, parent):
        """Build the memory explorer tab."""
        tab = ctk.CTkFrame(parent, fg_color=self.colors["bg"])
        tab.grid(row=0, column=0, sticky="nsew")
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        self._memory_tab = tab
        self._memory_memory_rows = []

        top = ctk.CTkFrame(tab, fg_color=self.colors["panel"], corner_radius=0)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        self._memory_search_box = ctk.CTkEntry(top, placeholder_text="Search memories...", height=28, font=FONTS["body_sm"])
        self._memory_search_box.grid(row=0, column=0, padx=12, pady=10, sticky="ew")
        ctk.CTkButton(
            top,
            text="Search",
            width=60,
            height=28,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._refresh_memory_tab,
        ).grid(row=0, column=1, padx=(0, 6), pady=10)
        ctk.CTkButton(
            top,
            text="Refresh",
            width=66,
            height=28,
            font=FONTS["sidebar"],
            fg_color=self.colors["card"],
            hover_color=self.colors["border_light"],
            text_color=self.colors["text"],
            corner_radius=5,
            command=self._refresh_memory_tab,
        ).grid(row=0, column=2, padx=(0, 12), pady=10)

        # Sort/filter bar
        filter_bar = ctk.CTkFrame(top, fg_color="transparent")
        filter_bar.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 8))
        ctk.CTkLabel(filter_bar, text="Sort:", font=FONTS["sidebar_h"],
                     text_color=self.colors["text_dim"]).pack(side="left", padx=(0, 4))
        self._memory_sort_var = tk.StringVar(value="recent")
        ctk.CTkComboBox(filter_bar, values=["recent", "oldest", "importance"],
                        variable=self._memory_sort_var, width=100, height=26,
                        command=lambda v: self._refresh_memory_tab()).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(filter_bar, text="Category:", font=FONTS["sidebar_h"],
                     text_color=self.colors["text_dim"]).pack(side="left", padx=(0, 4))
        self._memory_cat_var = tk.StringVar(value="all")
        ctk.CTkComboBox(filter_bar, values=["all", "fact", "memory", "task"],
                        variable=self._memory_cat_var, width=100, height=26,
                        command=lambda v: self._refresh_memory_tab()).pack(side="left")

        left = ctk.CTkScrollableFrame(
            tab,
            fg_color=self.colors["panel"],
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
            corner_radius=12,
        )
        left.grid(row=1, column=0, sticky="nsew", padx=(6, 4), pady=8)
        left.grid_columnconfigure(0, weight=1)
        self._memory_list_frame = left

        right = ctk.CTkFrame(
            tab,
            fg_color=self.colors["panel"],
            corner_radius=12,
            border_width=1,
            border_color=self.colors["border"],
        )
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 6), pady=8)
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="Memory Detail", font=FONTS["name"], text_color=self.colors["accent"]).pack(anchor="w", padx=12, pady=(10, 6))
        self._memory_detail_box = ctk.CTkTextbox(
            right,
            height=260,
            font=FONTS["body_sm"],
            fg_color=self.colors["input_bg"],
            text_color=self.colors["text"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=8,
            wrap="word",
        )
        self._memory_detail_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 12))
        for label, cmd in [
            ("Pin", self._pin_selected_memory),
            ("Archive", self._archive_selected_memory),
            ("Edit", self._edit_selected_memory),
            ("Delete", self._delete_selected_memory),
        ]:
            ctk.CTkButton(
                btn_row,
                text=label,
                width=72,
                height=28,
                font=FONTS["sidebar"],
                fg_color=self.colors["card"],
                hover_color=self.colors["border_light"],
                text_color=self.colors["text"],
                corner_radius=5,
                command=cmd,
            ).pack(side="left", padx=(0, 6))
        self._set_textbox_content(self._memory_detail_box, "Select a memory to inspect or edit it.")
        self._refresh_memory_tab()

    def _refresh_memory_tab(self):
        """Refresh the memory explorer list and detail pane."""
        if not hasattr(self, "_memory_list_frame"):
            return
        query = self._memory_search_box.get().strip() if hasattr(self, "_memory_search_box") else ""
        sort_mode = self._memory_sort_var.get() if hasattr(self, "_memory_sort_var") else "recent"
        cat_filter = self._memory_cat_var.get() if hasattr(self, "_memory_cat_var") else "all"
        for widget in self._memory_list_frame.winfo_children():
            widget.destroy()

        memories = []
        if query:
            result = self.memory.search(query)
            memories.extend(result.get("keyword_results") or [])
            memories.extend(result.get("semantic_results") or [])
        else:
            memories.extend(self.memory.get_recent_memories(limit=30))

        seen = set()
        normalized = []
        for item in memories:
            meta_id = (item.get("metadata") or {}).get("memory_id")
            key = str(item.get("id") or meta_id or item.get("memory_id") or hash(item.get("content", "")))
            if key in seen:
                continue
            seen.add(key)
            normalized.append(item)

        # Apply category filter
        if cat_filter != "all":
            filtered = []
            for item in normalized:
                tags = item.get("tags") or (item.get("metadata") or {}).get("tags") or []
                if isinstance(tags, list):
                    tag_str = " ".join(tags).lower()
                else:
                    tag_str = str(tags).lower()
                if cat_filter in tag_str:
                    filtered.append(item)
            normalized = filtered

        # Sort
        if sort_mode == "oldest":
            normalized.reverse()
        elif sort_mode == "importance":
            try:
                normalized.sort(key=lambda x: float(x.get("metadata", {}).get("importance", 0) if isinstance(x.get("metadata"), dict) else 0), reverse=True)
            except Exception:
                pass

        self._memory_memory_rows = normalized
        for item in normalized:
            meta_id = (item.get("metadata") or {}).get("memory_id")
            memory_id = int(item.get("id") or meta_id or item.get("memory_id") or 0)
            if memory_id <= 0:
                continue
            preview = str(item.get("content", ""))[:100].replace("\n", " ")
            tags = item.get("tags") or (item.get("metadata") or {}).get("tags") or []
            tag_str = f" [{', '.join(tags[:3])}]" if tags else ""
            row = ctk.CTkButton(
                self._memory_list_frame,
                text=f"#{memory_id}{tag_str}  {preview}",
                anchor="w",
                height=34,
                font=FONTS["body_sm"],
                fg_color=self.colors["card"],
                hover_color=self.colors["border_light"],
                text_color=self.colors["text"],
                corner_radius=8,
                command=lambda mid=memory_id: self._select_memory(mid),
            )
            row.pack(fill="x", padx=10, pady=(8, 0))

        if self._selected_memory_id is not None:
            self._select_memory(self._selected_memory_id)
        elif normalized:
            self._select_memory(int(normalized[0].get("id") or normalized[0].get("memory_id") or 0))
        else:
            self._set_textbox_content(self._memory_detail_box, "No memories found.")

    def _select_memory(self, memory_id: int):
        """Load a memory into the detail view."""
        memory = self.memory.get_memory_by_id(memory_id)
        if not memory:
            return
        self._selected_memory_id = memory_id
        detail = [
            f"ID: {memory['id']}",
            f"Importance: {memory.get('importance', 0)}",
            f"Tags: {', '.join(memory.get('tags') or []) or 'none'}",
            f"Created: {memory.get('created_at', '—')}",
            f"Accessed: {memory.get('accessed_at', '—')}",
            f"Access Count: {memory.get('access_count', 0)}",
            "",
            memory.get("content", ""),
        ]
        self._set_textbox_content(self._memory_detail_box, "\n".join(detail).strip())

    def _edit_selected_memory(self):
        """Edit the selected memory."""
        if self._selected_memory_id is None:
            return
        memory = self.memory.get_memory_by_id(self._selected_memory_id)
        if not memory:
            return
        new_text = simpledialog.askstring(
            "Edit Memory",
            "Update the memory text:",
            initialvalue=memory.get("content", ""),
            parent=self,
        )
        if new_text is None:
            return
        if self.memory.update_memory(self._selected_memory_id, content=new_text):
            self._add_system_message("Memory updated.", self.colors["success"])
            self._refresh_memory_tab()

    def _delete_selected_memory(self):
        """Delete the selected memory."""
        if self._selected_memory_id is None:
            return
        if not messagebox.askyesno("Delete Memory", "Delete this memory permanently?", parent=self):
            return
        if self.memory.delete_memory(self._selected_memory_id):
            self._add_system_message("Memory deleted.", self.colors["warning"])
            self._selected_memory_id = None
            self._refresh_memory_tab()

    def _pin_selected_memory(self):
        """Pin the selected memory."""
        if self._selected_memory_id is None:
            return
        if self.memory.pin_memory(self._selected_memory_id, enabled=True):
            self._add_system_message("Memory pinned.", self.colors["success"])
            self._refresh_memory_tab()

    def _archive_selected_memory(self):
        """Archive the selected memory."""
        if self._selected_memory_id is None:
            return
        if self.memory.archive_memory(self._selected_memory_id, enabled=True):
            self._add_system_message("Memory archived.", self.colors["warning"])
            self._refresh_memory_tab()

    def _build_agents_tab(self, parent):
        """Build the agent collaboration center with workflow visualization."""
        tab = ctk.CTkScrollableFrame(
            parent,
            fg_color=self.colors["bg"],
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
        )
        tab.grid(row=0, column=0, sticky="nsew")
        tab.grid_columnconfigure(0, weight=1)
        self._agents_tab = tab
        self._agents_box = None

        card = ctk.CTkFrame(
            tab,
            fg_color=self.colors["panel"],
            corner_radius=12,
            border_width=1,
            border_color=self.colors["border"],
        )
        card.grid(row=0, column=0, sticky="nsew", padx=6, pady=8)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="Agent Workflow", font=FONTS["name"], text_color=self.colors["accent"]).pack(anchor="w", padx=12, pady=(10, 6))

        # Agent workflow pipeline
        self._agent_flow_container = ctk.CTkFrame(card, fg_color="transparent")
        self._agent_flow_container.pack(fill="x", padx=12, pady=(0, 8))

        agent_defs = [
            ("Research Agent", "research"),
            ("Memory Agent", "memory"),
            ("Planning Agent", "planning"),
            ("Reasoning Agent", "reasoning"),
            ("Coordinator", "coordinator"),
        ]
        self._agent_status_labels = {}
        for name, key in agent_defs:
            row = ctk.CTkFrame(self._agent_flow_container, fg_color=self.colors["card"],
                               corner_radius=8, border_width=1, border_color=self.colors["border"])
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(1, weight=1)
            dot = ctk.CTkLabel(row, text="○", font=("Segoe UI", 12), text_color=self.colors["text_dim"])
            dot.grid(row=0, column=0, padx=(8, 4), pady=4)
            ctk.CTkLabel(row, text=name, font=FONTS["sidebar"], text_color=self.colors["text"]).grid(row=0, column=1, sticky="w")
            sl = ctk.CTkLabel(row, text="idle", font=FONTS["time"], text_color=self.colors["text_dim"])
            sl.grid(row=0, column=2, padx=(4, 8))
            self._agent_status_labels[key] = (dot, sl)

        # Separator
        ctk.CTkFrame(card, height=1, fg_color=self.colors["border"]).pack(fill="x", padx=12, pady=4)

        self._agents_box = ctk.CTkTextbox(
            card,
            height=280,
            font=FONTS["body_sm"],
            fg_color=self.colors["input_bg"],
            text_color=self.colors["text"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=8,
            wrap="word",
        )
        self._agents_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._set_textbox_content(self._agents_box, "Agent activity will be shown here.")
        self._refresh_agents_tab()

    def _refresh_agents_tab(self):
        """Refresh agent logs and update the workflow visualization."""
        if not hasattr(self, "_agents_box"):
            return
        hyper = self._active_hyper_engine()
        logs = []
        if hyper and getattr(hyper, "_agent_orchestrator", None):
            try:
                logs = hyper._agent_orchestrator.get_logs(limit=20)
            except Exception:
                logs = []
        lines = []
        if not logs:
            lines.append("No agent activity yet.")
        else:
            for entry in logs[-20:]:
                lines.append(
                    f"[{entry.get('agent', 'agent')}] {entry.get('phase', '')} "
                    f"({entry.get('duration_ms', 0)} ms)"
                )
                entry_content = entry.get("content", "")
                if entry_content:
                    lines.append(entry_content[:600])
                    lines.append("")

        # Update workflow status dots
        if logs:
            latest = logs[-1]
            agent_name = str(latest.get("agent", "")).lower()
            for key, (dot, lbl) in self._agent_status_labels.items():
                is_active = key in agent_name
                try:
                    dot.configure(text="●" if is_active else "○",
                                  text_color=self.colors["success"] if is_active else self.colors["text_dim"])
                    lbl.configure(text="active" if is_active else "idle",
                                  text_color=self.colors["success"] if is_active else self.colors["text_dim"])
                except Exception:
                    pass

        self._set_textbox_content(self._agents_box, "\n".join(lines).strip())

    def _build_improvements_tab(self, parent):
        """Build the self-improvement center."""
        tab = ctk.CTkScrollableFrame(
            parent,
            fg_color=self.colors["bg"],
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
        )
        tab.grid(row=0, column=0, sticky="nsew")
        tab.grid_columnconfigure(0, weight=1)
        self._improvements_tab = tab
        self._improvement_frames = []
        self._improvement_decisions = {}

        header = ctk.CTkFrame(tab, fg_color=self.colors["panel"], corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Improvement Analyzer", font=FONTS["name"], text_color=self.colors["accent"]).pack(anchor="w", padx=12, pady=10)
        self._improvement_summary_box = ctk.CTkTextbox(
            tab,
            height=120,
            font=FONTS["body_sm"],
            fg_color=self.colors["input_bg"],
            text_color=self.colors["text"],
            border_color=self.colors["border"],
            border_width=1,
            corner_radius=8,
            wrap="word",
        )
        self._improvement_summary_box.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        self._set_textbox_content(self._improvement_summary_box, "Loading improvement suggestions...")
        self._improvement_list = ctk.CTkScrollableFrame(
            tab,
            fg_color=self.colors["panel"],
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
            corner_radius=12,
        )
        self._improvement_list.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self._refresh_improvements_tab()

    def _refresh_improvements_tab(self):
        """Refresh the improvement suggestions list."""
        if not hasattr(self, "_improvement_summary_box"):
            return
        hyper = self._active_hyper_engine()
        summary = {}
        if hyper and getattr(hyper, "_improvement_analyzer", None):
            try:
                summary = hyper._improvement_analyzer.summarize()
            except Exception:
                summary = {}
        self._set_textbox_content(self._improvement_summary_box, json.dumps(summary or {}, indent=2, ensure_ascii=False))
        for widget in getattr(self, "_improvement_list", []).winfo_children() if hasattr(self, "_improvement_list") else []:
            widget.destroy()
        findings = (summary or {}).get("findings") or []
        if not findings:
            ctk.CTkLabel(self._improvement_list, text="No findings yet.", text_color=self.colors["text_dim"]).pack(padx=12, pady=12)
            return
        for idx, finding in enumerate(findings[:20]):
            card = ctk.CTkFrame(
                self._improvement_list,
                fg_color=self.colors["card"],
                corner_radius=10,
                border_width=1,
                border_color=self.colors["border"],
            )
            card.pack(fill="x", padx=12, pady=(10 if idx == 0 else 0, 8))
            text = "\n".join(
                [
                    f"Issue: {finding.get('issue', 'n/a')}",
                    f"Location: {finding.get('location', 'n/a')}",
                    f"Suggested Fix: {finding.get('suggested_fix', 'n/a')}",
                    f"Estimated Improvement: {finding.get('estimated_improvement', 'n/a')}",
                ]
            )
            ctk.CTkLabel(card, text=text, justify="left", anchor="w", wraplength=720, text_color=self.colors["text"]).pack(anchor="w", padx=12, pady=(10, 6))
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(anchor="w", padx=12, pady=(0, 10))
            signature = f"{finding.get('location')}::{finding.get('issue')}"
            for label, status in [("Approve", "approved"), ("Reject", "rejected"), ("Archive", "archived")]:
                ctk.CTkButton(
                    row,
                    text=label,
                    width=72,
                    height=26,
                    font=FONTS["sidebar"],
                    fg_color=self.colors["card"],
                    hover_color=self.colors["border_light"],
                    text_color=self.colors["text"],
                    corner_radius=5,
                    command=lambda sig=signature, st=status: self._record_improvement_decision(sig, st),
                ).pack(side="left", padx=(0, 6))

    def _record_improvement_decision(self, signature: str, status: str):
        """Record a human decision about an improvement suggestion."""
        self._improvement_decisions[signature] = status
        self._add_system_message(f"Improvement {status}: {signature}", self.colors["accent"])

    def _build_settings_tab(self, parent):
        """Build the settings area."""
        tab = ctk.CTkScrollableFrame(
            parent,
            fg_color=self.colors["bg"],
            scrollbar_button_color=self.colors["scrollbar"],
            scrollbar_button_hover_color=self.colors["border_light"],
        )
        tab.grid(row=0, column=0, sticky="nsew")
        tab.grid_columnconfigure(0, weight=1)
        self._settings_tab = tab
        self._setting_vars = {}

        sections = [
            ("AI Settings", [
                ("hyper_enabled", "Enable Hyper Layer", bool(self._active_hyper_engine()), self._on_toggle_hyper),
                ("research_sources", "Research Sources", self._ui_settings.get("research_sources", 3), self._on_research_sources_change),
            ]),
            ("Performance", [
                ("refresh_interval_ms", "Refresh Interval (ms)", self._ui_settings.get("refresh_interval_ms", 2500), self._on_refresh_interval_change),
                ("compact_panels", "Compact Panels", self._ui_settings.get("compact_panels", False), self._on_compact_panels_change),
            ]),
            ("Appearance", [
                ("theme_mode", "Theme Mode", self._theme_mode, self._on_theme_mode_change),
                ("density", "Layout Density", self._ui_settings.get("density", "comfortable"), self._on_density_change),
                ("animations", "Animations", self._ui_settings.get("animations", True), self._on_animations_change),
                ("font_size", "Font Scale", self._font_scale, self._on_font_scale_change),
            ]),
            ("Voice", [
                ("voice_enabled", "Voice Enabled", self._voice_enabled, self._on_voice_enabled_change),
            ]),
        ]

        row = 0
        for section_title, items in sections:
            card = ctk.CTkFrame(
                tab,
                fg_color=self.colors["panel"],
                corner_radius=12,
                border_width=1,
                border_color=self.colors["border"],
            )
            card.grid(row=row, column=0, sticky="ew", padx=6, pady=(8, 4))
            card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text=section_title, font=FONTS["name"], text_color=self.colors["accent"]).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6))
            inner_row = 1
            for key, label, value, handler in items:
                ctk.CTkLabel(card, text=label, font=FONTS["sidebar"], text_color=self.colors["text_dim"]).grid(row=inner_row, column=0, sticky="w", padx=12, pady=6)
                if isinstance(value, bool):
                    var = tk.BooleanVar(value=value)
                    widget = ctk.CTkSwitch(card, text="", variable=var, command=lambda k=key, v=var, h=handler: h(k, v.get()))
                elif isinstance(value, int):
                    var = tk.StringVar(value=str(value))
                    widget = ctk.CTkEntry(card, textvariable=var, height=28)
                    widget.bind("<Return>", lambda e, k=key, v=var, h=handler: h(k, v.get()))
                else:
                    var = tk.StringVar(value=str(value))
                    if key == "theme_mode":
                        widget = ctk.CTkComboBox(card, values=["dark", "light", "system"], variable=var, command=lambda v, k=key, h=handler: h(k, v))
                    else:
                        widget = ctk.CTkComboBox(card, values=["compact", "comfortable", "spacious"], variable=var, command=lambda v, k=key, h=handler: h(k, v))
                widget.grid(row=inner_row, column=1, sticky="ew", padx=12, pady=6)
                self._setting_vars[key] = var
                inner_row += 1
            row += 1

        ctk.CTkLabel(
            tab,
            text="Changes are applied live when possible; some engine-level options take effect on the next turn or restart.",
            font=FONTS["body_sm"],
            text_color=self.colors["text_dim"],
        ).grid(row=row, column=0, sticky="w", padx=10, pady=10)
        self._refresh_settings_tab()

    def _refresh_settings_tab(self):
        """Sync settings controls with runtime state."""
        if not hasattr(self, "_setting_vars"):
            return
        try:
            if "hyper_enabled" in self._setting_vars:
                self._setting_vars["hyper_enabled"].set(bool(self._ui_settings.get("hyper_enabled", True)))
            if "research_sources" in self._setting_vars:
                self._setting_vars["research_sources"].set(str(self._ui_settings.get("research_sources", 3)))
            if "refresh_interval_ms" in self._setting_vars:
                self._setting_vars["refresh_interval_ms"].set(str(self._ui_settings.get("refresh_interval_ms", 2500)))
            if "compact_panels" in self._setting_vars:
                self._setting_vars["compact_panels"].set(bool(self._ui_settings.get("compact_panels", False)))
            if "theme_mode" in self._setting_vars:
                self._setting_vars["theme_mode"].set(self._theme_mode)
            if "density" in self._setting_vars:
                self._setting_vars["density"].set(str(self._ui_settings.get("density", "comfortable")))
            if "animations" in self._setting_vars:
                self._setting_vars["animations"].set(bool(self._ui_settings.get("animations", True)))
            if "font_size" in self._setting_vars:
                self._setting_vars["font_size"].set(str(self._font_scale))
            if "voice_enabled" in self._setting_vars:
                self._setting_vars["voice_enabled"].set(bool(self._voice_enabled))
        except Exception:
            pass

    def _on_toggle_hyper(self, key: str, value):
        self._ui_settings[key] = bool(value)
        self._add_system_message(
            "Hyper layer UI toggle updated. The next response will respect the new state.",
            self.colors["accent"],
        )

    def _on_research_sources_change(self, key: str, value):
        try:
            self._ui_settings[key] = max(1, int(value))
        except Exception:
            self._ui_settings[key] = 3

    def _on_refresh_interval_change(self, key: str, value):
        try:
            self._ui_settings[key] = max(1000, int(value))
        except Exception:
            self._ui_settings[key] = 2500

    def _on_compact_panels_change(self, key: str, value):
        self._ui_settings[key] = bool(value)

    def _on_theme_mode_change(self, key: str, value):
        mode = self._normalize_theme_mode(value)
        self._theme_mode = mode
        self._layout_state["theme_mode"] = mode
        try:
            ctk.set_appearance_mode(mode)
        except Exception:
            pass
        self._save_layout_state()

    def _on_density_change(self, key: str, value):
        self._ui_settings[key] = str(value)

    def _on_animations_change(self, key: str, value):
        self._ui_settings[key] = bool(value)

    def _on_font_scale_change(self, key: str, value):
        try:
            self._font_scale = max(0.7, min(1.5, float(value)))
        except Exception:
            self._font_scale = 1.0
        self._save_layout_state()

    def _on_voice_enabled_change(self, key: str, value):
        self._voice_enabled = bool(value)
        if self._voice:
            if self._voice_enabled:
                self._voice.start(push_to_talk=False)
            else:
                self._voice.stop()

    def _on_escape_key(self, event) -> None:
        """Escape: stop speech if speaking, otherwise focus input."""
        if self._voice and self._voice.tts.is_speaking:
            self._voice.tts.stop_speaking()
            self._set_status(f"Connected  {settings.OLLAMA_MODEL}", self.colors["success"])
        else:
            self._input_box.focus()

    def _on_speed_change(self, value: float) -> None:
        """Handle voice speed slider change."""
        if self._voice and self._voice.tts.is_available:
            # Kokoro uses speed parameter, pyttsx3 uses rate
            if self._voice.tts.backend == "kokoro":
                if hasattr(self._voice.tts._engine, 'voice'):
                    self._voice.tts._engine.voice = self._voice.tts._engine.voice  # trigger reload
            else:
                # pyttsx3: convert 0.6-1.6 to 120-220 wpm
                wpm = int(120 + (value - 0.6) * 100)
                self._voice.tts.set_rate(wpm)

    def _on_enter_key(self, event):
        """Handle Enter key — send message (Shift+Enter is a newline, ignored here)."""
        self._send_message()
        return "break"

    # ------------------------------------------------------------------ #
    # Sidebar Helpers
    # ------------------------------------------------------------------ #

    def _add_sidebar_section(self, parent, title: str):
        """Add a clean section header."""
        ctk.CTkLabel(
            parent,
            text=title,
            font=("Segoe UI", 9, "bold"),
            text_color=self.colors["accent"],
        ).pack(anchor="w", pady=(8, 3))

    def _add_sidebar_stat(self, parent, label: str, value: str) -> ctk.CTkLabel:
        """Add a label+value row. Returns the value label for updates."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=0)

        ctk.CTkLabel(
            row,
            text=label,
            font=FONTS["sidebar"],
            text_color=self.colors["text_dim"],
            width=80,
            anchor="w",
        ).pack(side="left")

        val = ctk.CTkLabel(
            row,
            text=value,
            font=FONTS["sidebar"],
            text_color=self.colors["text"],
            anchor="w",
        )
        val.pack(side="left", fill="x", expand=True)
        return val

    def _add_divider(self, parent):
        """Add a horizontal divider line."""
        ctk.CTkFrame(
            parent,
            height=1,
            fg_color=self.colors["border"],
        ).pack(fill="x", pady=8)

    # ------------------------------------------------------------------ #
    # Message Rendering
    # ------------------------------------------------------------------ #

    def _add_message_bubble(
        self,
        role: str,
        text: str,
        timestamp: Optional[str] = None,
    ) -> ctk.CTkTextbox:
        """
        Add a chat bubble to the conversation.

        Returns the CTkTextbox so streaming can append to it.
        """
        ts = timestamp or datetime.now().strftime("%H:%M")
        is_joseph = role == "assistant"

        # Outer container for the bubble row
        bubble_row = ctk.CTkFrame(
            self._chat_scroll,
            fg_color="transparent",
        )
        bubble_row.grid(
            row=self._message_row,
            column=0,
            sticky="ew",
            padx=(20, 32) if not is_joseph else (20, 48),
            pady=(4, 1),
        )
        bubble_row.grid_columnconfigure(0, weight=1)
        self._message_row += 1

        # Name + timestamp header
        header_row = ctk.CTkFrame(bubble_row, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 3), padx=(4 if is_joseph else 0, 0))

        name = settings.JOSEPH_NAME if is_joseph else settings.USER_NAME
        name_color = self.colors["text_joseph"] if is_joseph else self.colors["text_user"]

        ctk.CTkLabel(
            header_row,
            text=name,
            font=FONTS["name"],
            text_color=name_color,
        ).pack(side="left")

        ctk.CTkLabel(
            header_row,
            text=f"  {ts}",
            font=FONTS["time"],
            text_color=self.colors["text_dim"],
        ).pack(side="left")

        # Bubble wrapper (for accent bar on Joseph messages)
        if is_joseph:
            wrapper = ctk.CTkFrame(bubble_row, fg_color="transparent")
            wrapper.pack(fill="x")
            wrapper.grid_columnconfigure(1, weight=1)

            # Left accent bar (3px, accent color)
            accent_bar = ctk.CTkFrame(wrapper, width=3, fg_color=self.colors["accent"], corner_radius=2)
            accent_bar.grid(row=0, column=0, sticky="ns", padx=(0, 8))

            bubble_parent = ctk.CTkFrame(wrapper, fg_color="transparent")
            bubble_parent.grid(row=0, column=1, sticky="ew")
            bubble_parent.grid_columnconfigure(0, weight=1)
        else:
            bubble_parent = bubble_row

        # Message bubble
        bubble_color = self.colors["card"] if is_joseph else self.colors["card_user"]

        # Calculate initial height based on text length
        lines = max(2, text.count("\n") + len(text) // 75 + 1)
        height = min(max(lines * 22, 48), 420)

        textbox = ctk.CTkTextbox(
            bubble_parent,
            font=FONTS["body"],
            fg_color=bubble_color,
            text_color=self.colors["text"],
            border_width=0,
            corner_radius=8,
            wrap="word",
            height=height,
            activate_scrollbars=False,
        )
        textbox.pack(fill="x", padx=(0, 0), pady=(0, 0))

        if text:
            textbox.insert("end", text)
            textbox.configure(state="disabled")

        # Add rating buttons for Joseph's messages
        if is_joseph:
            self._add_rating_buttons(bubble_parent, textbox)

        return textbox

    def _add_rating_buttons(self, parent, textbox: ctk.CTkTextbox) -> None:
        """Add 👍 👎 rating buttons below a Joseph message."""
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(2, 0))

        def rate(value: int, row=btn_row):
            """Handle rating click."""
            if self._personality_learning:
                self._personality_learning.rate_last_response(value)
            # Visual feedback — show which was clicked
            for widget in row.winfo_children():
                widget.configure(fg_color="transparent")
            color = self.colors["success"] if value > 0 else self.colors["error"]
            # Briefly flash the button
            self.after(100, lambda: None)  # Small delay for feel
            logger.debug(f"Response rated: {value}")

        ctk.CTkButton(
            btn_row,
            text="👍",
            font=("Segoe UI", 11),
            width=28, height=22,
            fg_color="transparent",
            hover_color=self.colors["card"],
            text_color=self.colors["text_dim"],
            corner_radius=4,
            command=lambda: rate(1),
        ).pack(side="left", padx=(0, 2))

        ctk.CTkButton(
            btn_row,
            text="👎",
            font=("Segoe UI", 11),
            width=28, height=22,
            fg_color="transparent",
            hover_color=self.colors["card"],
            text_color=self.colors["text_dim"],
            corner_radius=4,
            command=lambda: rate(-1),
        ).pack(side="left")

        # Separator
        ctk.CTkFrame(btn_row, width=1, height=14, fg_color=self.colors["border"]).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_row,
            text="Copy",
            font=("Segoe UI", 10),
            width=42, height=22,
            fg_color="transparent",
            hover_color=self.colors["card"],
            text_color=self.colors["text_dim"],
            corner_radius=4,
            command=lambda: self._copy_to_clipboard(textbox.get("1.0", "end-1c")),
        ).pack(side="left", padx=(0, 2))

        ctk.CTkButton(
            btn_row,
            text="Regen",
            font=("Segoe UI", 10),
            width=48, height=22,
            fg_color="transparent",
            hover_color=self.colors["card"],
            text_color=self.colors["text_dim"],
            corner_radius=4,
            command=self._regenerate_last,
        ).pack(side="left")

    def _copy_to_clipboard(self, text: str):
        """Copy text to system clipboard."""
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._add_system_message("Copied to clipboard", self.colors["text_dim"])
        except Exception as e:
            logger.debug(f"Copy failed: {e}")

    def _regenerate_last(self):
        """Regenerate the last assistant response."""
        try:
            history = self.memory.get_conversation_history()
            user_msgs = [m for m in history if m.get("role") == "user"]
            if not user_msgs:
                return
            last_user = user_msgs[-1]["content"]
            if history and history[-1].get("role") == "assistant":
                self.memory.short_term._messages.pop()
            self._start_joseph_response(last_user)
        except Exception as e:
            logger.debug(f"Regenerate: {e}")

    def _add_system_message(self, text: str, color: Optional[str] = None, icon: Optional[str] = None):
        """Add a centered system/status message with optional icon."""
        msg_color = color or self.colors["text_dim"]

        # Auto-pick icon based on color if not provided
        if icon is None:
            if color == self.colors["success"]:
                icon = "✓"
            elif color == self.colors["error"]:
                icon = "✗"
            elif color == self.colors["warning"]:
                icon = "⚠"
            elif color == self.colors["accent"]:
                icon = "ℹ"
            else:
                icon = ""

        frame = ctk.CTkFrame(self._chat_scroll, fg_color="transparent")
        frame.grid(
            row=self._message_row,
            column=0,
            sticky="ew",
            padx=24,
            pady=4,
        )
        self._message_row += 1

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack()

        if icon:
            ctk.CTkLabel(
                inner,
                text=icon + "  ",
                font=FONTS["body_sm"],
                text_color=msg_color,
            ).pack(side="left")

        ctk.CTkLabel(
            inner,
            text=text,
            font=FONTS["body_sm"],
            text_color=msg_color,
            wraplength=700,
            justify="left",
        ).pack(side="left")

    def _scroll_to_bottom(self):
        """Scroll the chat area to the latest message."""
        self._chat_scroll._parent_canvas.yview_moveto(1.0)

    def _resize_textbox(self, textbox: ctk.CTkTextbox, text: str):
        """Resize a textbox to fit its content."""
        lines = max(2, text.count("\n") + len(text) // 75 + 1)
        height = min(max(lines * 22, 48), 420)
        textbox.configure(height=height)

    # ------------------------------------------------------------------ #
    # Typing Indicator
    # ------------------------------------------------------------------ #

    def _show_typing_indicator(self):
        """Show animated typing indicator while Joseph thinks."""
        self._typing_frame = ctk.CTkFrame(self._chat_scroll, fg_color="transparent")
        self._typing_frame.grid(row=self._message_row, column=0, sticky="w", padx=24, pady=4)
        self._message_row += 1

        self._typing_label = ctk.CTkLabel(
            self._typing_frame,
            text="Joseph  ● ○ ○",
            font=FONTS["body_sm"],
            text_color=self.colors["thinking"],
        )
        self._typing_label.pack(side="left")
        self._typing_anim_step = 0
        self._animate_typing()

    def _animate_typing(self):
        """Animate the typing indicator dots."""
        if not hasattr(self, "_typing_label") or not self._typing_label.winfo_exists():
            return
        patterns = ["Joseph  ● ○ ○", "Joseph  ○ ● ○", "Joseph  ○ ○ ●", "Joseph  ● ● ●"]
        self._typing_anim_step = (self._typing_anim_step + 1) % len(patterns)
        self._typing_label.configure(text=patterns[self._typing_anim_step])
        self._typing_timer = self.after(400, self._animate_typing)

    def _hide_typing_indicator(self):
        """Remove the typing indicator."""
        try:
            if hasattr(self, "_typing_timer"):
                self.after_cancel(self._typing_timer)
            if hasattr(self, "_typing_frame") and self._typing_frame.winfo_exists():
                self._typing_frame.destroy()
                self._message_row -= 1
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Sending Messages
    # ------------------------------------------------------------------ #

    def _send_message(self):
        """Handle the user pressing Send or Enter."""
        if self._is_responding:
            return  # Don't allow sending while Joseph is responding

        text = self._input_box.get().strip()
        if not text:
            return

        # Clear input
        self._input_box.delete(0, "end")

        # Handle special commands
        if text.startswith("/"):
            self._handle_command(text)
            return

        # Show user message
        self._add_message_bubble("user", text)
        self._scroll_to_bottom()

        # Add to memory
        self.memory.add_user_message(text)

        # Start Joseph's response
        self._start_joseph_response(text)

    def _handle_command(self, text: str):
        """Handle /commands typed in the input box."""
        parts = text[1:].split(" ", 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else None

        if cmd in ("quit", "exit"):
            self._on_close()

        elif cmd == "clear":
            self._cmd_clear()

        elif cmd == "memory":
            self._cmd_memory_status()

        elif cmd == "facts":
            self._cmd_show_facts()

        elif cmd == "reminders":
            self._cmd_reminders()

        elif cmd == "tasks":
            self._cmd_tasks()

        elif cmd == "notes":
            self._cmd_notes()

        elif cmd == "remember" and arg:
            self.memory.save_explicit_memory(arg)
            self._add_system_message(f"Saved to memory: {arg}", self.colors["success"])
            self._update_sidebar()
            self._scroll_to_bottom()

        elif cmd == "help":
            help_text = (
                "Commands: /clear  /memory  /facts  /remember <text>\n"
                "          /reminders  /tasks  /notes  /quit\n"
                "Or just type normally to chat. Press F2 for voice."
            )
            self._add_system_message(help_text, self.colors["accent"])
            self._scroll_to_bottom()

        else:
            self._add_system_message(
                f"Unknown command: /{cmd}  -  type /help for commands",
                self.colors["warning"],
            )
            self._scroll_to_bottom()

    # ------------------------------------------------------------------ #
    # Joseph Response (Background Thread)
    # ------------------------------------------------------------------ #

    def _start_joseph_response(self, user_text: str):
        """
        Start streaming Joseph's response on a background thread.
        The UI stays responsive while the LLM generates.
        """
        self._is_responding = True
        self._current_response = ""
        self._send_btn.configure(state="disabled", text="...")
        self._set_status("Thinking...", self.colors["warning"])

        # Show typing indicator
        self._show_typing_indicator()
        self._scroll_to_bottom()

        # Create the response bubble (empty, will be filled by streaming)
        # It will be created when first chunk arrives (via _hide_typing_indicator)
        self._active_textbox = None
        self._first_chunk = True

        # Mark LLM as busy so background tasks yield
        self._llm_busy.set()
        # Run LLM on background thread
        thread = threading.Thread(
            target=self._llm_worker,
            args=(user_text,),
            daemon=True,
        )
        thread.start()

    def _llm_worker(self, user_text: str):
        """
        Background thread: planner decides routing, then executes.
        """
        _t0 = time.perf_counter()
        try:
            # Check custom commands first
            if self._custom_commands:
                cmd_key = self._custom_commands.match(user_text)
                if cmd_key and self._router:
                    result = self._custom_commands.execute(cmd_key, self._router)
                    if result:
                        self._response_queue.put(("automation_done", result))
                        return

            # Check if multi-step task
            if (self._planner and self._task_agent and
                    self._planner.should_use_task_agent(user_text)):
                if self._router:
                    self._task_agent.set_router(self._router)
                result = self._task_agent.execute(user_text)
                if result:
                    self._response_queue.put(("automation_done", result))
                    return

            # Check for background research (runs alongside LLM, doesn't short-circuit)
            _research_query = self._detect_research_intent(user_text)
            if _research_query:
                self._start_background_research(_research_query)

            # Regular chat - stream from LLM
            from brain.prompts import get_system_prompt
            from brain.cognitive_router import quality_check

            _t1 = time.perf_counter()

            # Phase X: Classify request and determine cognitive path
            _cognitive_decision = None
            if self._cognitive_router:
                _cognitive_decision = self._cognitive_router.classify(user_text, llm_interface=self.llm)

            is_chat = self._planner and self._planner.analyze(user_text) == "chat"
            active_hyper = self._active_hyper_engine()

            # Phase X: Override is_chat with cognitive router classification
            if _cognitive_decision and _cognitive_decision.path.value == "fast":
                is_chat = True

            # Chat messages get lightweight context (facts only, no ChromaDB)
            if is_chat:
                memory_context = ""
                facts = self.memory.long_term.format_facts_for_context()
                if facts and facts != "No facts stored yet.":
                    memory_context = f"## Known Facts About {settings.USER_NAME}\n{facts}"
                self._hyper_turn_packet = None
            else:
                memory_context = self.memory.get_context_for_llm(query=user_text)
                self._hyper_turn_packet = prepare_hyper_turn(active_hyper, user_text, memory=self.memory)
                if self._hyper_turn_packet and self._hyper_turn_packet.get("system_context"):
                    memory_context = (
                        f"{memory_context}\n\n{self._hyper_turn_packet['system_context']}"
                        if memory_context
                        else self._hyper_turn_packet["system_context"]
                    )
                companion_ctx = self.memory.get_companion_context()
                if companion_ctx:
                    memory_context = companion_ctx + "\n\n" + memory_context

            # Inject research-in-progress context so LLM knows to acknowledge it
            if _research_query:
                research_note = (
                    f"\n\nNOTE: BACKGROUND RESEARCH IN PROGRESS on '{_research_query}'.\n"
                    f"The user asked you to research this. Acknowledge that you're looking into it "
                    f"and will update them with findings. Keep your response conversational."
                )
                memory_context += research_note

            _t2 = time.perf_counter()
            logger.debug(f"[perf] context_build: {_t2-_t1:.3f}s | chat={is_chat}")
            _t3 = time.perf_counter()

            # Check single automation command
            _ta = time.perf_counter()
            automation_result = self._try_automation(user_text)
            _tb = time.perf_counter()
            if _tb-_ta > 0.1:
                logger.debug(f"[perf] _try_automation: {_tb-_ta:.3f}s")
            if automation_result:
                # Log automation activity
                if self._activity_tracker:
                    self._activity_tracker.log(
                        entry_type="command",
                        summary=f"Automation: {user_text[:100]}",
                        category="automation",
                        duration_ms=(_tb-_ta)*1000,
                        source="automation",
                    )
                self._response_queue.put(("automation_done", automation_result))
                # Run memory agent in background
                if self._memory_agent:
                    import threading
                    def _safe_px(ua, fr):
                        if getattr(self, "_llm_busy", None) and self._llm_busy.is_set():
                            return
                        self._memory_agent.process_exchange(ua, fr)
                    threading.Thread(
                        target=_safe_px,
                        args=(user_text, automation_result),
                        daemon=True,
                    ).start()
                return

            extra_context = get_context_enhancement(active_hyper, user_text)
            if extra_context:
                memory_context = f"{memory_context}\n\n{extra_context}" if memory_context else extra_context

            # Phase X: Inject cognitive depth/path instructions
            if _cognitive_decision and self._cognitive_router:
                depth_inst = self._cognitive_router.get_depth_instruction(_cognitive_decision)
                path_inst = self._cognitive_router.get_path_instruction(_cognitive_decision)
                if depth_inst or path_inst:
                    instr = "\n".join(filter(None, [depth_inst, path_inst]))
                    memory_context = f"{memory_context}\n\n{instr}" if memory_context else instr

            # Phase 7 — project awareness context injection
            if self._project_awareness:
                # Lazily wire project manager from Phase 5 when available
                if not self._project_awareness._pm:
                    try:
                        pm = getattr(self, "_phase5_pmgr", None)
                        if pm:
                            self._project_awareness._pm = pm
                    except Exception:
                        pass
                if memory_context:
                    proj_ctx = self._project_awareness.get_context(user_text)
                    if proj_ctx:
                        memory_context = f"{memory_context}\n\n{proj_ctx}"

            # Phase 7 — advanced personality modifier
            personality_modifier = ""
            if self._advanced_personality:
                self._advanced_personality.update(user_text)
                personality_modifier = self._advanced_personality.get_system_modifier()

            # Phase X: Build system prompt with SmartCache if available
            _cache_key = (memory_context, personality_modifier)
            _sc = self._smart_cache
            if _sc:
                _sp_cached = _sc.get_prompt(str(_cache_key))
                if _sp_cached:
                    system_prompt = _sp_cached
                else:
                    system_prompt = get_system_prompt(
                        user_name=settings.USER_NAME,
                        memory_context=memory_context,
                    )
                    if personality_modifier:
                        system_prompt += f"\n\nCurrent context: {personality_modifier}"
                    if self._personality_learning:
                        style = self._personality_learning.get_style_modifier()
                        if style:
                            system_prompt += f"\n\nLearned preferences: {style}"
                    _sc.set_prompt(str(_cache_key), system_prompt)
            else:
                _cache_key = (memory_context, personality_modifier)
                if _cache_key != getattr(self, "_sp_cache_key", None):
                    system_prompt = get_system_prompt(
                        user_name=settings.USER_NAME,
                        memory_context=memory_context,
                    )
                    if personality_modifier:
                        system_prompt += f"\n\nCurrent context: {personality_modifier}"
                    if self._personality_learning:
                        style = self._personality_learning.get_style_modifier()
                        if style:
                            system_prompt += f"\n\nLearned preferences: {style}"
                    self._sp_cache = system_prompt
                    self._sp_cache_key = _cache_key
                else:
                    system_prompt = self._sp_cache

            # Limit conversation history to last 6 messages for speed
            messages = self.memory.get_conversation_history()
            if len(messages) > 6:
                messages = messages[-6:]

            full_response = ""
            turn_started = time.perf_counter()
            _t4 = turn_started
            logger.debug(f"[perf] context_build: {_t4-_t3:.3f}s | total_pre_llm: {_t4-_t0:.3f}s")
            # Use multi-model router if available, otherwise standard LLM
            if self._multi_model_router and self._multi_model_router._active_fast:
                stream_source = self._multi_model_router.chat_stream(
                    messages=messages,
                    user_input=user_text,
                    system_prompt=system_prompt,
                )
            else:
                stream_source = self.llm.chat_stream(
                    messages=messages,
                    system_prompt=system_prompt,
                )

            for chunk in stream_source:
                self._response_queue.put(("chunk", chunk))
                full_response += chunk

            # Phase X: Lightweight quality check
            full_response = quality_check(full_response, user_text)

            # Phase X: Record latency in cognitive decision
            if _cognitive_decision is not None:
                _cognitive_decision.latency.total_ms = (time.perf_counter() - _t1) * 1000
                _cognitive_decision.latency.llm_ms = (time.perf_counter() - turn_started) * 1000

            _t5 = time.perf_counter()
            logger.debug(f"[perf] llm_stream: {_t5-turn_started:.3f}s | total: {_t5-_t0:.3f}s | tokens: ~{len(full_response.split())}")
            self._response_queue.put(("done", None))

            # Log chat activity
            _total_ms = (_t5 - _t0) * 1000
            if self._activity_tracker:
                self._activity_tracker.log(
                    entry_type="chat",
                    summary=f"User: {user_text[:100]}",
                    category="chat",
                    duration_ms=_total_ms,
                    source="joseph",
                )
                if full_response:
                    self._activity_tracker.log(
                        entry_type="chat",
                        summary=f"Response: {full_response[:150]}",
                        category="chat",
                        duration_ms=0,
                        source="joseph",
                    )
            if self._insight_engine and self._activity_tracker:
                for entry in self._activity_tracker.recent(3):
                    self._insight_engine.ingest(entry)
            if self._ambient_intel and self._activity_tracker:
                for entry in self._activity_tracker.recent(2):
                    self._ambient_intel.ingest(entry)

            # Self-correction check (background, non-blocking)
            if full_response and len(full_response.split()) > 3:
                threading.Thread(
                    target=self._run_self_correction,
                    args=(user_text, full_response, messages, system_prompt),
                    daemon=True,
                ).start()

            # Record interaction for personality learning
            if self._personality_learning and full_response:
                try:
                    self._personality_learning.record_interaction(
                        user_text, full_response
                    )
                except Exception:
                    pass

            if active_hyper and full_response:
                try:
                    enhanced = enhance_response(
                        active_hyper,
                        user_text,
                        full_response,
                        context={"mode": "ui"},
                    )
                    if enhanced:
                        full_response = enhanced
                except Exception:
                    pass

            finalize_hyper_turn(
                active_hyper,
                user_text,
                full_response,
                elapsed_seconds=time.perf_counter() - turn_started,
                memory=self.memory,
            )

            # Phase X: Continuity and consolidation recording
            if self._continuity_engine and full_response:
                try:
                    self._continuity_engine.record_turn(user_text, full_response)
                except Exception:
                    pass

            if getattr(self, '_consolidation_engine', None) and full_response:
                try:
                    self._consolidation_engine.consolidate_conversation(
                        user_messages=[user_text],
                        assistant_messages=[full_response],
                        session_id=self.memory.session_id,
                    )
                except Exception:
                    pass

            # Run memory agent in background
            if self._memory_agent and full_response:
                import threading
                def _safe_process_exchange(ua, fr):
                    # Skip if user is already sending the next message
                    if getattr(self, "_llm_busy", None) and self._llm_busy.is_set():
                        return
                    self._memory_agent.process_exchange(ua, fr)
                threading.Thread(
                    target=_safe_process_exchange,
                    args=(user_text, full_response),
                    daemon=True,
                ).start()

        except Exception as e:
            logger.error(f"LLM worker error: {e}")
            self._response_queue.put(("error", str(e)))
        finally:
            self._llm_busy.clear()

    def _detect_research_intent(self, text: str) -> Optional[str]:
        """Check if text is a research query. Returns extracted query or None."""
        match = re.search(
            r"\b(research|learn about|tell me about|explain what|"
            r"find information on|look into|look up|"
            r"give me information on|i want to know about|"
            r"teach me about|educate me on|"
            r"background on|find out about|"
            r"i.d like to know|i want to learn)\b",
            text, re.IGNORECASE,
        )
        if not match:
            return None
        query = re.sub(
            r"^(research|learn about|tell me about|explain what|"
            r"find information on|look into|give me information on|"
            r"i want to know about|teach me about|educate me on|"
            r"background on|find out about|"
            r"i.d like to know|i want to learn)\s+",
            "", text.strip(), flags=re.IGNORECASE,
        ).strip().rstrip(".,!?")
        if not query or len(query) < 3:
            return None
        return query

    def _start_background_research(self, query: str):
        """Start background research on a topic. Shows progress bar immediately."""
        if not self._background_research or self._background_research.is_researching():
            return

        def _show_started():
            self._research_progress_frame.grid()
            self._research_progress_label.configure(
                text=f"  Researching: {query[:60]}",
                text_color=self.colors.get("accent", "#4d9de0"),
            )
            self._research_progress_bar.set(0.05)
            self._research_progress_bar.configure(progress_color=self.colors.get("accent", "#4d9de0"))

        self.after(0, _show_started)

        self._background_research.research(
            query,
            on_progress=self._on_research_progress,
        )

    def _try_automation(self, user_text: str) -> Optional[str]:
        """
        Try to handle user_text as an automation command.
        Uses LLM-powered tool dispatcher first, falls back to regex router.
        """
        try:
            from automation.command_router import CommandRouter
            from brain.tools import ToolDispatcher

            # Initialize router
            if self._router is None:
                self._router = CommandRouter(llm=self.llm)
            else:
                self._router.set_llm(self.llm)

            # Initialize tool dispatcher (smarter, LLM-powered)
            if self._tool_dispatcher is None:
                self._tool_dispatcher = ToolDispatcher(llm=self.llm)
                self._tool_dispatcher.attach_browser(
                    self._router.browser,
                    self._router._loop,
                )
                from automation.desktop.app_control import AppController
                self._tool_dispatcher.app_ctrl = AppController()

            # Attach Phase 9 background research to router (for LLM RESEARCH type)
            if self._background_research:
                self._router.attach_background_research(self._background_research)

            # Attach Phase 5 services to both
            services = dict(
                weather=self._weather,
                notes=self._notes,
                scheduler=self._scheduler,
                briefing=self._briefing,
            )
            self._router.attach_services(**services)
            self._tool_dispatcher.attach_services(**services)
            self._tool_dispatcher.attach_llm(self.llm)

            # Attach Phase 7 services
            if self._vision:
                self._tool_dispatcher.vision = self._vision
            if self._file_manager:
                self._tool_dispatcher.file_manager = self._file_manager
            if self._autonomous_agent:
                self._tool_dispatcher.autonomous_agent = self._autonomous_agent
                self._autonomous_agent.tool_dispatcher = self._tool_dispatcher
            # Phase 8 — Google
            if hasattr(self, "_google") and self._google:
                self._tool_dispatcher.google = self._google

            # Try regex router first (fast — catches "open", "weather", "search" etc.)
            response, was_automated = self._router.handle_sync(user_text)
            if was_automated and response:
                return response

            # Try LLM tool dispatcher only for non-chat messages (saves ~2 LLM calls per message)
            if not (self._planner and self._planner.analyze(user_text) == "chat"):
                response, was_automated = self._tool_dispatcher.dispatch(user_text)
                if was_automated and response:
                    return response

        except Exception as e:
            logger.debug(f"Automation check error: {e}")

        return None

    def _on_research_progress(self, stage: str, message: str):
        """
        Called by background research engine at each stage.
        Updates progress bar + shows status messages.
        """
        stage_progress = {
            "searching": 0.15,
            "reading": 0.35,
            "synthesizing": 0.65,
            "storing": 0.85,
            "complete": 1.0,
            "error": 0.0,
        }
        stage_labels = {
            "searching": "Searching the web",
            "reading": "Reading sources",
            "synthesizing": "Synthesizing findings",
            "storing": "Saving results",
            "complete": "Done",
            "error": "Failed",
        }
        colors = {
            "searching": self.colors.get("accent_dim", "#2a5a8a"),
            "reading": self.colors.get("accent", "#4d9de0"),
            "synthesizing": self.colors.get("thinking", "#8b5cf6"),
            "storing": self.colors.get("success", "#3dba7a"),
            "complete": self.colors.get("success", "#3dba7a"),
            "error": self.colors.get("error", "#d95f5f"),
        }
        progress = stage_progress.get(stage, 0.0)
        label_text = stage_labels.get(stage, stage.capitalize())
        color = colors.get(stage, self.colors.get("text_dim", "#7a7a7a"))

        def _update_ui():
            if stage == "complete":
                self._add_message_bubble("assistant", message)
                self._research_progress_frame.grid_remove()
            elif stage == "error":
                self._add_system_message(message, color)
                self._research_progress_frame.grid_remove()
            else:
                self._research_progress_frame.grid()
                short_msg = message.split("...")[0] if "..." in message else message
                self._research_progress_label.configure(
                    text=f"  {label_text}: {short_msg}",
                    text_color=color,
                )
                self._research_progress_bar.configure(
                    progress_color=color,
                    fg_color=self.colors.get("border", "#333"),
                )
                if progress > 0:
                    self._research_progress_bar.set(progress)
                self._scroll_to_bottom()

        self.after(0, _update_ui)

    def _poll_response_queue(self):
        """
        Poll the response queue every 30ms on the main thread.
        This is how background thread results safely reach the UI.
        """
        try:
            while True:
                msg_type, data = self._response_queue.get_nowait()

                if msg_type == "chunk":
                    # Hide typing indicator on first chunk and create bubble
                    if self._first_chunk:
                        self._first_chunk = False
                        self._hide_typing_indicator()
                        self._active_textbox = self._add_message_bubble("assistant", "")
                        self._active_textbox.configure(state="normal")

                    self._current_response += data
                    if self._active_textbox:
                        self._active_textbox.insert("end", data)
                        self._resize_textbox(self._active_textbox, self._current_response)
                    self._scroll_to_bottom()

                elif msg_type == "done":
                    self._finish_response()

                elif msg_type == "error":
                    self._hide_typing_indicator()
                    if self._active_textbox is None:
                        self._active_textbox = self._add_message_bubble("assistant", "")
                        self._active_textbox.configure(state="normal")
                    self._active_textbox.insert("end", f"\n[Error: {data}]")
                    self._finish_response(error=True)

                elif msg_type == "automation_done":
                    # Automation completed - show result, speak it
                    self._hide_typing_indicator()
                    if self._active_textbox is None:
                        self._active_textbox = self._add_message_bubble("assistant", "")
                        self._active_textbox.configure(state="normal")
                    self._active_textbox.insert("end", data)
                    self._resize_textbox(self._active_textbox, data)
                    self._current_response = data
                    self._finish_response()
                    if self._voice and self._voice_enabled:
                        self._voice.tts.speak(data)

                elif msg_type == "voice_input":
                    # Show voice-transcribed user message in chat
                    self._add_message_bubble("user", f"🎤 {data}")
                    self._scroll_to_bottom()

                elif msg_type == "voice_response":
                    # Show voice response in chat
                    self._add_message_bubble("assistant", data)
                    self._update_sidebar()
                    self._scroll_to_bottom()

        except queue.Empty:
            pass

        # Schedule next poll at 16ms (60fps feel)
        self.after(16, self._poll_response_queue)

    def _finish_response(self, error: bool = False):
        """Called when streaming is complete."""
        # Hide typing indicator (in case it's still showing)
        self._hide_typing_indicator()

        # Lock the textbox
        if hasattr(self, "_active_textbox") and self._active_textbox:
            self._active_textbox.configure(state="disabled")

        # Save to memory
        if self._current_response and not error:
            # Reuse cached personality engine instead of creating new one each time
            if not hasattr(self, "_pe_cache"):
                from brain.personality import PersonalityEngine
                self._pe_cache = PersonalityEngine()
            formatted = self._pe_cache.format_response(self._current_response)
            formatted = enhance_response(
                self._active_hyper_engine(),
                "",
                formatted,
                context={"mode": "ui"},
            )
            self.memory.add_assistant_message(formatted)

            # Background fact extraction
            threading.Thread(
                target=self._background_memory_tasks,
                daemon=True,
            ).start()

        # Generate follow-up suggestions
        if self._followup_engine and self._current_response and not error:
            try:
                self._last_followups = self._followup_engine.suggest(
                    self._last_user_text, self._current_response
                )
                suggestions_frame = getattr(
                    self, "_phase7_suggestions", None
                )
                if suggestions_frame and hasattr(suggestions_frame, "refresh"):
                    suggestions_frame.refresh(
                        followup_engine=self._followup_engine,
                        user_input=self._last_user_text,
                        response_text=self._current_response,
                    )
            except Exception:
                pass

        # Re-enable input
        self._is_responding = False
        self._send_btn.configure(state="normal", text="Send  ▶")
        self._set_status(f"Connected  {settings.OLLAMA_MODEL}", self.colors["success"])
        self._update_sidebar()
        self._update_turn_panel()
        self._input_box.focus()

    def _run_self_correction(self, question, response, messages, system_prompt):
        """Background self-correction check — never blocks UI."""
        # Skip if user is already sending the next message (frees LLM for chat)
        if getattr(self, "_llm_busy", None) and self._llm_busy.is_set():
            return
        try:
            from brain.self_correction import SelfCorrection
            if not hasattr(self, "_self_corrector"):
                self._self_corrector = SelfCorrection(llm=self.llm)
            corrected = self._self_corrector.check_and_correct(
                question, response, messages, system_prompt
            )
            if corrected != response and len(corrected) > len(response):
                logger.info("Self-correction improved response")
                self.memory.add_assistant_message(corrected)
        except Exception as e:
            logger.debug(f"Self-correction background error: {e}")

    def _background_memory_tasks(self):
        """Run memory extraction in background - never blocks UI."""
        # Skip if user is already sending the next message (frees LLM for chat)
        if getattr(self, "_llm_busy", None) and self._llm_busy.is_set():
            return
        try:
            self.memory.maybe_summarize(self.llm)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Sidebar Updates
    # ------------------------------------------------------------------ #

    def _update_phase5_sidebar(self) -> None:
        """Update Phase 5 service stats in sidebar."""
        try:
            if self._weather:
                weather = self._weather.get_weather()
                if weather:
                    self._svc_weather.configure(
                        text=f"{weather['temp_f']}F  {weather['condition']}"
                    )
                else:
                    self._svc_weather.configure(text="Unavailable")

            if self._notes:
                stats = self._notes.get_stats()
                self._svc_tasks.configure(
                    text=f"{stats['pending_tasks']} pending"
                )
                self._svc_notes.configure(
                    text=f"{stats['total_notes']} notes"
                )

            if self._scheduler:
                jobs = len(self._scheduler.get_jobs())
                self._svc_scheduler.configure(
                    text=f"{jobs} scheduled"
                )
        except Exception as e:
            logger.debug(f"Phase 5 sidebar update error: {e}")

    def _update_sidebar(self):
        """Refresh sidebar stats — only updates labels that changed."""
        try:
            status = self.memory.get_status()
            # Cache last values to avoid redundant label updates
            if not hasattr(self, "_sidebar_cache"):
                self._sidebar_cache = {}

            def _set_if_changed(label, key, value):
                if self._sidebar_cache.get(key) != value:
                    label.configure(text=value)
                    self._sidebar_cache[key] = value

            _set_if_changed(
                self._mem_conversation, "conv",
                f"{status['short_term_messages']} / {status['short_term_limit']}"
            )
            _set_if_changed(
                self._mem_memories, "mem",
                f"{status['long_term_memories']} memories"
            )
            _set_if_changed(self._mem_facts, "facts", str(status["long_term_facts"]))

            sem_text = "Active" if status["semantic_search"] else "Offline"
            sem_color = self.colors["success"] if status["semantic_search"] else self.colors["error"]
            if self._sidebar_cache.get("sem") != sem_text:
                self._mem_semantic.configure(text=sem_text, text_color=sem_color)
                self._sidebar_cache["sem"] = sem_text

            _set_if_changed(self._sess_id, "sid", status["session_id"])
        except Exception as e:
            logger.debug(f"Sidebar update error: {e}")

    def _set_status(self, text: str, dot_color: str = None):
        """Update the header status indicator and window title."""
        self._status_label.configure(text=text)
        if dot_color:
            self._status_dot.configure(text_color=dot_color)

        # Update window title based on status
        if "Thinking" in text:
            self.title("JOSEPH - Thinking...")
        elif "Listening" in text:
            self.title("JOSEPH - Listening...")
        else:
            self.title("JOSEPH - Personal AI Assistant")

    # ------------------------------------------------------------------ #
    # Quick Action Commands
    # ------------------------------------------------------------------ #

    def _cmd_clear(self):
        """Clear conversation history."""
        self.memory.short_term.clear()
        self._add_system_message("Conversation cleared", self.colors["text_dim"])
        self._update_sidebar()
        self._scroll_to_bottom()

    def _cmd_show_facts(self):
        """Show stored user facts in chat."""
        facts = self.memory.long_term.get_all_facts()
        if not facts:
            self._add_system_message("No facts stored yet.", self.colors["text_dim"])
        else:
            lines = "\n".join([f"  {k}: {v}" for k, v in facts.items()])
            self._add_system_message(f"Known facts:\n{lines}", self.colors["accent"])
        self._scroll_to_bottom()

    def _cmd_memory_status(self):
        """Show memory status in chat."""
        status_text = self.memory.format_status()
        self._add_system_message(status_text, self.colors["accent"])
        self._scroll_to_bottom()

    def _cmd_reminders(self):
        """Show scheduled reminders."""
        if self._scheduler:
            text = self._scheduler.format_jobs()
        else:
            text = "Scheduler not ready yet."
        self._add_system_message(text, self.colors["accent"])
        self._scroll_to_bottom()

    def _cmd_tasks(self):
        """Show pending tasks."""
        if self._notes:
            tasks = self._notes.get_pending_tasks()
            text = self._notes.format_tasks(tasks)
        else:
            text = "Tasks not ready yet."
        self._add_system_message(text, self.colors["accent"])
        self._scroll_to_bottom()

    def _cmd_notes(self):
        """Show recent notes."""
        if self._notes:
            notes = self._notes.get_recent_notes(limit=10)
            text = self._notes.format_notes(notes)
        else:
            text = "Notes not ready yet."
        self._add_system_message(text, self.colors["accent"])
        self._scroll_to_bottom()

    def _do_search(self) -> None:
        """Execute search from the search bar."""
        query = self._search_box.get().strip()
        if not query:
            return
        self._search_box.delete(0, "end")
        self._cmd_search(query)

    def _cmd_search(self, query: str = "") -> None:
        """Search all conversations and memories."""
        if not query:
            self._add_system_message(
                "Usage: /search <query>  or  type 'search my conversations for X'",
                self.colors["text_dim"],
            )
            self._scroll_to_bottom()
            return

        if self._conversation_search:
            results = self._conversation_search.search(query)
            text = self._conversation_search.format_results(results)
        else:
            text = "Search not available."
        self._add_system_message(text, self.colors["accent"])
        self._scroll_to_bottom()

    def _cmd_focus(self, duration: int = 25) -> None:
        """Start a focus session."""
        if self._focus_mode:
            result = self._focus_mode.start(duration_minutes=duration)
            self._add_message_bubble("assistant", result)
        else:
            self._add_system_message("Focus mode not ready.", self.colors["text_dim"])
        self._scroll_to_bottom()

    def _cmd_focus_status(self) -> None:
        """Show focus session status."""
        if self._focus_mode:
            text = self._focus_mode.status()
            self._add_system_message(text, self.colors["accent"])
        self._scroll_to_bottom()

    def _cmd_emails(self) -> None:
        """Show email triage."""
        def do_triage():
            if self._email_triage:
                text = self._email_triage.get_morning_summary()
            else:
                text = "Email triage not available. Set up Google integration first."
            self.after(0, lambda: self._add_system_message(text, self.colors["accent"]))
            self.after(0, self._scroll_to_bottom)

        import threading
        threading.Thread(target=do_triage, daemon=True).start()

    def _cmd_spotify(self, action: str = "", query: str = "") -> None:
        """Control Spotify."""
        if not self._spotify:
            self._add_system_message(
                "Spotify not configured. Add SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET to .env",
                self.colors["text_dim"],
            )
            self._scroll_to_bottom()
            return

        if action == "play":
            result = self._spotify.play(query)
        elif action == "pause":
            result = self._spotify.pause()
        elif action == "next":
            result = self._spotify.next_track()
        elif action == "status":
            result = self._spotify.now_playing()
        else:
            result = self._spotify.now_playing()

        self._add_system_message(result, self.colors["accent"])
        self._scroll_to_bottom()

    # ------------------------------------------------------------------ #
    # Session Lifecycle
    # ------------------------------------------------------------------ #

    def _start_session(self):
        """Initialize session and show greeting."""
        self.memory.start_session()
        active_hyper = self._active_hyper_engine()
        if active_hyper and hasattr(active_hyper, "set_session_context"):
            active_hyper.set_session_context(self.memory.session_id)
        self._update_sidebar()
        self._update_turn_panel()
        if hasattr(self, "_sess_started"):
            self._sess_started.configure(text=datetime.now().strftime("%H:%M"))

        # Show greeting on a slight delay so UI renders first
        self.after(400, self._show_greeting)
        self.after(1500, self._init_agents)
        self.after(2000, self._init_phase5)
        self.after(2500, self._refresh_command_center)
        # Warm-start the LLM model so first user message isn't cold
        try:
            import threading
            threading.Thread(target=self.llm.generate, args=("hi",), kwargs={"max_tokens": 1}, daemon=True).start()
        except Exception:
            pass

    def _show_greeting(self):
        """Show Joseph's opening greeting."""
        greeting = self.personality.get_greeting()
        self._add_message_bubble("assistant", greeting)
        self.memory.add_assistant_message(greeting)
        self._scroll_to_bottom()

    # ------------------------------------------------------------------ #
    # Voice System
    # ------------------------------------------------------------------ #

    def _init_voice(self) -> None:
        """Initialize the voice system after the UI is ready."""
        try:
            from voice.voice_controller import VoiceController, VoiceState

            self._voice = VoiceController(
                on_text_callback=self._handle_voice_text,
                on_state_change=self._on_voice_state_change,
            )

            started = self._voice.start(push_to_talk=False)

            if started:
                self._voice_enabled = True
                self._voice_btn.configure(
                    text_color=self.colors["success"],
                    fg_color=self.colors["card"],
                )
                self._voice_state_label.configure(
                    text=f"Say '{settings.WAKE_WORD}'...",
                    text_color=self.colors["text_dim"],
                )
                logger.info("Voice system started from UI")
            else:
                self._voice_state_label.configure(
                    text="Voice unavailable - text only",
                    text_color=self.colors["text_dim"],
                )

        except Exception as e:
            logger.warning(f"Voice init failed: {e}")
            try:
                self._voice_state_label.configure(
                    text="Voice unavailable",
                    text_color=self.colors["text_dim"],
                )
            except Exception:
                pass

    def _init_agents(self) -> None:
        """Initialize Phase 4 agents."""
        try:
            from agents.memory_agent import MemoryAgent
            from agents.task_agent import TaskAgent
            from agents.planner_agent import PlannerAgent

            self._memory_agent = MemoryAgent(
                memory_manager=self.memory,
                llm=self.llm,
            )
            self._task_agent = TaskAgent(llm=self.llm)
            self._planner = PlannerAgent(llm=self.llm)
            logger.info("Phase 4 agents initialized")
        except Exception as e:
            logger.warning(f"Agent init failed: {e}")

    def _init_phase5(self) -> None:
        """Initialize Phase 5+ services — all in parallel background threads."""
        threading.Thread(target=self._load_phase5_services, daemon=True).start()

    def _load_phase5_services(self) -> None:
        """Load all Phase 5+ services (runs on background thread)."""
        try:
            from brain.weather import WeatherService
            from brain.notes import NotesManager
            from brain.briefing import BriefingSystem
            from brain.context_awareness import ContextAwareness
            from brain.google_integration import GoogleIntegration
            from brain.hotkey_daemon import HotkeyDaemon
            from scheduler.scheduler_manager import SchedulerManager

            self._weather = WeatherService()
            self._notes = NotesManager()
            self._context_awareness = ContextAwareness()
            self._context_awareness.start()
            self._google = GoogleIntegration()

            # Scheduler with TTS callback
            def speak_reminder(msg: str):
                if self._voice and self._voice_enabled:
                    self._voice.tts.speak(msg, interrupt=True)
                self.after(0, lambda: self._add_system_message(
                    f"Reminder: {msg}", self.colors["warning"]
                ))

            self._scheduler = SchedulerManager(on_reminder=speak_reminder)
            self._scheduler.start()

            # Briefing system — include Google calendar if available
            self._briefing = BriefingSystem(
                weather_service=self._weather,
                notes_manager=self._notes,
                scheduler=self._scheduler,
                memory_manager=self.memory,
                tts=self._voice.tts if self._voice else None,
            )

            # Hotkey daemon
            self._hotkey_daemon = HotkeyDaemon()
            self._hotkey_daemon.start(
                on_activate=self._hotkey_activate,
                on_screenshot=self._hotkey_screenshot,
                on_clipboard=self._hotkey_clipboard,
                on_briefing=self._hotkey_briefing,
                on_note=self._hotkey_note,
            )

            # Attach services to router
            if self._router:
                self._router.attach_services(
                    weather=self._weather,
                    notes=self._notes,
                    scheduler=self._scheduler,
                    briefing=self._briefing,
                )

            # Phase 7 — Vision, File Manager, Autonomous Agent
            self._init_phase7()

            # Phase 9 — Notifications, Tray, Proactive, Multi-model, Plugins
            self._init_phase9()

            # Phase 8 — Connect project store to workspace engines
            pm = getattr(self, "_phase5_pmgr", None)
            if pm and hasattr(pm, "project_store"):
                self._project_store = pm.project_store
                if self._workspace_manager:
                    self._workspace_manager._ps = pm.project_store
                    self._workspace_manager._gt = pm.goal_tracker
                    self._workspace_manager._mt = pm.milestone_tracker
                    self._workspace_manager._tm = pm.task_manager
                    self._workspace_manager._nm = getattr(self, "_notes", None)
                if self._project_commander:
                    self._project_commander._wm = self._workspace_manager
                # Connect briefing_v2 / weekly_review to project_store
                for engine in [self._briefing_v2, self._weekly_review]:
                    if engine:
                        engine._ps = pm.project_store
                # Connect project_memory and continuity_engine to project_store
                if self._project_memory:
                    self._project_memory._ps = pm.project_store
                if self._continuity_engine:
                    self._continuity_engine._ps = pm.project_store
                # Connect ambient_intel to project_manager
                if self._ambient_intel:
                    self._ambient_intel._pm = pm
                # Connect followup_engine to project_manager
                if self._followup_engine:
                    self._followup_engine._pm = pm
                # Connect Phase 9 engines to research workspace & project store
                if self._document_intelligence and self._research_workspace:
                    self._document_intelligence._rw = self._research_workspace
                if self._paper_analyzer and self._research_workspace:
                    self._paper_analyzer._rw = self._research_workspace
                logger.info("Phase 8: Engines connected to project store")

            # Start API server in background
            self._start_api_server()

            # Update sidebar
            self.after(0, self._update_phase5_sidebar)
            logger.info("All services initialized (Phase 5-8)")

        except Exception as e:
            logger.warning(f"Service init failed: {e}")

    def _init_phase11(self) -> None:
        """Initialize Phase 11 — Spotify, Focus Mode, Email Triage."""
        try:
            from brain.spotify import SpotifyController
            from brain.focus_mode import FocusMode
            from brain.email_triage import EmailTriage

            self._spotify = SpotifyController()

            def on_break(msg: str):
                if self._voice and self._voice_enabled:
                    self._voice.tts.speak(msg)
                self.after(0, lambda: self._add_message_bubble("assistant", msg))
                self.after(0, self._scroll_to_bottom)
                if self._notifications:
                    self._notifications.send_alert(msg)

            self._focus_mode = FocusMode(
                on_break=on_break,
                scheduler=self._scheduler,
                spotify=self._spotify,
                browser=self._router.browser if self._router else None,
            )

            self._email_triage = EmailTriage(
                google=self._google,
                llm=self.llm,
            )

            # Add Spotify and focus to tool dispatcher
            if self._tool_dispatcher:
                self._tool_dispatcher.spotify = self._spotify
                self._tool_dispatcher.focus_mode = self._focus_mode
                self._tool_dispatcher.email_triage = self._email_triage

            logger.info("Phase 11 initialized — Spotify, Focus Mode, Email Triage")

        except Exception as e:
            logger.warning(f"Phase 11 init failed: {e}")

    def _init_phase10(self) -> None:
        """Initialize Phase 10 — Clipboard Monitor, Custom Commands, Personality Learning."""
        try:
            from brain.clipboard_monitor import ClipboardMonitor
            from brain.custom_commands import CustomCommandManager
            from brain.personality_learning import PersonalityLearning

            # Clipboard monitor
            self._clipboard_monitor = ClipboardMonitor(
                on_suggestion=self._on_clipboard_suggestion
            )
            self._clipboard_monitor.start()

            # Custom commands
            self._custom_commands = CustomCommandManager()

            # Personality learning
            self._personality_learning = PersonalityLearning()

            logger.info(
                f"Phase 10 initialized — "
                f"Clipboard: monitoring, "
                f"Custom commands: {self._custom_commands.command_count}, "
                f"Personality learning: active"
            )
        except Exception as e:
            logger.warning(f"Phase 10 init failed: {e}")

    def _on_clipboard_suggestion(self, suggestion: str, item) -> None:
        """Called by clipboard monitor with a contextual suggestion."""
        self.after(0, lambda: self._add_system_message(
            suggestion, self.colors["text_dim"]
        ))
        self.after(0, self._scroll_to_bottom)

    def _init_phase9(self) -> None:
        """Initialize Phase 9 — Notifications, Tray, Proactive, Multi-model, Plugins."""
        try:
            from brain.notifications import NotificationSystem
            from brain.system_tray import SystemTray
            from brain.proactive import ProactiveEngine
            from brain.multi_model import MultiModelRouter
            from brain.plugin_system import PluginSystem
            from brain.conversation_search import ConversationSearch

            # Notifications
            self._notifications = NotificationSystem()

            # Update scheduler to also send notifications
            if self._scheduler:
                original_callback = self._scheduler.on_reminder
                def enhanced_reminder(msg: str):
                    original_callback(msg)
                    self._notifications.send_reminder(msg)
                self._scheduler.on_reminder = enhanced_reminder

            # System tray
            self._system_tray = SystemTray()
            self._system_tray.start(
                on_show=lambda: self.after(0, self.deiconify),
                on_hide=lambda: self.after(0, self.withdraw),
                on_voice=self._hotkey_activate,
                on_briefing=self._hotkey_briefing,
                on_exit=lambda: self.after(0, self._on_close),
            )

            # Proactive engine
            self._proactive_engine = ProactiveEngine(
                on_suggestion=self._on_proactive_suggestion
            )
            self._proactive_engine.attach_services(
                notes=self._notes,
                weather=self._weather,
                scheduler=self._scheduler,
                memory=self.memory,
            )
            self._proactive_engine.start()

            # Multi-model router
            self._multi_model_router = MultiModelRouter(llm_interface=self.llm)

            # Plugin system
            self._plugin_system = PluginSystem()
            plugin_context = {
                "llm": self.llm,
                "memory": self.memory,
                "notes": self._notes,
                "weather": self._weather,
                "scheduler": self._scheduler,
            }
            self._plugin_system.load_all(context=plugin_context)

            # Conversation search
            self._conversation_search = ConversationSearch(memory_manager=self.memory)

            # Phase 10 — Clipboard, Custom Commands, Personality Learning
            self._init_phase10()

            # Phase 11 — Spotify, Focus Mode, Email Triage
            self._init_phase11()

            logger.info("Phase 9 services initialized")

        except Exception as e:
            logger.warning(f"Phase 9 init failed: {e}")

    def _on_proactive_suggestion(self, message: str) -> None:
        """Called by proactive engine with a suggestion."""
        # Show in chat
        self.after(0, lambda: self._add_system_message(
            f"💡 {message}", self.colors["accent"]
        ))
        self.after(0, self._scroll_to_bottom)
        # Speak it
        if self._voice and self._voice_enabled:
            self._voice.tts.speak(message)
        # Send Windows notification
        if self._notifications:
            self._notifications.send_alert(message)

    def _init_phase7(self) -> None:
        """Initialize Phase 7 — Vision, File Manager, Autonomous Agent."""
        try:
            from brain.vision import VisionSystem
            from brain.file_manager import FileManager
            from brain.personality_engine import AdvancedPersonality
            from agents.autonomous_agent import AutonomousAgent

            self._vision = VisionSystem(llm=self.llm)
            self._file_manager = FileManager()
            self._advanced_personality = AdvancedPersonality()
            self._advanced_personality.load_from_memory(self.memory)

            self._autonomous_agent = AutonomousAgent(
                llm=self.llm,
                tool_dispatcher=self._tool_dispatcher,
                on_step=self._on_agent_step,
            )

            logger.info(
                f"Phase 7 initialized — "
                f"Vision: {self._vision.is_available}, "
                f"Files: ready, "
                f"Autonomous: ready"
            )
        except Exception as e:
            logger.warning(f"Phase 7 init failed: {e}")

    def _on_agent_step(self, step: int, action_type: str, result: str) -> None:
        """Called by autonomous agent after each step — updates UI."""
        self.after(0, lambda: self._add_system_message(
            f"Step {step} [{action_type}]: {result[:80]}...",
            self.colors["thinking"],
        ))
        self.after(0, self._scroll_to_bottom)
        """
        Initialize the voice system after the UI is ready.
        Runs 1 second after startup so the window appears first.
        """
        try:
            from voice.voice_controller import VoiceController, VoiceState

            self._voice = VoiceController(
                on_text_callback=self._handle_voice_text,
                on_state_change=self._on_voice_state_change,
            )

            # Start with wake word detection
            started = self._voice.start(push_to_talk=False)

            if started:
                self._voice_enabled = True
                self._voice_btn.configure(
                    text_color=self.colors["success"],
                    fg_color=self.colors["card"],
                )
                self._voice_state_label.configure(
                    text=f"Listening for '{settings.WAKE_WORD}'...",
                    text_color=self.colors["text_dim"],
                )
                logger.info("Voice system started from UI")
            else:
                self._voice_state_label.configure(
                    text="Voice unavailable - text only",
                    text_color=self.colors["text_dim"],
                )

        except Exception as e:
            logger.warning(f"Voice init failed: {e}")
            self._voice_state_label.configure(
                text="Voice unavailable",
                text_color=self.colors["text_dim"],
            )

    def _toggle_voice(self) -> None:
        """Toggle push-to-talk listening."""
        if not self._voice or not self._voice_enabled:
            self._add_system_message(
                "Voice system not available. Check microphone.",
                self.colors["warning"],
            )
            return

        from voice.voice_controller import VoiceState

        if self._voice.state == VoiceState.IDLE:
            # Trigger push-to-talk
            self._voice_btn.configure(
                fg_color=self.colors["error"],
                text_color="#ffffff",
            )
            self._voice_state_label.configure(
                text="Listening... speak now",
                text_color=self.colors["error"],
            )
            self._set_status("Listening...", self.colors["error"])
            self._voice.push_to_talk()
        else:
            self._add_system_message(
                "Already listening or processing...",
                self.colors["text_dim"],
            )

    def _handle_voice_text(self, text: str) -> str:
        """
        Called by VoiceController with transcribed speech.
        Checks automation first, then streams LLM response to TTS.
        """
        logger.info(f"Voice input: '{text}'")
        self._response_queue.put(("voice_input", text))
        self.memory.add_user_message(text)

        # Try automation first
        automation_result = self._try_automation(text)
        if automation_result:
            self.memory.add_assistant_message(automation_result)
            self._response_queue.put(("voice_response", automation_result))
            if self._voice:
                self._voice.tts.speak(automation_result)
            return automation_result

        # Stream LLM response — speak sentences as they arrive
        try:
            from brain.prompts import get_system_prompt

            memory_context = self.memory.get_context_for_llm(query=text)
            active_hyper = self._active_hyper_engine()
            hyper_packet = prepare_hyper_turn(active_hyper, text, memory=self.memory)
            if hyper_packet.get("system_context"):
                memory_context = (
                    f"{memory_context}\n\n{hyper_packet['system_context']}"
                    if memory_context
                    else hyper_packet["system_context"]
                )
            extra_context = get_context_enhancement(active_hyper, text)
            if extra_context:
                memory_context = f"{memory_context}\n\n{extra_context}" if memory_context else extra_context
            system_prompt = get_system_prompt(
                user_name=settings.USER_NAME,
                memory_context=memory_context,
            )
            messages = self.memory.get_conversation_history()

            # Get the stream iterator
            start_time = time.perf_counter()
            stream = self.llm.chat_stream(
                messages=messages,
                system_prompt=system_prompt,
            )

            full_response = ""
            display_buffer = ""

            # Stream TTS sentence by sentence while collecting full response
            import re
            sentence_end = re.compile(r'(?<=[.!?])\s+')
            tts_buffer = ""

            for chunk in stream:
                full_response += chunk
                display_buffer += chunk
                tts_buffer += chunk

                # Speak complete sentences immediately
                parts = sentence_end.split(tts_buffer)
                if len(parts) > 1:
                    for sentence in parts[:-1]:
                        sentence = sentence.strip()
                        if sentence and len(sentence) > 3 and self._voice:
                            self._voice.tts.speak(sentence)
                    tts_buffer = parts[-1]

            # Speak any remaining text
            if tts_buffer.strip() and self._voice:
                self._voice.tts.speak(tts_buffer.strip())

            if full_response:
                if not hasattr(self, "_pe_cache"):
                    from brain.personality import PersonalityEngine
                    self._pe_cache = PersonalityEngine()
                formatted = self._pe_cache.format_response(full_response)
                formatted = enhance_response(
                    active_hyper,
                    text,
                    formatted,
                    context={"mode": "voice"},
                )
                self.memory.add_assistant_message(formatted)
                finalize_hyper_turn(
                    active_hyper,
                    text,
                    formatted,
                    elapsed_seconds=time.perf_counter() - start_time,
                    memory=self.memory,
                )
                self._response_queue.put(("voice_response", formatted))
                return formatted

        except Exception as e:
            logger.error(f"Voice LLM error: {e}")
            error_msg = "Sorry, something went wrong."
            self._response_queue.put(("voice_response", error_msg))
            if self._voice:
                self._voice.tts.speak(error_msg)
            return error_msg

        return ""

    def _on_voice_state_change(self, state) -> None:
        """Called when voice state changes - updates UI indicators."""
        from voice.voice_controller import VoiceState

        state_display = {
            VoiceState.IDLE: (f"Say '{settings.WAKE_WORD}'...", self.colors["text_dim"]),
            VoiceState.WAKE_DETECTED: ("Wake word detected!", self.colors["accent"]),
            VoiceState.LISTENING: ("Listening...", self.colors["error"]),
            VoiceState.PROCESSING: ("Processing...", self.colors["warning"]),
            VoiceState.SPEAKING: ("Speaking...", self.colors["success"]),
            VoiceState.DISABLED: ("Voice disabled", self.colors["text_dim"]),
        }

        text, color = state_display.get(state, ("", self.colors["text_dim"]))

        # Update UI on main thread
        self.after(0, lambda: self._voice_state_label.configure(
            text=text, text_color=color
        ))

        # Reset voice button color when idle
        if state == VoiceState.IDLE:
            self.after(0, lambda: self._voice_btn.configure(
                fg_color=self.colors["card"],
                text_color=self.colors["success"],
            ))

    # ------------------------------------------------------------------ #
    # Phase 8 — Hotkeys, Google, API
    # ------------------------------------------------------------------ #

    def _hotkey_activate(self) -> None:
        """Called by Ctrl+Shift+J — activate voice push-to-talk."""
        self.after(0, self._toggle_voice)

    def _hotkey_screenshot(self) -> None:
        """Called by Ctrl+Shift+S — screenshot and analyze."""
        def do_screenshot():
            if self._vision:
                result = self._vision.describe_screen()
            elif self._file_manager:
                path = self._file_manager._resolve_path
                import pyautogui
                path = str(settings.EXPORTS_DIR / f"screenshot_{datetime.now().strftime('%H%M%S')}.png")
                pyautogui.screenshot(path)
                result = f"Screenshot saved: {path}"
            else:
                result = "Vision system not available."
            self.after(0, lambda: self._add_message_bubble("assistant", result))
            self.after(0, self._scroll_to_bottom)

        import threading
        threading.Thread(target=do_screenshot, daemon=True).start()

    def _hotkey_clipboard(self) -> None:
        """Called by Ctrl+Shift+C — read clipboard."""
        def do_clipboard():
            import pyperclip
            content = pyperclip.paste()
            if content:
                preview = content[:300] + "..." if len(content) > 300 else content
                result = f"Clipboard:\n{preview}"
            else:
                result = "Clipboard is empty."
            self.after(0, lambda: self._add_message_bubble("assistant", result))
            self.after(0, self._scroll_to_bottom)

        import threading
        threading.Thread(target=do_clipboard, daemon=True).start()

    def _hotkey_briefing(self) -> None:
        """Called by Ctrl+Shift+B — daily briefing."""
        def do_briefing():
            if self._briefing:
                result = self._briefing.generate()
                if self._voice and self._voice_enabled:
                    self._voice.tts.speak(result)
            else:
                result = "Briefing system not ready."
            self.after(0, lambda: self._add_message_bubble("assistant", result))
            self.after(0, self._scroll_to_bottom)

        import threading
        threading.Thread(target=do_briefing, daemon=True).start()

    def _hotkey_note(self) -> None:
        """Called by Ctrl+Shift+N — focus input for quick note."""
        self.after(0, lambda: self._input_box.focus())
        self.after(0, lambda: self._input_box.insert(0, "add note: "))

    def _start_api_server(self) -> None:
        """Start the FastAPI server in a background thread."""
        try:
            import uvicorn
            from api.server import app as api_app, inject_services

            # Inject all services into the API
            inject_services(
                llm=self.llm,
                memory=self.memory,
                personality=self.personality,
                weather=self._weather,
                notes=self._notes,
                scheduler=self._scheduler,
                google=self._google,
                tool_dispatcher=self._tool_dispatcher,
                hyper=self._active_hyper_engine(),
            )

            config = uvicorn.Config(
                api_app,
                host=settings.API_HOST,
                port=settings.API_PORT,
                log_level="warning",
                loop="asyncio",
            )
            server = uvicorn.Server(config)

            self._api_server_thread = threading.Thread(
                target=server.run,
                daemon=True,
                name="API-Server",
            )
            self._api_server_thread.start()
            logger.info(
                f"API server started at http://{settings.API_HOST}:{settings.API_PORT}"
            )

        except Exception as e:
            logger.warning(f"API server failed to start: {e}")

    def _on_close(self):
        """Clean shutdown - save session before closing."""
        try:
            self._capture_layout_state()
        except Exception:
            pass
        try:
            if self._hotkey_daemon:
                self._hotkey_daemon.stop()
        except Exception:
            pass
        try:
            if self._system_tray:
                self._system_tray.stop()
        except Exception:
            pass
        try:
            if self._proactive_engine:
                self._proactive_engine.stop()
        except Exception:
            pass
        try:
            if self._clipboard_monitor:
                self._clipboard_monitor.stop()
        except Exception:
            pass
        try:
            if self._voice:
                self._voice.stop()
        except Exception:
            pass
        try:
            if self._scheduler:
                self._scheduler.stop()
        except Exception:
            pass
        try:
            if self._context_awareness:
                self._context_awareness.stop()
        except Exception:
            pass
        try:
            if self._router:
                self._router._loop.run_until_complete(self._router.close())
        except Exception:
            pass
        try:
            self.memory.end_session()
        except Exception:
            pass
        try:
            if self._command_center_refresh_job:
                self.after_cancel(self._command_center_refresh_job)
        except Exception:
            pass
        shutdown_hyper(self._hyper)
        self.destroy()
