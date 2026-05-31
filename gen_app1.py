import os, shutil
path = r'C:\Users\Grayson\Desktop\Joseph\ui\app.py'
backup = path + '.bak'
if not os.path.exists(backup):
    shutil.copy2(path, backup)
    print(f"Backup: {backup}")

content = '''"""
ui/app.py
---------
JOSEPH Desktop UI - Phase 4: Responsive, themed, polished.
"""

import logging
import json
import os
import queue
import threading
import time
import webbrowser
import re
from datetime import datetime
from typing import Optional
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
import tkinter as tk

from configs.settings import settings
from hyper.bootstrap import (
    enhance_response, finalize_hyper_turn,
    get_context_enhancement, prepare_hyper_turn, shutdown_hyper,
)

logger = logging.getLogger(__name__)

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
    "title": ("Segoe UI", 16, "bold"),
    "subtitle": ("Segoe UI", 10),
    "body": ("Segoe UI", 13),
    "body_sm": ("Segoe UI", 11),
    "mono": ("Consolas", 11),
    "name": ("Segoe UI Semibold", 11, "bold"),
    "time": ("Segoe UI", 9),
    "sidebar": ("Segoe UI", 10),
    "sidebar_h": ("Segoe UI", 9, "bold"),
    "input": ("Segoe UI", 13),
    "btn": ("Segoe UI Semibold", 12, "bold"),
}


class JosephApp(ctk.CTk):
    """Main application window - Phase 4."""

    NAV_PAGES = [
        "Chat", "Dashboard", "Knowledge Graph", "Memory",
        "Agents", "Diagnostics", "Improvements", "Settings",
    ]

    CONTEXT_SECTIONS = [
        ("Current Turn", "turn"), ("Agent Activity", "agents"),
        ("Research", "research"), ("Memory", "memory"),
        ("Diagnostics", "diagnostics"),
    ]

    def __init__(self, llm, memory, personality, hyper_engine=None):
        super().__init__()
        self.llm = llm
        self.memory = memory
        self.personality = personality
        self._hyper = hyper_engine

        self._response_queue = queue.Queue()
        self._is_responding = False
        self._current_response = ""

        # Lazy services
        self._voice = None
        self._voice_enabled = False
        self._router = None
        self._tool_dispatcher = None
        self._memory_agent = None
        self._task_agent = None
        self._planner = None
        self._weather = None
        self._notes = None
        self._scheduler = None
        self._briefing = None
        self._context_awareness = None
        self._vision = None
        self._file_manager = None
        self._advanced_personality = None
        self._autonomous_agent = None
        self._google = None
        self._hotkey_daemon = None
        self._api_server_thread = None
        self._notifications = None
        self._system_tray = None
        self._proactive_engine = None
        self._multi_model_router = None
        self._plugin_system = None
        self._conversation_search = None
        self._clipboard_monitor = None
        self._custom_commands = None
        self._personality_learning = None
        self._spotify = None
        self._focus_mode = None
        self._email_triage = None
        self._pe_cache = None

        self._hyper_turn_packet = {}
        self._pending_attachments = []
        self._active_textbox = None
        self._first_chunk = True
        self._typing_frame = None
        self._typing_label = None
        self._typing_timer = None
        self._message_row = 0
        self._sidebar_cache = {}
        self._graph_zoom = 1.0
        self._graph_positions = {}
        self._selected_graph_node = None
        self._selected_memory_id = None
        self._selected_improvement = None
        self._improvement_decisions = {}
        self._last_turn_summary = {}
        self._page_frames = {}
        self._nav_buttons = {}
        self._active_page = "Chat"
        self._context_cards = {}
        self._dashboard_boxes = {}
        self._diagnostics_boxes = {}
        self._memory_memory_rows = []
        self._agents_flow_frames = {}
        self._setting_vars = {}
        self._graph_hitboxes = {}
        self._graph_canvas = None
        self._graph_detail_box = None
        self._graph_search_box = None
        self._command_center_refresh_job = None
        self._improvement_list = None
        self._improvement_summary_box = None
        self._chat_scroll = None
        self._search_box = None
        self._input_box = None
        self._send_btn = None
        self._voice_btn = None
        self._speed_slider = None
        self._voice_state_label = None
        self._status_label = None
        self._status_dot = None
        self._clock_label = None
        self._nav_toggle_button = None
        self._context_toggle_button = None
        self._nav_status_label = None
        self._nav_buttons_frame = None
        self._context_stack = None
        self._turn_detail_box = None
        self._turn_agents_label = None
        self._turn_sources_label = None
        self._turn_memories_label = None
        self._turn_reasoning_label = None
        self._turn_detail_toggle = None
        self._memory_list_frame = None
        self._memory_detail_box = None
        self._memory_search_box = None
        self._agents_box = None
        self._sidebar_frame = None
        self._agent_flow_container = None
        self._agent_status_labels = {}
        self._memory_sort_var = None
        self._memory_cat_var = None

        # Layout state
        self._layout_state = self._load_layout_state()
        self._nav_visible = self._layout_state.get("nav_visible", True)
        self._context_visible = self._layout_state.get("context_visible", True)
        self._nav_width = int(self._layout_state.get("nav_width", 220))
        self._context_width = int(self._layout_state.get("context_width", 300))
        self._theme_name = self._layout_state.get("theme_mode", "dark")
        self._theme_name = self._normalize_theme_mode(self._theme_name)
        self._layout_density = self._layout_state.get("density", "comfortable")
        self._font_scale = float(self._layout_state.get("font_scale", 1.0))
        self._ui_settings = {
            "hyper_enabled": bool(hyper_engine),
            "research_sources": 3,
            "refresh_interval_ms": 2500,
            "density": "comfortable",
            "animations": True,
            "compact_panels": False,
        }
        self.colors = dict(THEMES[self._theme_name])
        self._graph_pan_offset_x = 0
        self._graph_pan_offset_y = 0
        self._graph_pan_start_pos = None
        self._graph_drag_start = None

        ctk.set_appearance_mode(self._theme_name)
        ctk.set_default_color_theme("blue")

        self._setup_window()
        self._build_ui()
        self._start_session()
        self._poll_response_queue()
        self.after(1000, self._init_voice)
'''

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"Wrote {len(content)} bytes")
