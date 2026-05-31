"""
ui/phase8.py
---------------
Phase 8 UI widgets — Personal Operating System and Autonomous Workflows.

Frames:
- WorkspaceView: unified project workspace with all connected data
- RoadmapView: roadmap display with milestone progress
- WeeklyReviewView: weekly review report display
- BriefingV2View: enhanced daily briefing display
- LearningView: learning companion with goals, sessions, reviews
- DecisionHistoryView: decision log with search
- ContinuityView: cross-session continuity display
- Phase8Integration: hooks all into JosephApp
"""

import logging
import tkinter as tk
from datetime import datetime
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

logger = logging.getLogger(__name__)


def _section_header(text: str) -> str:
    return f"\u2500 {text} \u2500"


# ------------------------------------------------------------------ #
# Workspace View
# ------------------------------------------------------------------ #

class WorkspaceViewFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Unified workspace display for a single project."""

    def __init__(self, master, workspace_manager=None, project_commander=None,
                 project_store=None, **kwargs):
        super().__init__(master, **kwargs)
        self._wm = workspace_manager
        self._pc = project_commander
        self._ps = project_store
        self._current_project_id: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Project Workspace",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        # Project selector
        selector_frame = ctk.CTkFrame(self, fg_color="transparent")
        selector_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._project_var = tk.StringVar(value="")
        self._project_menu = ctk.CTkOptionMenu(
            selector_frame, variable=self._project_var,
            values=[""], command=self._on_project_selected, width=200,
        )
        self._project_menu.pack(side="left", padx=(0, 8))

        self._refresh_btn = ctk.CTkButton(
            selector_frame, text="Refresh", command=self._refresh,
            width=80,
        )
        self._refresh_btn.pack(side="left")

        # Content area
        self._content = ctk.CTkTextbox(
            self, wrap="word", font=("Consolas", 11),
            fg_color="#1a1a1a", text_color="#e0e0e0",
        )
        self._content.pack(fill="both", expand=True, padx=8, pady=4)

        self._refresh_project_list()

    def _on_project_selected(self, choice):
        if not choice or not self._ps:
            return
        try:
            for proj in self._ps.get_active_projects():
                if proj.name == choice:
                    self._current_project_id = proj.id
                    self._render_workspace()
                    return
        except Exception:
            pass

    def refresh(self, workspace_manager=None, project_commander=None):
        if workspace_manager:
            self._wm = workspace_manager
        if project_commander:
            self._pc = project_commander
        self._refresh_project_list()

    def _refresh_project_list(self):
        if not self._ps:
            return
        try:
            projects = self._ps.get_all_projects()
            names = [p.name for p in projects]
            self._project_menu.configure(values=names if names else [""])
            if names:
                self._project_var.set(names[0])
                self._on_project_selected(names[0])
        except Exception:
            pass

    def _refresh(self):
        self._render_workspace()

    def _render_workspace(self):
        pid = self._current_project_id
        if not pid or not self._wm:
            self._content.delete("1.0", "end")
            self._content.insert("1.0", "Select a project to view its workspace.")
            return

        ws = self._wm.get_workspace(pid)
        if not ws:
            self._content.delete("1.0", "end")
            self._content.insert("1.0", "Workspace not found.")
            return

        status = self._pc.get_status(pid) if self._pc else {}
        lines = [
            f"Workspace: {ws.project_name}",
            f"Progress: {status.get('progress_pct', 0)}%",
            "",
            _section_header("GOALS"),
        ]
        if ws.goals:
            for g in ws.goals:
                lines.append(f"  {g.get('title', '')} [{g.get('status', '')}]")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(_section_header("MILESTONES"))
        if ws.milestones:
            for m in ws.milestones:
                due = m.get("target_date", "")
                lines.append(f"  {m.get('title', '')} due {due} [{m.get('status', '')}]")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(_section_header("TASKS"))
        if ws.tasks:
            open_t = [t for t in ws.tasks if t.get("status") != "done"]
            done_t = [t for t in ws.tasks if t.get("status") == "done"]
            lines.append(f"  {len(open_t)} open / {len(done_t)} done")
            for t in open_t[:10]:
                lines.append(f"  - {t.get('title', '')}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(_section_header("RESEARCH"))
        if ws.research_entries:
            for r in ws.research_entries[-5:]:
                lines.append(f"  - {r.get('query', '')[:60]}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(_section_header("FILES & LINKS"))
        lines.append(f"  Files: {len(ws.files)}")
        lines.append(f"  KG Links: {len(ws.kg_links)}")

        lines.append("")
        lines.append(_section_header("DECISIONS"))
        if ws.decisions:
            for d in ws.decisions[-5:]:
                lines.append(f"  - {d.get('title', '')}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(_section_header("LESSONS"))
        if ws.lessons:
            for l in ws.lessons[-3:]:
                lines.append(f"  - {l.get('lesson', '')[:80]}")
        else:
            lines.append("  (none)")

        self._content.delete("1.0", "end")
        self._content.insert("1.0", "\n".join(lines))


# ------------------------------------------------------------------ #
# Roadmap View
# ------------------------------------------------------------------ #

class RoadmapViewFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Display roadmaps with milestone progress bars."""

    def __init__(self, master, roadmap_engine=None, **kwargs):
        super().__init__(master, **kwargs)
        self._rm = roadmap_engine
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Roadmaps",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            self, text="Learning plans, development plans, and project roadmaps.",
            font=("Segoe UI", 10), text_color="gray", anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 8))

        # Template buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=4)

        self._template_var = tk.StringVar(value="python")
        templates = ["python", "rust", "embedded", "computer_science"]
        self._template_menu = ctk.CTkOptionMenu(
            btn_frame, variable=self._template_var,
            values=templates, width=140,
        )
        self._template_menu.pack(side="left", padx=(0, 8))

        self._create_btn = ctk.CTkButton(
            btn_frame, text="Create Roadmap",
            command=self._on_create, width=120,
        )
        self._create_btn.pack(side="left")

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self, roadmap_engine=None):
        if roadmap_engine:
            self._rm = roadmap_engine

    def _on_create(self):
        if not self._rm:
            return
        topic = self._template_var.get()
        roadmap = self._rm.create_learning_plan(topic)
        if roadmap:
            self._render_roadmap(roadmap)

    def _render_roadmap(self, roadmap):
        for w in self._content.winfo_children():
            w.destroy()

        header = ctk.CTkLabel(
            self._content,
            text=f"{roadmap.title} ({roadmap.total_effort_hours}h total)",
            font=("Segoe UI", 12, "bold"), anchor="w",
        )
        header.pack(fill="x", padx=4, pady=(4, 8))

        for i, m in enumerate(roadmap.milestones):
            frame = ctk.CTkFrame(self._content, fg_color="#252525", corner_radius=4)
            frame.pack(fill="x", pady=2, padx=4)

            status = m.get("status", "pending")
            status_colors = {
                "pending": "#888", "in_progress": "#d4924a", "completed": "#3dba7a",
            }
            color = status_colors.get(status, "#888")

            row1 = ctk.CTkFrame(frame, fg_color="transparent")
            row1.pack(fill="x", padx=8, pady=(4, 0))

            ctk.CTkLabel(
                row1, text=f"Step {i+1}",
                font=("Segoe UI", 9, "bold"), text_color=color,
            ).pack(side="left", padx=(0, 8))

            ctk.CTkLabel(
                row1, text=m.get("title", ""),
                font=("Segoe UI", 11, "bold"), anchor="w",
            ).pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(
                row1, text=f"~{m.get('estimated_hours', 1)}h",
                font=("Segoe UI", 9), text_color="#888",
            ).pack(side="right")

            row2 = ctk.CTkFrame(frame, fg_color="transparent")
            row2.pack(fill="x", padx=8, pady=(0, 4))

            ctk.CTkLabel(
                row2, text=m.get("description", ""),
                font=("Segoe UI", 9), text_color="#aaa", anchor="w",
                wraplength=500,
            ).pack(fill="x", padx=(0, 4))


# ------------------------------------------------------------------ #
# Weekly Review View
# ------------------------------------------------------------------ #

class WeeklyReviewViewFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Display weekly review reports."""

    def __init__(self, master, weekly_review=None, **kwargs):
        super().__init__(master, **kwargs)
        self._wr = weekly_review
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Weekly Review",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        self._generate_btn = ctk.CTkButton(
            self, text="Generate Weekly Review",
            command=self._on_generate, width=200,
        )
        self._generate_btn.pack(pady=8)

        self._content = ctk.CTkTextbox(
            self, wrap="word", font=("Consolas", 11),
            fg_color="#1a1a1a", text_color="#e0e0e0",
        )
        self._content.pack(fill="both", expand=True, padx=8, pady=4)

    def refresh(self, weekly_review=None):
        if weekly_review:
            self._wr = weekly_review

    def _on_generate(self):
        if not self._wr:
            return
        try:
            report = self._wr.generate()
            self._content.delete("1.0", "end")
            self._content.insert("1.0", report)
        except Exception as e:
            self._content.delete("1.0", "end")
            self._content.insert("1.0", f"Error generating review: {e}")


# ------------------------------------------------------------------ #
# Briefing V2 View
# ------------------------------------------------------------------ #

class BriefingV2ViewFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Enhanced daily briefing display."""

    def __init__(self, master, briefing_v2=None, **kwargs):
        super().__init__(master, **kwargs)
        self._bv2 = briefing_v2
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Daily Briefing",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        self._generate_btn = ctk.CTkButton(
            self, text="Generate Briefing",
            command=self._on_generate, width=180,
        )
        self._generate_btn.pack(pady=8)

        self._content = ctk.CTkTextbox(
            self, wrap="word", font=("Consolas", 11),
            fg_color="#1a1a1a", text_color="#e0e0e0",
        )
        self._content.pack(fill="both", expand=True, padx=8, pady=4)

    def refresh(self, briefing_v2=None):
        if briefing_v2:
            self._bv2 = briefing_v2

    def _on_generate(self):
        if not self._bv2:
            return
        try:
            report = self._bv2.generate()
            self._content.delete("1.0", "end")
            self._content.insert("1.0", report)
        except Exception as e:
            self._content.delete("1.0", "end")
            self._content.insert("1.0", f"Error generating briefing: {e}")


# ------------------------------------------------------------------ #
# Learning View
# ------------------------------------------------------------------ #

class LearningViewFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Learning companion display."""

    def __init__(self, master, learning_companion=None, roadmap_engine=None,
                 **kwargs):
        super().__init__(master, **kwargs)
        self._lc = learning_companion
        self._rm = roadmap_engine
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Learning Companion",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        # Controls
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=8, pady=4)

        self._topic_entry = ctk.CTkEntry(
            ctrl_frame, placeholder_text="Topic (e.g., Rust)", width=200,
        )
        self._topic_entry.pack(side="left", padx=(0, 8))

        self._add_goal_btn = ctk.CTkButton(
            ctrl_frame, text="Add Goal", command=self._on_add_goal,
            width=80,
        )
        self._add_goal_btn.pack(side="left", padx=(0, 8))

        self._refresh_btn = ctk.CTkButton(
            ctrl_frame, text="Refresh", command=self._refresh_display,
            width=80,
        )
        self._refresh_btn.pack(side="left")

        # Stats
        self._stats_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 10), text_color="gray", anchor="w",
        )
        self._stats_label.pack(fill="x", padx=8, pady=4)

        # Goals container
        self._goals_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._goals_frame.pack(fill="both", expand=True, padx=4, pady=4)

    def refresh(self, learning_companion=None, roadmap_engine=None):
        if learning_companion:
            self._lc = learning_companion
        if roadmap_engine:
            self._rm = roadmap_engine
        self._refresh_display()

    def _on_add_goal(self):
        topic = self._topic_entry.get().strip()
        if not topic or not self._lc:
            return
        self._lc.create_goal(topic)
        self._topic_entry.delete(0, "end")
        self._refresh_display()

    def _refresh_display(self):
        for w in self._goals_frame.winfo_children():
            w.destroy()

        if not self._lc:
            ctk.CTkLabel(
                self._goals_frame, text="Learning companion not available.",
                text_color="gray",
            ).pack(pady=20)
            return

        stats = self._lc.get_study_stats()
        self._stats_label.configure(
            text=f"{stats['active_goals']} goals · "
            f"{stats['total_sessions']} sessions · "
            f"{stats['total_hours']}h studied · "
            f"{stats['completed_topics']} topics completed"
        )

        goals = self._lc.get_all_goals()
        if not goals:
            ctk.CTkLabel(
                self._goals_frame,
                text="No learning goals yet. Add one above!",
                text_color="gray",
            ).pack(pady=20)
            return

        for goal in goals:
            frame = ctk.CTkFrame(
                self._goals_frame, fg_color="#252525", corner_radius=6,
            )
            frame.pack(fill="x", pady=4, padx=4)

            ctk.CTkLabel(
                frame, text=goal.topic,
                font=("Segoe UI", 12, "bold"), anchor="w",
            ).pack(fill="x", padx=8, pady=(6, 2))

            status_text = f"Level: {goal.target_level} · Status: {goal.status}"
            if goal.completed_topics:
                status_text += f" · {len(goal.completed_topics)} topics done"
            ctk.CTkLabel(
                frame, text=status_text,
                font=("Segoe UI", 9), text_color="#aaa", anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 2))

            if goal.current_topic:
                ctk.CTkLabel(
                    frame, text=f"Current: {goal.current_topic}",
                    font=("Segoe UI", 10), text_color="#d4924a", anchor="w",
                ).pack(fill="x", padx=8, pady=(0, 4))

            # Completed topics
            if goal.completed_topics:
                topics_text = "Completed: " + ", ".join(goal.completed_topics[-5:])
                ctk.CTkLabel(
                    frame, text=topics_text,
                    font=("Segoe UI", 9), text_color="#3dba7a", anchor="w",
                    wraplength=450,
                ).pack(fill="x", padx=8, pady=(0, 6))

        # Due reviews
        due = self._lc.get_due_reviews()
        if due:
            due_frame = ctk.CTkFrame(self._goals_frame, fg_color="#2d2d1a")
            due_frame.pack(fill="x", pady=8, padx=4)
            ctk.CTkLabel(
                due_frame, text=f"Reviews Due: {len(due)}",
                font=("Segoe UI", 11, "bold"), text_color="#d4924a", anchor="w",
            ).pack(fill="x", padx=8, pady=4)
            for r in due[:5]:
                ctk.CTkLabel(
                    due_frame, text=f"  - {r.topic}",
                    font=("Segoe UI", 9), anchor="w",
                ).pack(fill="x", padx=8)


# ------------------------------------------------------------------ #
# Decision History View
# ------------------------------------------------------------------ #

class DecisionHistoryViewFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Decision history display with search."""

    def __init__(self, master, decision_history=None, **kwargs):
        super().__init__(master, **kwargs)
        self._dh = decision_history
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Decision History",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        # Search
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._search_var = tk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Search decisions...",
            textvariable=self._search_var, width=250,
        )
        self._search_entry.pack(side="left", padx=(0, 8))

        self._search_btn = ctk.CTkButton(
            search_frame, text="Search", command=self._on_search, width=80,
        )
        self._search_btn.pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            search_frame, text="Show All", command=self._show_all, width=80,
            fg_color="#555",
        ).pack(side="left")

        self._results_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._results_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._show_all()

    def refresh(self, decision_history=None):
        if decision_history:
            self._dh = decision_history
        self._show_all()

    def _on_search(self):
        query = self._search_var.get().strip()
        if not query or not self._dh:
            self._show_all()
            return
        self._render_decisions(self._dh.search(query))

    def _show_all(self):
        if not self._dh:
            return
        self._render_decisions(self._dh.get_all())

    def _render_decisions(self, decisions):
        for w in self._results_frame.winfo_children():
            w.destroy()

        if not decisions:
            ctk.CTkLabel(
                self._results_frame, text="No decisions recorded yet.",
                text_color="gray",
            ).pack(pady=20)
            return

        for d in decisions[:20]:
            frame = ctk.CTkFrame(
                self._results_frame, fg_color="#252525", corner_radius=4,
            )
            frame.pack(fill="x", pady=2, padx=4)

            ctk.CTkLabel(
                frame, text=d.title,
                font=("Segoe UI", 11, "bold"), anchor="w",
            ).pack(fill="x", padx=8, pady=(4, 0))

            ctk.CTkLabel(
                frame, text=d.description[:120],
                font=("Segoe UI", 9), text_color="#ccc", anchor="w",
                wraplength=450,
            ).pack(fill="x", padx=8, pady=(0, 2))

            meta = f"[{d.category}] {d.timestamp[:10]}"
            if d.rationale:
                meta += f" · Why: {d.rationale[:60]}"
            ctk.CTkLabel(
                frame, text=meta,
                font=("Segoe UI", 8), text_color="#888", anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 4))


# ------------------------------------------------------------------ #
# Continuity View
# ------------------------------------------------------------------ #

class ContinuityViewFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Cross-session continuity display."""

    def __init__(self, master, continuity_engine=None, **kwargs):
        super().__init__(master, **kwargs)
        self._ce = continuity_engine
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Session Continuity",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        self._refresh_btn = ctk.CTkButton(
            self, text="Refresh Context",
            command=self._on_refresh, width=140,
        )
        self._refresh_btn.pack(pady=8)

        self._content = ctk.CTkTextbox(
            self, wrap="word", font=("Consolas", 11),
            fg_color="#1a1a1a", text_color="#e0e0e0",
        )
        self._content.pack(fill="both", expand=True, padx=8, pady=4)

    def refresh(self, continuity_engine=None):
        if continuity_engine:
            self._ce = continuity_engine
        self._on_refresh()

    def _on_refresh(self):
        if not self._ce:
            return
        try:
            ctx = self._ce.get_continuity_context()
            history = self._ce.get_session_history_summary()
            text = f"Session History:\n{history}\n\n{ctx}"
            self._content.delete("1.0", "end")
            self._content.insert("1.0", text)
        except Exception as e:
            self._content.delete("1.0", "end")
            self._content.insert("1.0", f"Error: {e}")


# ------------------------------------------------------------------ #
# Phase 8 Integration
# ------------------------------------------------------------------ #

class Phase8Integration:
    """
    Hooks Phase 8 widgets into JosephApp.

    Adds 6 new pages: Workspace, Roadmaps, Weekly Review, Briefing,
    Learning, Decisions, Continuity.
    """

    @staticmethod
    def hook_into(app):
        if ctk is None:
            logger.warning("customtkinter not available, skipping Phase 8 UI")
            return

        try:
            pages = [
                ("Workspace", WorkspaceViewFrame, {
                    "workspace_manager": getattr(app, "_workspace_manager", None),
                    "project_commander": getattr(app, "_project_commander", None),
                    "project_store": getattr(app, "_project_store", None),
                }),
                ("Roadmaps", RoadmapViewFrame, {
                    "roadmap_engine": getattr(app, "_roadmap_engine", None),
                }),
                ("Weekly Review", WeeklyReviewViewFrame, {
                    "weekly_review": getattr(app, "_weekly_review", None),
                }),
                ("Briefing", BriefingV2ViewFrame, {
                    "briefing_v2": getattr(app, "_briefing_v2", None),
                }),
                ("Learning", LearningViewFrame, {
                    "learning_companion": getattr(app, "_learning_companion", None),
                    "roadmap_engine": getattr(app, "_roadmap_engine", None),
                }),
                ("Decisions", DecisionHistoryViewFrame, {
                    "decision_history": getattr(app, "_decision_history", None),
                }),
                ("Continuity", ContinuityViewFrame, {
                    "continuity_engine": getattr(app, "_continuity_engine", None),
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

                ref_name = f"_phase8_{page_name.lower().replace(' ', '_')}"
                setattr(app, ref_name, frame)

            logger.info("Phase 8 integration complete")
        except Exception as e:
            logger.warning(f"Phase 8 integration failed: {e}")
