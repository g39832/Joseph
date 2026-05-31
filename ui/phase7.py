"""
ui/phase7.py
---------------
Phase 7 UI widgets for JOSEPH.

Provides customtkinter frames for:
- Activity Timeline: chronological log of actions
- Insight Dashboard: topic breakdown and learning insights
- Research Workspace: browse/search research entries
- Suggestions Panel: follow-up recommendations and ambient suggestions

Each widget is independent and can be embedded in a tab view.
"""

import logging
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

logger = logging.getLogger(__name__)

# Color scheme
COLORS = {
    "tool": "#4A90D9",
    "command": "#7B68EE",
    "memory": "#2E8B57",
    "decision": "#DAA520",
    "chat": "#666666",
    "error": "#DC143C",
    "system": "#4682B4",
    "suggestion": "#9370DB",
}

# Icons (unicode)
ICONS = {
    "tool": "\U0001F527",
    "command": "\u2328",
    "memory": "\U0001F4BE",
    "decision": "\u2699",
    "chat": "\U0001F4AC",
    "error": "\u26A0",
    "system": "\U0001F4E1",
    "suggestion": "\U0001F4A1",
}


def _color_for(entry_type: str) -> str:
    return COLORS.get(entry_type, "#888888")


def _icon_for(entry_type: str) -> str:
    return ICONS.get(entry_type, "\u2022")


def _tags_display(tags: list[str]) -> str:
    if not tags:
        return ""
    return " " + " ".join(f"[{t}]" for t in tags)


class ActivityTimelineFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Scrollable activity log display."""

    def __init__(self, master, tracker=None, **kwargs):
        super().__init__(master, **kwargs)
        self._tracker = tracker
        self._labels: list = []
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Activity Timeline",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        self._stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._stats_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._total_label = ctk.CTkLabel(
            self._stats_frame, text="Total: 0", font=("Segoe UI", 11)
        )
        self._total_label.pack(side="left", padx=(0, 16))

        self._filter_var = tk.StringVar(value="all")
        self._filter_menu = ctk.CTkOptionMenu(
            self._stats_frame,
            values=["all", "chat", "tool", "command", "memory", "decision"],
            variable=self._filter_var,
            command=self._on_filter,
            width=100,
        )
        self._filter_menu.pack(side="right")

        self._canvas_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._canvas_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._refresh()

    def _on_filter(self, _choice=None):
        self._refresh()

    def refresh(self, tracker=None):
        if tracker:
            self._tracker = tracker
        self._refresh()

    def _refresh(self):
        for w in self._canvas_frame.winfo_children():
            w.destroy()
        self._labels.clear()

        if not self._tracker:
            ctk.CTkLabel(
                self._canvas_frame,
                text="No activity tracker connected.",
                font=("Segoe UI", 11),
                text_color="gray",
            ).pack(pady=20)
            return

        entries = self._tracker.recent(100)
        selected = self._filter_var.get()
        if selected != "all":
            entries = [
                e for e in entries if e.entry_type == selected
            ]

        self._total_label.configure(text=f"Total: {len(entries)}")

        if not entries:
            ctk.CTkLabel(
                self._canvas_frame,
                text="No matching entries.",
                font=("Segoe UI", 11),
                text_color="gray",
            ).pack(pady=20)
            return

        for entry in reversed(entries):
            color = _color_for(entry.entry_type)
            icon = _icon_for(entry.entry_type)

            frame = ctk.CTkFrame(
                self._canvas_frame, fg_color="transparent"
            )
            frame.pack(fill="x", pady=1)

            time_str = entry.timestamp[11:19] if entry.timestamp else ""
            info = (
                f"{icon} [{time_str}] "
                f"{entry.entry_type.upper()}"
            )
            if entry.category != "general":
                info += f" ({entry.category})"

            header = ctk.CTkLabel(
                frame,
                text=info,
                font=("Segoe UI", 10, "bold"),
                text_color=color,
                anchor="w",
            )
            header.pack(fill="x", padx=4)

            summary = ctk.CTkLabel(
                frame,
                text=entry.summary[:120],
                font=("Segoe UI", 10),
                anchor="w",
                wraplength=500,
            )
            summary.pack(fill="x", padx=(16, 4))

            if entry.detail:
                detail = ctk.CTkLabel(
                    frame,
                    text=entry.detail[:200],
                    font=("Segoe UI", 9),
                    text_color="gray",
                    anchor="w",
                    wraplength=480,
                )
                detail.pack(fill="x", padx=(24, 4))

            if entry.duration_ms > 0:
                dur = ctk.CTkLabel(
                    frame,
                    text=f"{entry.duration_ms:.0f}ms",
                    font=("Segoe UI", 8),
                    text_color="#666",
                    anchor="e",
                )
                dur.pack(anchor="e", padx=8)


class InsightDashboardFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Displays topic breakdown and learning insights."""

    def __init__(self, master, insight_engine=None, **kwargs):
        super().__init__(master, **kwargs)
        self._engine = insight_engine
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Insight Dashboard",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            self,
            text="Topic breakdown and learning insights from your activity.",
            font=("Segoe UI", 10),
            text_color="gray",
            anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 8))

        self._topics_frame = ctk.CTkFrame(self)
        self._topics_frame.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(
            self._topics_frame,
            text="Topics Explored",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 4))

        self._topic_container = ctk.CTkFrame(
            self._topics_frame, fg_color="transparent"
        )
        self._topic_container.pack(fill="x", padx=8, pady=(0, 8))

        self._insights_frame = ctk.CTkFrame(self)
        self._insights_frame.pack(fill="both", expand=True, padx=8, pady=4)

        ctk.CTkLabel(
            self._insights_frame,
            text="Insights",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 4))

        self._insight_container = ctk.CTkFrame(
            self._insights_frame, fg_color="transparent"
        )
        self._insight_container.pack(
            fill="both", expand=True, padx=8, pady=(0, 8)
        )

        self._refresh_btn = ctk.CTkButton(
            self,
            text="Refresh Insights",
            command=self._refresh,
            width=140,
        )
        self._refresh_btn.pack(pady=8)

    def refresh(self, engine=None):
        if engine:
            self._engine = engine
        self._refresh()

    def _refresh(self):
        # Clear topic container
        for w in self._topic_container.winfo_children():
            w.destroy()

        # Clear insight container
        for w in self._insight_container.winfo_children():
            w.destroy()

        if not self._engine:
            ctk.CTkLabel(
                self._topic_container,
                text="No insight engine connected.",
                text_color="gray",
            ).pack()
            return

        # Topics
        topics = self._engine.get_topic_breakdown()
        if topics:
            max_count = max(topics.values()) if topics else 1
            for topic, count in topics.items():
                bar_frame = ctk.CTkFrame(
                    self._topic_container, fg_color="transparent"
                )
                bar_frame.pack(fill="x", pady=1)

                label = ctk.CTkLabel(
                    bar_frame,
                    text=f"{topic.title()}: {count}",
                    font=("Segoe UI", 10),
                    width=150,
                    anchor="w",
                )
                label.pack(side="left", padx=4)

                bar_width = max(
                    20, int((count / max_count) * 200)
                )
                bar = ctk.CTkProgressBar(
                    bar_frame, width=bar_width, height=12
                )
                bar.set(count / max_count if max_count else 0)
                bar.pack(side="left", padx=4)
        else:
            ctk.CTkLabel(
                self._topic_container,
                text="No topics tracked yet.",
                text_color="gray",
            ).pack()

        # Insights
        insights = self._engine.get_insights()
        if insights:
            for insight in insights[-10:]:
                frame = ctk.CTkFrame(
                    self._insight_container, fg_color="transparent"
                )
                frame.pack(fill="x", pady=2)

                ctk.CTkLabel(
                    frame,
                    text=insight.title,
                    font=("Segoe UI", 10, "bold"),
                    anchor="w",
                ).pack(fill="x", padx=4)

                ctk.CTkLabel(
                    frame,
                    text=insight.detail,
                    font=("Segoe UI", 9),
                    text_color="#CCC",
                    anchor="w",
                    wraplength=450,
                ).pack(fill="x", padx=(12, 4))
        else:
            ctk.CTkLabel(
                self._insight_container,
                text="No insights generated yet. Insights appear after "
                "enough activity is tracked.",
                text_color="gray",
                wraplength=400,
            ).pack(pady=10)


class ResearchWorkspaceFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Browse and search research entries."""

    def __init__(self, master, research_workspace=None, **kwargs):
        super().__init__(master, **kwargs)
        self._workspace = research_workspace
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Research Workspace",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        # Search bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._search_var = tk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search research entries...",
            textvariable=self._search_var,
            width=300,
        )
        self._search_entry.pack(side="left", padx=(0, 8))

        self._search_btn = ctk.CTkButton(
            search_frame,
            text="Search",
            command=self._on_search,
            width=80,
        )
        self._search_btn.pack(side="left", padx=(0, 4))

        self._clear_btn = ctk.CTkButton(
            search_frame,
            text="Clear",
            command=self._refresh,
            width=60,
            fg_color="#555",
        )
        self._clear_btn.pack(side="left")

        # Stats
        self._stats_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 10), text_color="gray",
            anchor="w",
        )
        self._stats_label.pack(fill="x", padx=8, pady=(0, 4))

        # Results container
        self._results_frame = ctk.CTkFrame(
            self, fg_color="transparent"
        )
        self._results_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._refresh()

    def _on_search(self):
        query = self._search_var.get().strip()
        self._refresh(query)

    def refresh(self, workspace=None):
        if workspace:
            self._workspace = workspace
        self._refresh()

    def _refresh(self, query: str = ""):
        for w in self._results_frame.winfo_children():
            w.destroy()

        if not self._workspace:
            ctk.CTkLabel(
                self._results_frame,
                text="No research workspace connected.",
                text_color="gray",
            ).pack(pady=20)
            return

        entries = (
            self._workspace.search(query)
            if query
            else self._workspace.get_all()
        )

        stats = self._workspace.get_stats()
        self._stats_label.configure(
            text=f"{stats['total_entries']} entries, "
            f"{stats['total_sources']} sources, "
            f"{stats['projects_linked']} projects linked"
        )

        if not entries:
            ctk.CTkLabel(
                self._results_frame,
                text=(
                    "No research entries yet."
                    if not query
                    else f"No results for '{query}'."
                ),
                text_color="gray",
            ).pack(pady=20)
            return

        for entry in reversed(entries):
            frame = ctk.CTkFrame(
                self._results_frame, fg_color="transparent"
            )
            frame.pack(fill="x", pady=2)

            ctk.CTkLabel(
                frame,
                text=f"\U0001F50D {entry.query[:80]}",
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill="x", padx=4)

            if entry.notes:
                ctk.CTkLabel(
                    frame,
                    text=entry.notes[:150],
                    font=("Segoe UI", 9),
                    text_color="#CCC",
                    anchor="w",
                    wraplength=450,
                ).pack(fill="x", padx=(16, 4))

            meta_parts = []
            if entry.tags:
                meta_parts.append(" ".join(f"[{t}]" for t in entry.tags))
            if entry.sources:
                meta_parts.append(f"{len(entry.sources)} source(s)")
            if entry.created_at:
                meta_parts.append(entry.created_at[:10])
            if meta_parts:
                ctk.CTkLabel(
                    frame,
                    text=" | ".join(meta_parts),
                    font=("Segoe UI", 8),
                    text_color="#666",
                    anchor="w",
                ).pack(fill="x", padx=(16, 4))


class SuggestionsPanelFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Displays follow-up recommendations and ambient suggestions."""

    def __init__(
        self,
        master,
        followup_engine=None,
        ambient_intelligence=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._followup = followup_engine
        self._ambient = ambient_intelligence
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Suggestions & Follow-ups",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        # Ambient toggle
        toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        toggle_frame.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(
            toggle_frame,
            text="Ambient Intelligence:",
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(0, 8))

        self._ambient_var = tk.BooleanVar(value=False)
        self._ambient_toggle = ctk.CTkSwitch(
            toggle_frame,
            text="",
            variable=self._ambient_var,
            command=self._on_toggle_ambient,
        )
        self._ambient_toggle.pack(side="left")

        ctk.CTkLabel(
            toggle_frame,
            text="(proactive suggestions)",
            font=("Segoe UI", 9),
            text_color="gray",
        ).pack(side="left", padx=8)

        # Follow-ups container
        self._followup_frame = ctk.CTkFrame(self)
        self._followup_frame.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(
            self._followup_frame,
            text="Follow-up Actions",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 4))

        self._followup_container = ctk.CTkFrame(
            self._followup_frame, fg_color="transparent"
        )
        self._followup_container.pack(fill="x", padx=8, pady=(0, 8))

        # Ambient suggestions container
        self._ambient_frame = ctk.CTkFrame(self)
        self._ambient_frame.pack(fill="both", expand=True, padx=8, pady=4)

        ctk.CTkLabel(
            self._ambient_frame,
            text="Ambient Suggestions",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 4))

        self._ambient_container = ctk.CTkFrame(
            self._ambient_frame, fg_color="transparent"
        )
        self._ambient_container.pack(
            fill="both", expand=True, padx=8, pady=(0, 8)
        )

        self._refresh_btn = ctk.CTkButton(
            self,
            text="Refresh",
            command=self._refresh,
            width=100,
        )
        self._refresh_btn.pack(pady=8)

    def _on_toggle_ambient(self):
        if self._ambient:
            self._ambient.enabled = self._ambient_var.get()

    def refresh(
        self,
        followup_engine=None,
        ambient_intelligence=None,
        user_input="",
        response_text="",
    ):
        if followup_engine:
            self._followup = followup_engine
        if ambient_intelligence:
            self._ambient = ambient_intelligence
            self._ambient_var.set(self._ambient.enabled)
        self._refresh(user_input, response_text)

    def _refresh(self, user_input="", response_text=""):
        # Clear containers
        for w in self._followup_container.winfo_children():
            w.destroy()
        for w in self._ambient_container.winfo_children():
            w.destroy()

        has_content = False

        # Follow-ups
        if self._followup and user_input:
            followups = self._followup.suggest(user_input, response_text)
            if followups:
                has_content = True
                for fu in followups:
                    frame = ctk.CTkFrame(
                        self._followup_container,
                        fg_color="transparent",
                    )
                    frame.pack(fill="x", pady=2)

                    icon = _icon_for(fu.category)
                    ctk.CTkLabel(
                        frame,
                        text=f"{icon} {fu.text}",
                        font=("Segoe UI", 10),
                        anchor="w",
                        wraplength=400,
                    ).pack(fill="x", padx=4)

        if not has_content and self._followup:
            ctk.CTkLabel(
                self._followup_container,
                text="Follow-ups appear after you send a message.",
                text_color="gray",
                font=("Segoe UI", 10),
            ).pack(pady=10)

        # Ambient suggestions
        ambients = []
        if self._ambient and self._ambient.enabled:
            ambients = self._ambient.get_suggestions(min_confidence=0.3)

        if ambients:
            for i, suggestion in enumerate(ambients):
                frame = ctk.CTkFrame(
                    self._ambient_container,
                    fg_color="#2D2D3D",
                    corner_radius=6,
                )
                frame.pack(fill="x", pady=2, padx=2)

                text_frame = ctk.CTkFrame(
                    frame, fg_color="transparent"
                )
                text_frame.pack(
                    fill="x", padx=8, pady=(6, 2), side="left",
                    expand=True,
                )

                ctk.CTkLabel(
                    text_frame,
                    text=f"\U0001F4A1 {suggestion.message[:120]}",
                    font=("Segoe UI", 10),
                    anchor="w",
                    wraplength=350,
                ).pack(fill="x")

                ctk.CTkLabel(
                    text_frame,
                    text=f"confidence: {suggestion.confidence:.0%}",
                    font=("Segoe UI", 8),
                    text_color="#888",
                    anchor="w",
                ).pack(fill="x")

                dismiss_btn = ctk.CTkButton(
                    frame,
                    text="\u2715",
                    width=24,
                    height=24,
                    fg_color="transparent",
                    text_color="#888",
                    hover_color="#555",
                    command=lambda idx=i: self._dismiss(idx),
                )
                dismiss_btn.pack(
                    side="right", padx=(0, 8), pady=6
                )
        else:
            ctk.CTkLabel(
                self._ambient_container,
                text=(
                    "Enable ambient intelligence above for proactive "
                    "suggestions."
                ),
                text_color="gray",
                font=("Segoe UI", 10),
            ).pack(pady=10)

    def _dismiss(self, index: int):
        if self._ambient:
            self._ambient.dismiss(index)
            self._refresh()


class Phase7Integration:
    """
    Hooks Phase 7 widgets into JosephApp.

    Adds 4 new pages to the navigation bar and creates the embedded
    panel frames. Functional hooks (activity tracking, project context,
    follow-ups) are applied directly in app.py for clarity.
    """

    @staticmethod
    def hook_into(app):
        if ctk is None:
            logger.warning("customtkinter not available, skipping Phase 7 UI")
            return

        try:
            pages = [
                ("Activity Timeline", ActivityTimelineFrame, {
                    "tracker": getattr(app, "_activity_tracker", None),
                }),
                ("Insights", InsightDashboardFrame, {
                    "insight_engine": getattr(app, "_insight_engine", None),
                }),
                ("Research", ResearchWorkspaceFrame, {
                    "research_workspace": getattr(app, "_research_workspace", None),
                }),
                ("Suggestions", SuggestionsPanelFrame, {
                    "followup_engine": getattr(app, "_followup_engine", None),
                    "ambient_intelligence": getattr(app, "_ambient_intel", None),
                }),
            ]

            for page_name, frame_class, kwargs in pages:
                if page_name not in app._page_frames:
                    page_frame = ctk.CTkFrame(
                        app._workspace_stack,
                        fg_color=app.colors.get("bg", "#141414"),
                        corner_radius=0,
                    )
                    page_frame.grid(row=0, column=0, sticky="nsew")
                    page_frame.grid_rowconfigure(0, weight=1)
                    page_frame.grid_columnconfigure(0, weight=1)
                    app._page_frames[page_name] = page_frame

                    btn = ctk.CTkButton(
                        app._nav_buttons_frame,
                        text=page_name,
                        height=34,
                        font=("Segoe UI", 12),
                        fg_color=app.colors.get("card", "#252525"),
                        hover_color=app.colors.get("border_light", "#404040"),
                        text_color=app.colors.get("text", "#ececec"),
                        corner_radius=8,
                        anchor="w",
                        command=lambda p=page_name: app._show_page(p),
                    )
                    btn.pack(fill="x", pady=4)
                    app._nav_buttons[page_name] = btn

                frame = frame_class(
                    app._page_frames[page_name],
                    **kwargs,
                    fg_color="transparent",
                    corner_radius=0,
                )
                frame.pack(fill="both", expand=True)

                ref_name = f"_phase7_{page_name.lower().replace(' ', '_')}"
                setattr(app, ref_name, frame)

            logger.info("Phase 7 integration complete")
        except Exception as e:
            logger.warning(f"Phase 7 integration failed: {e}")
