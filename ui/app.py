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
import queue
import asyncio
import threading
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from configs.settings import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Color Palette
# ------------------------------------------------------------------ #
COLORS = {
    "bg":           "#141414",
    "panel":        "#1e1e1e",
    "card":         "#252525",
    "card_user":    "#2c2c2c",
    "card_hover":   "#2f2f2f",
    "border":       "#333333",
    "border_light": "#404040",
    "accent":       "#4d9de0",
    "accent_hover": "#3d8dd0",
    "accent_dim":   "#2a5a8a",
    "text":         "#ececec",
    "text_dim":     "#7a7a7a",
    "text_muted":   "#555555",
    "text_joseph":  "#4d9de0",
    "text_user":    "#d0d0d0",
    "success":      "#3dba7a",
    "error":        "#d95f5f",
    "warning":      "#d4924a",
    "input_bg":     "#1a1a1a",
    "scrollbar":    "#333333",
    "thinking":     "#8b5cf6",
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

    def __init__(self, llm, memory, personality):
        super().__init__()

        self.llm = llm
        self.memory = memory
        self.personality = personality

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

        self._setup_window()
        self._build_ui()
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
        self.geometry("1140x740")
        self.minsize(820, 580)
        self.configure(fg_color=COLORS["bg"])

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1140) // 2
        y = (self.winfo_screenheight() - 740) // 2
        self.geometry(f"1140x740+{x}+{y}")

        # Handle close button
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Hotkeys
        self.bind("<F2>", lambda e: self._toggle_voice())
        self.bind("<Escape>", self._on_escape_key)

        # Grid layout: header row + main row + input row
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

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
            fg_color=COLORS["panel"],
            corner_radius=0,
        )
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        # Thin accent line at bottom of header
        accent_line = ctk.CTkFrame(header, height=1, fg_color=COLORS["accent"])
        accent_line.place(relx=0, rely=1.0, anchor="sw", relwidth=1.0)

        # Left: Logo + name
        logo_frame = ctk.CTkFrame(header, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=0, sticky="w")

        ctk.CTkLabel(
            logo_frame,
            text="◈",
            font=("Segoe UI", 18),
            text_color=COLORS["accent"],
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            logo_frame,
            text="JOSEPH",
            font=FONTS["title"],
            text_color=COLORS["text"],
        ).pack(side="left")

        ctk.CTkLabel(
            logo_frame,
            text="Personal AI Assistant",
            font=FONTS["subtitle"],
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(10, 0))

        # Right: Status indicator + clock
        self._status_frame = ctk.CTkFrame(header, fg_color="transparent")
        self._status_frame.grid(row=0, column=2, padx=20, pady=0, sticky="e")

        # Live clock
        self._clock_label = ctk.CTkLabel(
            self._status_frame,
            text=datetime.now().strftime("%H:%M"),
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["text_dim"],
        )
        self._clock_label.pack(side="right", padx=(16, 0))
        self._update_clock()

        # Status label
        self._status_label = ctk.CTkLabel(
            self._status_frame,
            text=f"Connected  {settings.OLLAMA_MODEL}",
            font=FONTS["body_sm"],
            text_color=COLORS["text_dim"],
        )
        self._status_label.pack(side="right", padx=(0, 6))

        # Pulsing status dot
        self._status_dot = ctk.CTkLabel(
            self._status_frame,
            text="●",
            font=("Segoe UI", 12),
            text_color=COLORS["success"],
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
            color = COLORS["success"] if self._dot_bright else "#1e6640"
            self._status_dot.configure(text_color=color)
            self._dot_bright = not self._dot_bright
        self.after(1200, self._pulse_dot)

    def _build_main_area(self):
        """Main content area: chat on left, sidebar on right."""
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, minsize=260)

        self._build_chat_area(main)
        self._build_sidebar(main)

    def _build_chat_area(self, parent):
        """Scrollable chat message area with search bar."""
        chat_container = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg"],
            corner_radius=0,
        )
        chat_container.grid(row=0, column=0, sticky="nsew")
        chat_container.grid_rowconfigure(1, weight=1)
        chat_container.grid_columnconfigure(0, weight=1)

        # ── Search bar ───────────────────────────────────────
        search_bar = ctk.CTkFrame(chat_container, fg_color=COLORS["panel"], height=38, corner_radius=0)
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
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["text_muted"],
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
            fg_color=COLORS["card"],
            hover_color=COLORS["border_light"],
            text_color=COLORS["text"],
            corner_radius=5,
            command=self._do_search,
        ).grid(row=0, column=1)

        # Bottom border under search bar
        ctk.CTkFrame(chat_container, height=1, fg_color=COLORS["border"]).grid(
            row=0, column=0, sticky="ews", pady=(37, 0)
        )

        # ── Scrollable messages ──────────────────────────────
        self._chat_scroll = ctk.CTkScrollableFrame(
            chat_container,
            fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["scrollbar"],
            scrollbar_button_hover_color=COLORS["border_light"],
            corner_radius=0,
        )
        self._chat_scroll.grid(row=1, column=0, sticky="nsew")
        self._chat_scroll.grid_columnconfigure(0, weight=1)

        self._message_row = 0

    def _build_sidebar(self, parent):
        """Right sidebar — clean, minimal, functional."""
        sidebar = ctk.CTkFrame(
            parent,
            fg_color=COLORS["panel"],
            corner_radius=0,
            width=260,
        )
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(0, weight=1)

        # Left border
        ctk.CTkFrame(sidebar, width=1, fg_color=COLORS["border"]).place(
            x=0, y=0, relheight=1
        )

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color=COLORS["scrollbar"],
            scrollbar_button_hover_color=COLORS["border_light"],
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
            fg_color=COLORS["card"],
            hover_color=COLORS["border_light"],
            text_color=COLORS["text"],
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
            text_color=COLORS["text_muted"],
        ).pack(anchor="center", pady=(2, 6))

    def _build_input_bar(self):
        """Bottom input bar with text field, voice button, and send button."""
        input_bar = ctk.CTkFrame(
            self,
            height=80,
            fg_color=COLORS["panel"],
            corner_radius=0,
        )
        input_bar.grid(row=2, column=0, sticky="ew")
        input_bar.grid_columnconfigure(0, weight=1)
        input_bar.grid_propagate(False)

        # Top border line (slightly lighter for subtle gradient feel)
        border_top = ctk.CTkFrame(input_bar, height=2, fg_color=COLORS["border_light"])
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
            fg_color=COLORS["card"],
            hover_color=COLORS["border_light"],
            text_color=COLORS["text_dim"],
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
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["text_muted"],
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
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
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
            text_color=COLORS["text_muted"],
        ).pack(side="left")

        # Voice speed slider
        speed_frame = ctk.CTkFrame(hint_row, fg_color="transparent")
        speed_frame.pack(side="right")

        ctk.CTkLabel(
            speed_frame,
            text="Speed",
            font=("Segoe UI", 9),
            text_color=COLORS["text_muted"],
        ).pack(side="left", padx=(0, 4))

        self._speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=0.6,
            to=1.6,
            number_of_steps=10,
            width=80,
            height=14,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent_dim"],
            fg_color=COLORS["border"],
            command=self._on_speed_change,
        )
        self._speed_slider.set(1.0)
        self._speed_slider.pack(side="left")

        self._voice_state_label = ctk.CTkLabel(
            hint_row,
            text="",
            font=FONTS["body_sm"],
            text_color=COLORS["text_dim"],
        )
        # voice_state_label goes between hint and speed
        self._voice_state_label.pack(side="left", padx=(12, 0))

    def _on_escape_key(self, event) -> None:
        """Escape: stop speech if speaking, otherwise focus input."""
        if self._voice and self._voice.tts.is_speaking:
            self._voice.tts.stop_speaking()
            self._set_status(f"Connected  {settings.OLLAMA_MODEL}", COLORS["success"])
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
            text_color=COLORS["accent"],
        ).pack(anchor="w", pady=(8, 3))

    def _add_sidebar_stat(self, parent, label: str, value: str) -> ctk.CTkLabel:
        """Add a label+value row. Returns the value label for updates."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=0)

        ctk.CTkLabel(
            row,
            text=label,
            font=FONTS["sidebar"],
            text_color=COLORS["text_dim"],
            width=80,
            anchor="w",
        ).pack(side="left")

        val = ctk.CTkLabel(
            row,
            text=value,
            font=FONTS["sidebar"],
            text_color=COLORS["text"],
            anchor="w",
        )
        val.pack(side="left", fill="x", expand=True)
        return val

    def _add_divider(self, parent):
        """Add a horizontal divider line."""
        ctk.CTkFrame(
            parent,
            height=1,
            fg_color=COLORS["border"],
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
        name_color = COLORS["text_joseph"] if is_joseph else COLORS["text_user"]

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
            text_color=COLORS["text_dim"],
        ).pack(side="left")

        # Bubble wrapper (for accent bar on Joseph messages)
        if is_joseph:
            wrapper = ctk.CTkFrame(bubble_row, fg_color="transparent")
            wrapper.pack(fill="x")
            wrapper.grid_columnconfigure(1, weight=1)

            # Left accent bar (3px, accent color)
            accent_bar = ctk.CTkFrame(wrapper, width=3, fg_color=COLORS["accent"], corner_radius=2)
            accent_bar.grid(row=0, column=0, sticky="ns", padx=(0, 8))

            bubble_parent = ctk.CTkFrame(wrapper, fg_color="transparent")
            bubble_parent.grid(row=0, column=1, sticky="ew")
            bubble_parent.grid_columnconfigure(0, weight=1)
        else:
            bubble_parent = bubble_row

        # Message bubble
        bubble_color = COLORS["card"] if is_joseph else COLORS["card_user"]

        # Calculate initial height based on text length
        lines = max(2, text.count("\n") + len(text) // 75 + 1)
        height = min(max(lines * 22, 48), 420)

        textbox = ctk.CTkTextbox(
            bubble_parent,
            font=FONTS["body"],
            fg_color=bubble_color,
            text_color=COLORS["text"],
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
            color = COLORS["success"] if value > 0 else COLORS["error"]
            # Briefly flash the button
            self.after(100, lambda: None)  # Small delay for feel
            logger.debug(f"Response rated: {value}")

        ctk.CTkButton(
            btn_row,
            text="👍",
            font=("Segoe UI", 11),
            width=28, height=22,
            fg_color="transparent",
            hover_color=COLORS["card"],
            text_color=COLORS["text_dim"],
            corner_radius=4,
            command=lambda: rate(1),
        ).pack(side="left", padx=(0, 2))

        ctk.CTkButton(
            btn_row,
            text="👎",
            font=("Segoe UI", 11),
            width=28, height=22,
            fg_color="transparent",
            hover_color=COLORS["card"],
            text_color=COLORS["text_dim"],
            corner_radius=4,
            command=lambda: rate(-1),
        ).pack(side="left")

    def _add_system_message(self, text: str, color: Optional[str] = None, icon: Optional[str] = None):
        """Add a centered system/status message with optional icon."""
        msg_color = color or COLORS["text_dim"]

        # Auto-pick icon based on color if not provided
        if icon is None:
            if color == COLORS["success"]:
                icon = "✓"
            elif color == COLORS["error"]:
                icon = "✗"
            elif color == COLORS["warning"]:
                icon = "⚠"
            elif color == COLORS["accent"]:
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
            text_color=COLORS["thinking"],
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
            self._add_system_message(f"Saved to memory: {arg}", COLORS["success"])
            self._update_sidebar()
            self._scroll_to_bottom()

        elif cmd == "help":
            help_text = (
                "Commands: /clear  /memory  /facts  /remember <text>\n"
                "          /reminders  /tasks  /notes  /quit\n"
                "Or just type normally to chat. Press F2 for voice."
            )
            self._add_system_message(help_text, COLORS["accent"])
            self._scroll_to_bottom()

        else:
            self._add_system_message(
                f"Unknown command: /{cmd}  -  type /help for commands",
                COLORS["warning"],
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
        self._set_status("Thinking...", COLORS["warning"])

        # Show typing indicator
        self._show_typing_indicator()
        self._scroll_to_bottom()

        # Create the response bubble (empty, will be filled by streaming)
        # It will be created when first chunk arrives (via _hide_typing_indicator)
        self._active_textbox = None
        self._first_chunk = True

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

            # Check single automation command
            automation_result = self._try_automation(user_text)
            if automation_result:
                self._response_queue.put(("automation_done", automation_result))
                # Run memory agent in background
                if self._memory_agent:
                    import threading
                    threading.Thread(
                        target=self._memory_agent.process_exchange,
                        args=(user_text, automation_result),
                        daemon=True,
                    ).start()
                return

            # Regular chat - stream from LLM
            from brain.prompts import get_system_prompt

            memory_context = self.memory.get_context_for_llm(query=user_text)
            companion_ctx = self.memory.get_companion_context()
            if companion_ctx:
                memory_context = companion_ctx + "\n\n" + memory_context

            # Phase 7 — advanced personality modifier
            personality_modifier = ""
            if self._advanced_personality:
                self._advanced_personality.update(user_text)
                personality_modifier = self._advanced_personality.get_system_modifier()

            system_prompt = get_system_prompt(
                user_name=settings.USER_NAME,
                memory_context=memory_context,
            )
            if personality_modifier:
                system_prompt += f"\n\nCurrent context: {personality_modifier}"

            # Add personality learning style
            if self._personality_learning:
                style = self._personality_learning.get_style_modifier()
                if style:
                    system_prompt += f"\n\nLearned preferences: {style}"
            messages = self.memory.get_conversation_history()

            full_response = ""
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

            self._response_queue.put(("done", None))

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

            # Run memory agent in background
            if self._memory_agent and full_response:
                import threading
                threading.Thread(
                    target=self._memory_agent.process_exchange,
                    args=(user_text, full_response),
                    daemon=True,
                ).start()

        except Exception as e:
            logger.error(f"LLM worker error: {e}")
            self._response_queue.put(("error", str(e)))

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

            # Try LLM tool dispatcher first
            response, was_automated = self._tool_dispatcher.dispatch(user_text)
            if was_automated and response:
                return response

            # Fall back to regex router for speed on obvious commands
            response, was_automated = self._router.handle_sync(user_text)
            if was_automated and response:
                return response

        except Exception as e:
            logger.debug(f"Automation check error: {e}")

        return None

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
            self.memory.add_assistant_message(formatted)

            # Background fact extraction
            threading.Thread(
                target=self._background_memory_tasks,
                daemon=True,
            ).start()

        # Re-enable input
        self._is_responding = False
        self._send_btn.configure(state="normal", text="Send  ▶")
        self._set_status(f"Connected  {settings.OLLAMA_MODEL}", COLORS["success"])
        self._update_sidebar()
        self._input_box.focus()

    def _background_memory_tasks(self):
        """Run memory extraction in background - never blocks UI."""
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
            sem_color = COLORS["success"] if status["semantic_search"] else COLORS["error"]
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
        self._add_system_message("Conversation cleared", COLORS["text_dim"])
        self._update_sidebar()
        self._scroll_to_bottom()

    def _cmd_show_facts(self):
        """Show stored user facts in chat."""
        facts = self.memory.long_term.get_all_facts()
        if not facts:
            self._add_system_message("No facts stored yet.", COLORS["text_dim"])
        else:
            lines = "\n".join([f"  {k}: {v}" for k, v in facts.items()])
            self._add_system_message(f"Known facts:\n{lines}", COLORS["accent"])
        self._scroll_to_bottom()

    def _cmd_memory_status(self):
        """Show memory status in chat."""
        status_text = self.memory.format_status()
        self._add_system_message(status_text, COLORS["accent"])
        self._scroll_to_bottom()

    def _cmd_reminders(self):
        """Show scheduled reminders."""
        if self._scheduler:
            text = self._scheduler.format_jobs()
        else:
            text = "Scheduler not ready yet."
        self._add_system_message(text, COLORS["accent"])
        self._scroll_to_bottom()

    def _cmd_tasks(self):
        """Show pending tasks."""
        if self._notes:
            tasks = self._notes.get_pending_tasks()
            text = self._notes.format_tasks(tasks)
        else:
            text = "Tasks not ready yet."
        self._add_system_message(text, COLORS["accent"])
        self._scroll_to_bottom()

    def _cmd_notes(self):
        """Show recent notes."""
        if self._notes:
            notes = self._notes.get_recent_notes(limit=10)
            text = self._notes.format_notes(notes)
        else:
            text = "Notes not ready yet."
        self._add_system_message(text, COLORS["accent"])
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
                COLORS["text_dim"],
            )
            self._scroll_to_bottom()
            return

        if self._conversation_search:
            results = self._conversation_search.search(query)
            text = self._conversation_search.format_results(results)
        else:
            text = "Search not available."
        self._add_system_message(text, COLORS["accent"])
        self._scroll_to_bottom()

    def _cmd_focus(self, duration: int = 25) -> None:
        """Start a focus session."""
        if self._focus_mode:
            result = self._focus_mode.start(duration_minutes=duration)
            self._add_message_bubble("assistant", result)
        else:
            self._add_system_message("Focus mode not ready.", COLORS["text_dim"])
        self._scroll_to_bottom()

    def _cmd_focus_status(self) -> None:
        """Show focus session status."""
        if self._focus_mode:
            text = self._focus_mode.status()
            self._add_system_message(text, COLORS["accent"])
        self._scroll_to_bottom()

    def _cmd_emails(self) -> None:
        """Show email triage."""
        def do_triage():
            if self._email_triage:
                text = self._email_triage.get_morning_summary()
            else:
                text = "Email triage not available. Set up Google integration first."
            self.after(0, lambda: self._add_system_message(text, COLORS["accent"]))
            self.after(0, self._scroll_to_bottom)

        import threading
        threading.Thread(target=do_triage, daemon=True).start()

    def _cmd_spotify(self, action: str = "", query: str = "") -> None:
        """Control Spotify."""
        if not self._spotify:
            self._add_system_message(
                "Spotify not configured. Add SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET to .env",
                COLORS["text_dim"],
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

        self._add_system_message(result, COLORS["accent"])
        self._scroll_to_bottom()

    # ------------------------------------------------------------------ #
    # Session Lifecycle
    # ------------------------------------------------------------------ #

    def _start_session(self):
        """Initialize session and show greeting."""
        self.memory.start_session()
        self._update_sidebar()
        self._sess_started.configure(text=datetime.now().strftime("%H:%M"))

        # Show greeting on a slight delay so UI renders first
        self.after(400, self._show_greeting)
        self.after(1500, self._init_agents)
        self.after(2000, self._init_phase5)

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
                    text_color=COLORS["success"],
                    fg_color=COLORS["card"],
                )
                self._voice_state_label.configure(
                    text=f"Say '{settings.WAKE_WORD}'...",
                    text_color=COLORS["text_dim"],
                )
                logger.info("Voice system started from UI")
            else:
                self._voice_state_label.configure(
                    text="Voice unavailable - text only",
                    text_color=COLORS["text_dim"],
                )

        except Exception as e:
            logger.warning(f"Voice init failed: {e}")
            try:
                self._voice_state_label.configure(
                    text="Voice unavailable",
                    text_color=COLORS["text_dim"],
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
                    f"Reminder: {msg}", COLORS["warning"]
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
            suggestion, COLORS["text_dim"]
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
            f"💡 {message}", COLORS["accent"]
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
            COLORS["thinking"],
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
                    text_color=COLORS["success"],
                    fg_color=COLORS["card"],
                )
                self._voice_state_label.configure(
                    text=f"Listening for '{settings.WAKE_WORD}'...",
                    text_color=COLORS["text_dim"],
                )
                logger.info("Voice system started from UI")
            else:
                self._voice_state_label.configure(
                    text="Voice unavailable - text only",
                    text_color=COLORS["text_dim"],
                )

        except Exception as e:
            logger.warning(f"Voice init failed: {e}")
            self._voice_state_label.configure(
                text="Voice unavailable",
                text_color=COLORS["text_dim"],
            )

    def _toggle_voice(self) -> None:
        """Toggle push-to-talk listening."""
        if not self._voice or not self._voice_enabled:
            self._add_system_message(
                "Voice system not available. Check microphone.",
                COLORS["warning"],
            )
            return

        from voice.voice_controller import VoiceState

        if self._voice.state == VoiceState.IDLE:
            # Trigger push-to-talk
            self._voice_btn.configure(
                fg_color=COLORS["error"],
                text_color="#ffffff",
            )
            self._voice_state_label.configure(
                text="Listening... speak now",
                text_color=COLORS["error"],
            )
            self._set_status("Listening...", COLORS["error"])
            self._voice.push_to_talk()
        else:
            self._add_system_message(
                "Already listening or processing...",
                COLORS["text_dim"],
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
            system_prompt = get_system_prompt(
                user_name=settings.USER_NAME,
                memory_context=memory_context,
            )
            messages = self.memory.get_conversation_history()

            # Get the stream iterator
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
                self.memory.add_assistant_message(formatted)
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
            VoiceState.IDLE: (f"Say '{settings.WAKE_WORD}'...", COLORS["text_dim"]),
            VoiceState.WAKE_DETECTED: ("Wake word detected!", COLORS["accent"]),
            VoiceState.LISTENING: ("Listening...", COLORS["error"]),
            VoiceState.PROCESSING: ("Processing...", COLORS["warning"]),
            VoiceState.SPEAKING: ("Speaking...", COLORS["success"]),
            VoiceState.DISABLED: ("Voice disabled", COLORS["text_dim"]),
        }

        text, color = state_display.get(state, ("", COLORS["text_dim"]))

        # Update UI on main thread
        self.after(0, lambda: self._voice_state_label.configure(
            text=text, text_color=color
        ))

        # Reset voice button color when idle
        if state == VoiceState.IDLE:
            self.after(0, lambda: self._voice_btn.configure(
                fg_color=COLORS["card"],
                text_color=COLORS["success"],
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
        self.destroy()
