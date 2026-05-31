"""
ui/phase6.py
------------
Explainability Panel — Phase 6.

Displays a detailed breakdown of how Joseph processed each request:
  - Detected intent
  - Execution plan (subsystems invoked)
  - Context sources retrieved
  - Tools invoked (if any)
  - Knowledge graph updates
  - Timing and duration

Hooks into the app via the Phase6Integration class, following the
same pattern as Phase 5.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
except ImportError:
    ctk = None


FONTS_P6 = {
    "title": ("Segoe UI", 14, "bold"),
    "subtitle": ("Segoe UI", 11, "bold"),
    "body": ("Segoe UI", 11),
    "mono": ("Consolas", 10),
    "small": ("Segoe UI", 9),
}


class ExplainabilityPanel(ctk.CTkScrollableFrame if ctk else object):
    """
    Panel showing the full orchestration trace for the last interaction.

    Sections:
      1. Intent — detected intent category
      2. Plan — subsystems and steps executed
      3. Context sources — what was retrieved and from where
      4. Tools — any tools invoked and their results
      5. Graph updates — knowledge graph changes
      6. Timing — duration per step and total
    """

    def __init__(self, parent, colors=None, **kwargs):
        if ctk:
            super().__init__(parent, **kwargs)
        self.colors = colors or {}
        self.router = None
        self._intent_label = None
        self._plan_text = None
        self._sources_text = None
        self._tools_text = None
        self._graph_text = None
        self._timing_text = None
        self._build_panel()

    def _build_panel(self):
        """Build the explainability panel UI."""
        if not ctk:
            return

        c = self.colors

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(
            header,
            text="⚙  Orchestration Trace",
            font=FONTS_P6["title"],
            text_color=c.get("text", "#ececec"),
        ).pack(side="left")

        self._refresh_btn = ctk.CTkButton(
            header,
            text="⟳ Refresh",
            width=70,
            height=24,
            font=FONTS_P6["small"],
            fg_color=c.get("card", "#252525"),
            hover_color=c.get("border_light", "#404040"),
            text_color=c.get("text", "#ececec"),
            corner_radius=4,
            command=self.refresh,
        )
        self._refresh_btn.pack(side="right")

        separator = ctk.CTkFrame(self, height=1, fg_color=c.get("border", "#333333"))
        separator.pack(fill="x", padx=12, pady=(0, 8))

        # ── 1. Intent Section ──
        self._build_section_header("Intent", 0)
        self._intent_label = ctk.CTkLabel(
            self,
            text="No request processed yet",
            font=FONTS_P6["body"],
            text_color=c.get("text_dim", "#7a7a7a"),
            anchor="w",
            justify="left",
        )
        self._intent_label.pack(fill="x", padx=24, pady=(0, 12))

        # ── 2. Plan Section ──
        self._build_section_header("Execution Plan", 1)
        self._plan_text = ctk.CTkTextbox(
            self,
            height=80,
            font=FONTS_P6["mono"],
            fg_color=c.get("input_bg", "#1a1a1a"),
            text_color=c.get("text", "#ececec"),
            border_color=c.get("border", "#333333"),
            border_width=1,
            corner_radius=4,
            wrap="none",
        )
        self._plan_text.pack(fill="x", padx=24, pady=(0, 12))
        self._plan_text.insert("end", "Awaiting first request...")
        self._plan_text.configure(state="disabled")

        # ── 3. Context Sources ──
        self._build_section_header("Context Sources", 2)
        self._sources_text = ctk.CTkTextbox(
            self,
            height=60,
            font=FONTS_P6["mono"],
            fg_color=c.get("input_bg", "#1a1a1a"),
            text_color=c.get("text", "#ececec"),
            border_color=c.get("border", "#333333"),
            border_width=1,
            corner_radius=4,
            wrap="none",
        )
        self._sources_text.pack(fill="x", padx=24, pady=(0, 12))
        self._sources_text.insert("end", "No context retrieved yet")
        self._sources_text.configure(state="disabled")

        # ── 4. Tools Section ──
        self._build_section_header("Tools Invoked", 3)
        self._tools_text = ctk.CTkTextbox(
            self,
            height=60,
            font=FONTS_P6["mono"],
            fg_color=c.get("input_bg", "#1a1a1a"),
            text_color=c.get("text", "#ececec"),
            border_color=c.get("border", "#333333"),
            border_width=1,
            corner_radius=4,
            wrap="none",
        )
        self._tools_text.pack(fill="x", padx=24, pady=(0, 12))
        self._tools_text.insert("end", "No tools used yet")
        self._tools_text.configure(state="disabled")

        # ── 5. Graph Updates ──
        self._build_section_header("Knowledge Graph Updates", 4)
        self._graph_text = ctk.CTkTextbox(
            self,
            height=60,
            font=FONTS_P6["mono"],
            fg_color=c.get("input_bg", "#1a1a1a"),
            text_color=c.get("text", "#ececec"),
            border_color=c.get("border", "#333333"),
            border_width=1,
            corner_radius=4,
            wrap="none",
        )
        self._graph_text.pack(fill="x", padx=24, pady=(0, 12))
        self._graph_text.insert("end", "No graph updates yet")
        self._graph_text.configure(state="disabled")

        # ── 6. Timing ──
        self._build_section_header("Timing", 5)
        self._timing_text = ctk.CTkLabel(
            self,
            text="No timing data yet",
            font=FONTS_P6["body"],
            text_color=c.get("text_dim", "#7a7a7a"),
            anchor="w",
            justify="left",
        )
        self._timing_text.pack(fill="x", padx=24, pady=(0, 12))

    def _build_section_header(self, title: str, index: int):
        if not ctk:
            return
        c = self.colors
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=12, pady=(4, 4))

        ctk.CTkLabel(
            frame,
            text=f"{index + 1}. {title}",
            font=FONTS_P6["subtitle"],
            text_color=c.get("accent", "#4d9de0"),
            anchor="w",
        ).pack(side="left")

    def set_router(self, router):
        """Set the AssistantRouter to pull data from."""
        self.router = router

    def refresh(self):
        """Refresh the panel from the current router state."""
        if not ctk:
            return
        if not self.router:
            self._set_text(self._intent_label, "Router not set")
            return

        result = self.router.get_last_result()
        if not result:
            self._set_text(self._intent_label, "No request processed yet")
            return

        data = result.to_dict()

        # 1. Intent
        self._set_text(self._intent_label, f"Intent: {data.get('intent', 'unknown')}")

        # 2. Plan
        plan = data.get("plan")
        if plan and plan.get("steps"):
            lines = []
            for step in plan["steps"]:
                status_icon = "✓" if step.get("status") == "completed" else "○"
                lines.append(
                    f"  {status_icon} {step['subsystem']}/{step['action']} "
                    f"({step.get('duration_ms', 0)}ms)"
                )
            self._set_textbox(self._plan_text, "\n".join(lines))
        else:
            self._set_textbox(self._plan_text, "No plan executed")

        # 3. Context sources
        sources = data.get("context_sources") or []
        if sources and isinstance(sources, list):
            lines = [f"  {s.get('type', '?')}: {s.get('length', 0)} chars" for s in sources]
            self._set_textbox(self._sources_text, "\n".join(lines) if lines else "No sources")
        else:
            subs = data.get("subsystem_outputs", {})
            src_line = subs.get("context_sources", "Not available")
            self._set_textbox(self._sources_text, f"  {src_line}")

        # 4. Tools
        tool_result = data.get("tool_result")
        if tool_result:
            self._set_textbox(self._tools_text, f"  Result: {tool_result[:500]}")
        else:
            self._set_textbox(self._tools_text, "  No tools invoked")

        # 5. Graph updates
        graph_updates = data.get("graph_updates") or []
        if graph_updates:
            seen = set()
            lines = []
            for u in graph_updates:
                key = (u.get("action", ""), u.get("label", ""))
                if key not in seen:
                    seen.add(key)
                    lines.append(f"  {u.get('action', '?')}: {u.get('label', u.get('source', '?'))}")
            self._set_textbox(self._graph_text, "\n".join(lines) if lines else "  No updates")
        else:
            self._set_textbox(self._graph_text, "  No graph updates")

        # 6. Timing
        timing_lines = [
            f"  Total: {data.get('duration_ms', 0)}ms",
        ]
        error = data.get("error")
        if error:
            timing_lines.append(f"  Error: {error}")
        self._set_text(self._timing_text, "\n".join(timing_lines))

    def _set_text(self, label, text):
        """Update a CTkLabel's text."""
        try:
            label.configure(text=str(text))
        except Exception:
            pass

    def _set_textbox(self, textbox, text):
        """Update a CTkTextbox's content."""
        try:
            textbox.configure(state="normal")
            textbox.delete("0.0", "end")
            textbox.insert("end", str(text))
            textbox.configure(state="disabled")
        except Exception:
            pass


class Phase6Integration:
    """
    Hooks the explainability panel into JosephApp.

    Follows the same pattern as Phase5Integration.hook_into().
    """

    @staticmethod
    def hook_into(app):
        """
        Monkey-patch the app to add the Phase 6 explainability panel.

        Adds an "Explain" page to the navigation and wires the
        AssistantRouter for automatic trace collection.
        """
        if ctk is None:
            logger.warning("customtkinter not available, skipping Phase 6 UI")
            return

        try:
            # Create the router if not already created by main.py
            if not hasattr(app, "_phase6_router") or app._phase6_router is None:
                from brain.orchestrator import AssistantRouter
                app._phase6_router = AssistantRouter(
                    llm=app.llm,
                    memory=app.memory,
                    hyper_engine=getattr(app, "_hyper", None),
                    memory_relevance=getattr(app, "_memory_relevance", None),
                    smart_cache=getattr(app, "_smart_cache", None),
                )

            # Create the explainability panel
            panel = ExplainabilityPanel(
                parent=app._page_frames.get("Explain", None) or _create_explain_page(app),
                colors=app.colors,
                fg_color=app.colors.get("bg", "#141414"),
                corner_radius=0,
            )

            if "Explain" in app._page_frames:
                # Repack panel into the existing page frame
                for widget in app._page_frames["Explain"].winfo_children():
                    widget.destroy()
                panel.pack(fill="both", expand=True)
                panel.set_router(app._phase6_router)

                # Hook into the existing page
                page_frame = app._page_frames["Explain"]
                panel = ExplainabilityPanel(
                    page_frame,
                    colors=app.colors,
                    fg_color=app.colors.get("bg", "#141414"),
                    corner_radius=0,
                )
                panel.pack(fill="both", expand=True)
                panel.set_router(app._phase6_router)
                app._explain_panel = panel

                logger.info("Phase 6: Explain panel added to existing page")
            else:
                _create_explain_page(app)
                page_frame = app._page_frames["Explain"]
                panel = ExplainabilityPanel(
                    page_frame,
                    colors=app.colors,
                    fg_color=app.colors.get("bg", "#141414"),
                    corner_radius=0,
                )
                panel.pack(fill="both", expand=True)
                panel.set_router(app._phase6_router)
                app._explain_panel = panel
                logger.info("Phase 6: Explain page and panel created")

            # Monkey-patch the send message method to auto-refresh explain panel
            _original_finish = getattr(app, "_finish_response", None)

            def _phase6_finish_response(error=False):
                if _original_finish:
                    _original_finish(error=error)
                # Auto-refresh explain panel after each response
                if hasattr(app, "_explain_panel"):
                    app.after(100, app._explain_panel.refresh)

            app._finish_response = _phase6_finish_response

            logger.info("Phase 6 integration complete")

        except Exception as e:
            logger.warning(f"Phase 6 integration failed: {e}")


def _create_explain_page(app):
    """Create a new Explain page in the app's navigation."""
    if not hasattr(app, "_page_frames"):
        return None

    try:
        # Find the workspace area (the container for page_frames)
        workspace = None
        for child in app.winfo_children():
            if hasattr(child, "winfo_children"):
                for grandchild in child.winfo_children():
                    if hasattr(grandchild, "winfo_children"):
                        for gg in grandchild.winfo_children():
                            if isinstance(gg, ctk.CTkFrame) and gg != getattr(app, "_chat_scroll", None):
                                for ggg in gg.winfo_children():
                                    if hasattr(ggg, "winfo_children") and hasattr(ggg, "tkraise"):
                                        workspace = ggg

        if workspace is None:
            # Walk all children to find the paned window or workspace
            def find_workspace(widget):
                if hasattr(widget, "tkraise") and hasattr(widget, "winfo_children"):
                    for child in widget.winfo_children():
                        if isinstance(child, ctk.CTkFrame):
                            result = find_workspace(child)
                            if result:
                                return result
                return None

            for child in app.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    result = find_workspace(child)
                    if result:
                        workspace = result
                        break

        if workspace is None:
            # Last resort: use the app itself as parent
            workspace = app

        # Create the Explain page frame
        explain_frame = ctk.CTkFrame(
            workspace,
            fg_color=app.colors.get("bg", "#141414"),
            corner_radius=0,
        )
        app._page_frames["Explain"] = explain_frame

        # Add nav button if nav_buttons exist
        if hasattr(app, "_nav_buttons") and hasattr(app, "_nav_panel"):
            import tkinter as tk
            btn = ctk.CTkButton(
                app._nav_panel,
                text="Explain",
                font=("Segoe UI", 12),
                fg_color=app.colors.get("card", "#252525"),
                hover_color=app.colors.get("border_light", "#404040"),
                text_color=app.colors.get("text", "#ececec"),
                anchor="w",
                corner_radius=5,
                command=lambda: app._show_page("Explain"),
            )
            btn.pack(fill="x", padx=8, pady=2)
            app._nav_buttons["Explain"] = btn

        explain_frame.grid(row=0, column=0, sticky="nsew")
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=1)

        return explain_frame

    except Exception as e:
        logger.warning(f"Could not create Explain page: {e}")
        return app
