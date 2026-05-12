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
        self.bind("<Escape>", lambda e: self._input_box.focus())

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
        main.grid_columnconfigure(1, minsize=280)

        self._build_chat_area(main)
        self._build_sidebar(main)

    def _build_chat_area(self, parent):
        """Scrollable chat message area."""
        chat_container = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg"],
            corner_radius=0,
        )
        chat_container.grid(row=0, column=0, sticky="nsew")
        chat_container.grid_rowconfigure(0, weight=1)
        chat_container.grid_columnconfigure(0, weight=1)

        # Scrollable frame for messages
        self._chat_scroll = ctk.CTkScrollableFrame(
            chat_container,
            fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["scrollbar"],
            scrollbar_button_hover_color=COLORS["border_light"],
            corner_radius=0,
        )
        self._chat_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self._chat_scroll.grid_columnconfigure(0, weight=1)

        self._message_row = 0  # Track row index for new messages

    def _build_sidebar(self, parent):
        """Right sidebar with memory status, session info, and quick actions."""
        sidebar = ctk.CTkFrame(
            parent,
            fg_color=COLORS["panel"],
            corner_radius=0,
            width=280,
        )
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(0, weight=1)

        # Separator line on left edge
        sep = ctk.CTkFrame(sidebar, width=1, fg_color=COLORS["border"])
        sep.place(x=0, y=0, relheight=1)

        # Scrollable content inside sidebar
        sidebar_scroll = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color=COLORS["scrollbar"],
            scrollbar_button_hover_color=COLORS["border_light"],
            corner_radius=0,
        )
        sidebar_scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        sidebar_scroll.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(sidebar_scroll, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=12)

        # --- Memory Status Section ---
        self._add_sidebar_section(content, "M E M O R Y")

        self._mem_conversation = self._add_sidebar_stat(
            content, "Conversation", "0 / 20 messages"
        )
        self._mem_memories = self._add_sidebar_stat(
            content, "Long-term", "0 memories"
        )
        self._mem_facts = self._add_sidebar_stat(
            content, "Known facts", "0"
        )
        self._mem_semantic = self._add_sidebar_stat(
            content, "Semantic", "Active"
        )

        self._add_divider(content)

        # --- Session Section ---
        self._add_sidebar_section(content, "S E S S I O N")

        self._sess_id = self._add_sidebar_stat(content, "ID", "-")
        self._sess_model = self._add_sidebar_stat(
            content, "Model", settings.OLLAMA_MODEL
        )
        self._sess_started = self._add_sidebar_stat(
            content, "Started", datetime.now().strftime("%H:%M")
        )

        self._add_divider(content)

        # --- Quick Actions ---
        self._add_sidebar_section(content, "Q U I C K  A C T I O N S")

        btn_cfg = dict(
            font=FONTS["sidebar"],
            height=30,
            fg_color=COLORS["card"],
            hover_color=COLORS["border_light"],
            text_color=COLORS["text"],
            corner_radius=6,
            anchor="w",
        )

        ctk.CTkButton(content, text="Clear Chat", command=self._cmd_clear, **btn_cfg).pack(fill="x", pady=(4, 2))
        ctk.CTkButton(content, text="Show Facts", command=self._cmd_show_facts, **btn_cfg).pack(fill="x", pady=2)
        ctk.CTkButton(content, text="Memory Status", command=self._cmd_memory_status, **btn_cfg).pack(fill="x", pady=2)
        ctk.CTkButton(content, text="Reminders", command=self._cmd_reminders, **btn_cfg).pack(fill="x", pady=2)
        ctk.CTkButton(content, text="My Tasks", command=self._cmd_tasks, **btn_cfg).pack(fill="x", pady=2)
        ctk.CTkButton(content, text="My Notes", command=self._cmd_notes, **btn_cfg).pack(fill="x", pady=2)

        self._add_divider(content)
        self._add_sidebar_section(content, "A G E N T S")
        self._agent_status = self._add_sidebar_stat(content, "Memory", "Active")
        self._add_sidebar_stat(content, "Planner", "Active")
        self._add_sidebar_stat(content, "Tasks", "Ready")

        self._add_divider(content)
        self._add_sidebar_section(content, "S E R V I C E S")
        self._svc_weather = self._add_sidebar_stat(content, "Weather", "Loading...")
        self._svc_tasks = self._add_sidebar_stat(content, "Tasks", "-")
        self._svc_notes = self._add_sidebar_stat(content, "Notes", "-")
        self._svc_scheduler = self._add_sidebar_stat(content, "Scheduler", "-")

        self._add_divider(content)

        # Version label at bottom
        ctk.CTkLabel(
            content,
            text="JOSEPH v1.0",
            font=("Segoe UI", 9),
            text_color=COLORS["text_muted"],
        ).pack(anchor="center", pady=(4, 8))

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
            text="Enter to send  ·  Shift+Enter for newline  ·  / for commands  ·  F2 for voice",
            font=("Segoe UI", 9),
            text_color=COLORS["text_muted"],
        ).pack(side="left")

        self._voice_state_label = ctk.CTkLabel(
            hint_row,
            text="",
            font=FONTS["body_sm"],
            text_color=COLORS["text_dim"],
        )
        self._voice_state_label.pack(side="right")

    def _on_enter_key(self, event):
        """Handle Enter key — send message (Shift+Enter is a newline, ignored here)."""
        self._send_message()
        return "break"

    # ------------------------------------------------------------------ #
    # Sidebar Helpers
    # ------------------------------------------------------------------ #

    def _add_sidebar_section(self, parent, title: str):
        """Add a section header to the sidebar."""
        ctk.CTkLabel(
            parent,
            text=title,
            font=FONTS["sidebar_h"],
            text_color=COLORS["accent"],
        ).pack(anchor="w", pady=(8, 4))

    def _add_sidebar_stat(self, parent, label: str, value: str) -> ctk.CTkLabel:
        """Add a label+value row to the sidebar. Returns the value label."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)

        ctk.CTkLabel(
            row,
            text=label,
            font=FONTS["sidebar"],
            text_color=COLORS["text_dim"],
            width=90,
            anchor="w",
        ).pack(side="left")

        val_label = ctk.CTkLabel(
            row,
            text=value,
            font=FONTS["sidebar"],
            text_color=COLORS["text"],
            anchor="w",
        )
        val_label.pack(side="left", fill="x", expand=True)
        return val_label

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
            padx=(16, 24) if not is_joseph else (16, 40),
            pady=(6, 2),
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

        return textbox

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
            # Add companion context
            companion_ctx = self.memory.get_companion_context()
            if companion_ctx:
                memory_context = companion_ctx + "\n\n" + memory_context

            system_prompt = get_system_prompt(
                user_name=settings.USER_NAME,
                memory_context=memory_context,
            )
            messages = self.memory.get_conversation_history()

            full_response = ""
            for chunk in self.llm.chat_stream(
                messages=messages,
                system_prompt=system_prompt,
            ):
                self._response_queue.put(("chunk", chunk))
                full_response += chunk

            self._response_queue.put(("done", None))

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
        """Try to handle user_text as an automation command."""
        try:
            from automation.command_router import CommandRouter

            if self._router is None:
                self._router = CommandRouter(llm=self.llm)
            else:
                self._router.set_llm(self.llm)

            # Always attach latest Phase 5 services
            self._router.attach_services(
                weather=self._weather,
                notes=self._notes,
                scheduler=self._scheduler,
                briefing=self._briefing,
            )

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

        # Schedule next poll
        self.after(30, self._poll_response_queue)

    def _finish_response(self, error: bool = False):
        """Called when streaming is complete."""
        # Hide typing indicator (in case it's still showing)
        self._hide_typing_indicator()

        # Lock the textbox
        if hasattr(self, "_active_textbox") and self._active_textbox:
            self._active_textbox.configure(state="disabled")

        # Save to memory
        if self._current_response and not error:
            from brain.personality import PersonalityEngine
            pe = PersonalityEngine()
            formatted = pe.format_response(self._current_response)
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
        """Refresh sidebar stats from current memory state."""
        try:
            status = self.memory.get_status()
            self._mem_conversation.configure(
                text=f"{status['short_term_messages']} / {status['short_term_limit']} messages"
            )
            self._mem_memories.configure(
                text=f"{status['long_term_memories']} memories"
            )
            self._mem_facts.configure(text=str(status["long_term_facts"]))
            self._mem_semantic.configure(
                text="Active" if status["semantic_search"] else "Offline",
                text_color=COLORS["success"] if status["semantic_search"] else COLORS["error"],
            )
            self._sess_id.configure(text=status["session_id"])
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
        """Initialize Phase 5 services in background."""
        import threading
        threading.Thread(target=self._load_phase5_services, daemon=True).start()

    def _load_phase5_services(self) -> None:
        """Load all Phase 5 services (runs on background thread)."""
        try:
            from brain.weather import WeatherService
            from brain.notes import NotesManager
            from brain.briefing import BriefingSystem
            from brain.context_awareness import ContextAwareness
            from scheduler.scheduler_manager import SchedulerManager

            self._weather = WeatherService()
            self._notes = NotesManager()
            self._context_awareness = ContextAwareness()
            self._context_awareness.start()

            # Scheduler with TTS callback
            def speak_reminder(msg: str):
                if self._voice and self._voice_enabled:
                    self._voice.tts.speak(msg, interrupt=True)
                # Also show in chat
                self.after(0, lambda: self._add_system_message(
                    f"Reminder: {msg}", COLORS["warning"]
                ))

            self._scheduler = SchedulerManager(on_reminder=speak_reminder)
            self._scheduler.start()

            # Briefing system
            self._briefing = BriefingSystem(
                weather_service=self._weather,
                notes_manager=self._notes,
                scheduler=self._scheduler,
                memory_manager=self.memory,
                tts=self._voice.tts if self._voice else None,
            )

            # Attach services to router
            if self._router:
                self._router.attach_services(
                    weather=self._weather,
                    notes=self._notes,
                    scheduler=self._scheduler,
                    briefing=self._briefing,
                )

            # Update sidebar
            self.after(0, self._update_phase5_sidebar)
            logger.info("Phase 5 services initialized")

        except Exception as e:
            logger.warning(f"Phase 5 init failed: {e}")

    def _init_voice(self) -> None:
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
        Checks automation first, then falls back to LLM.
        """
        logger.info(f"Voice input: '{text}'")

        # Show user message in UI
        self._response_queue.put(("voice_input", text))

        # Add to memory
        self.memory.add_user_message(text)

        # Try automation first (open YouTube, open Notepad, etc.)
        automation_result = self._try_automation(text)
        if automation_result:
            self.memory.add_assistant_message(automation_result)
            self._response_queue.put(("voice_response", automation_result))
            return automation_result

        # Regular chat - get LLM response
        try:
            from brain.prompts import get_system_prompt

            memory_context = self.memory.get_context_for_llm(query=text)
            system_prompt = get_system_prompt(
                user_name=settings.USER_NAME,
                memory_context=memory_context,
            )
            messages = self.memory.get_conversation_history()

            response = self.llm.chat(
                messages=messages,
                system_prompt=system_prompt,
            )

            if response:
                formatted = self.personality.format_response(response)
                self.memory.add_assistant_message(formatted)
                self._response_queue.put(("voice_response", formatted))
                return formatted

        except Exception as e:
            logger.error(f"Voice LLM error: {e}")
            error_msg = "Sorry, something went wrong."
            self._response_queue.put(("voice_response", error_msg))
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

    def _on_close(self):
        """Clean shutdown - save session before closing."""
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
