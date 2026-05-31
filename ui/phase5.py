"""
ui/phase5.py
------------
Phase 5 UI integration — adds Engineering Assistant, Tool Framework,
Project Manager, and Enhanced Voice System to the JOSEPH desktop UI.

Usage:
    from ui.phase5 import Phase5Integration
    Phase5Integration.hook_into(app_instance)
"""

import logging
import threading
import os
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import tkinter as tk

logger = logging.getLogger(__name__)

try:
    from ui.app import FONTS
except ImportError:
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

SAFETY_COLORS = {
    "safe": "#3dba7a",
    "confirm": "#d4924a",
    "restricted": "#d95f5f",
    "dangerous": "#ff4444",
}


class Phase5Integration:
    """
    Static methods that add Phase 5 features to a JosephApp instance.

    Usage:
        Phase5Integration.hook_into(app)  # After app is created
    """

    @staticmethod
    def hook_into(app):
        """Add all Phase 5 tabs and features to the given JosephApp instance."""
        required = ["colors", "_page_frames", "_nav_buttons", "_workspace_stack", "_nav_buttons_frame"]
        for attr in required:
            if not hasattr(app, attr):
                raise AttributeError(f"app missing required attribute: {attr}")

        new_tabs = [
            ("Engineering Assistant", Phase5Integration.build_engineering_tab),
            ("Tools & Permissions", Phase5Integration.build_tools_tab),
            ("Project Manager", Phase5Integration.build_projects_tab),
        ]

        for name, builder in new_tabs:
            frame = ctk.CTkFrame(
                app._workspace_stack,
                fg_color=app.colors["bg"],
                corner_radius=0,
            )
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_rowconfigure(0, weight=1)
            frame.grid_columnconfigure(0, weight=1)
            app._page_frames[name] = frame

            btn = ctk.CTkButton(
                app._nav_buttons_frame,
                text=name,
                height=34,
                font=FONTS["sidebar"],
                fg_color=app.colors["card"],
                hover_color=app.colors["border_light"],
                text_color=app.colors["text"],
                corner_radius=8,
                anchor="w",
                command=lambda p=name: app._show_page(p),
            )
            btn.pack(fill="x", pady=4)
            app._nav_buttons[name] = btn

            builder(app, frame)

        Phase5Integration._patch_voice_settings(app)
        logger.info(f"Phase 5 tabs added: {[t[0] for t in new_tabs]}")

    # ------------------------------------------------------------------ #
    # Engineering Assistant Tab
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_engineering_tab(app, parent):
        """Build the Engineering Assistant tab with analysis controls and results."""
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        colors = app.colors

        def _get_engineer():
            if not hasattr(app, "_engineering_assistant"):
                try:
                    from engineer.engineering_assistant import EngineeringAssistant
                    app._engineering_assistant = EngineeringAssistant(llm=app.llm)
                except Exception as e:
                    logger.error(f"Failed to init EngineeringAssistant: {e}")
                    return None
            return app._engineering_assistant

        # --- Top controls ---
        controls = ctk.CTkFrame(parent, fg_color=colors["panel"], corner_radius=0)
        controls.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        controls.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            controls,
            text="Project:",
            font=FONTS["sidebar_h"],
            text_color=colors["text_dim"],
        ).grid(row=0, column=0, padx=(14, 6), pady=10, sticky="w")

        dir_var = tk.StringVar(value=str(Path.cwd()))
        dir_entry = ctk.CTkEntry(
            controls,
            textvariable=dir_var,
            font=FONTS["body_sm"],
            height=28,
            fg_color=colors["input_bg"],
            border_color=colors["border"],
            text_color=colors["text"],
            corner_radius=6,
        )
        dir_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=10)

        ctk.CTkButton(
            controls,
            text="Browse",
            width=68,
            height=28,
            font=FONTS["sidebar"],
            fg_color=colors["card"],
            hover_color=colors["border_light"],
            text_color=colors["text"],
            corner_radius=5,
            command=lambda: _browse_dir(),
        ).grid(row=0, column=2, padx=(0, 14), pady=10)

        def _browse_dir():
            d = filedialog.askdirectory(title="Select project directory")
            if d:
                dir_var.set(d)

        # --- Analysis type + Run ---
        mid_row = ctk.CTkFrame(parent, fg_color=colors["panel"], corner_radius=0)
        mid_row.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        mid_row.grid_columnconfigure(0, weight=0)

        ctk.CTkLabel(
            mid_row,
            text="Analysis:",
            font=FONTS["sidebar_h"],
            text_color=colors["text_dim"],
        ).pack(side="left", padx=(14, 6), pady=8)

        analysis_var = tk.StringVar(value="Quick Summary")
        analysis_combo = ctk.CTkComboBox(
            mid_row,
            values=[
                "Quick Summary",
                "Full Report",
                "Bugs",
                "Architecture",
                "Dependencies",
                "Refactoring",
            ],
            variable=analysis_var,
            width=160,
            height=28,
            font=FONTS["body_sm"],
            fg_color=colors["input_bg"],
            border_color=colors["border"],
            button_color=colors["card"],
            button_hover_color=colors["border_light"],
            dropdown_fg_color=colors["panel"],
            dropdown_hover_color=colors["card"],
            dropdown_text_color=colors["text"],
            text_color=colors["text"],
            corner_radius=6,
        )
        analysis_combo.pack(side="left", padx=(0, 10), pady=8)

        status_label = ctk.CTkLabel(
            mid_row,
            text="Ready",
            font=FONTS["body_sm"],
            text_color=colors["text_dim"],
        )
        status_label.pack(side="right", padx=(0, 14), pady=8)

        spinner_label = ctk.CTkLabel(
            mid_row,
            text="",
            font=FONTS["body_sm"],
            text_color=colors["accent"],
        )
        spinner_label.pack(side="right", padx=(0, 6), pady=8)

        def _set_status(text, color=None):
            status_label.configure(text=text, text_color=color or colors["text_dim"])

        def _set_spinner(active):
            spinner_label.configure(text="⟳ Analyzing..." if active else "")

        run_btn = ctk.CTkButton(
            mid_row,
            text="Run Analysis",
            width=110,
            height=28,
            font=FONTS["sidebar"],
            fg_color=colors["accent"],
            hover_color=colors["accent_hover"],
            text_color="#ffffff",
            corner_radius=5,
            command=lambda: _run_analysis(),
        )
        run_btn.pack(side="left", padx=(0, 6), pady=8)

        # --- Results tab view ---
        result_tabs = ctk.CTkTabview(
            parent,
            fg_color=colors["panel"],
            segmented_button_fg_color=colors["card"],
            segmented_button_selected_color=colors["accent"],
            segmented_button_selected_hover_color=colors["accent_hover"],
            segmented_button_unselected_color=colors["card"],
            segmented_button_unselected_hover_color=colors["border_light"],
            text_color=colors["text"],
            corner_radius=8,
        )
        result_tabs.grid(row=2, column=0, sticky="nsew", padx=6, pady=6)
        result_tabs.grid_rowconfigure(0, weight=1)
        result_tabs.grid_columnconfigure(0, weight=1)

        tab_keys = ["Summary", "Architecture", "Dependencies", "Bugs", "Refactoring"]
        result_boxes = {}
        for key in tab_keys:
            tab_frame = result_tabs.add(key)
            tab_frame.grid_rowconfigure(0, weight=1)
            tab_frame.grid_columnconfigure(0, weight=1)
            box = ctk.CTkTextbox(
                tab_frame,
                font=FONTS["body_sm"],
                fg_color=colors["input_bg"],
                text_color=colors["text"],
                border_color=colors["border"],
                border_width=1,
                corner_radius=8,
                wrap="word",
            )
            box.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
            box.insert("end", "Run an analysis to see results here.")
            box.configure(state="disabled")
            result_boxes[key] = box

        def _set_box(key, content):
            if key in result_boxes:
                box = result_boxes[key]
                try:
                    box.configure(state="normal")
                    box.delete("1.0", "end")
                    box.insert("end", content or "No data.")
                    box.configure(state="disabled")
                except Exception:
                    pass

        def _run_analysis():
            directory = dir_var.get().strip()
            if not directory or not os.path.isdir(directory):
                _set_status("Invalid directory", colors["error"])
                return

            engine = _get_engineer()
            if not engine:
                _set_status("Engineering Assistant unavailable", colors["error"])
                return

            _set_status("Analyzing...", colors["warning"])
            _set_spinner(True)
            run_btn.configure(state="disabled")

            analysis_type = analysis_var.get()

            def _worker():
                try:
                    if analysis_type == "Quick Summary":
                        summary = engine.get_project_summary(directory)
                        _safe_ui(lambda: _set_box("Summary", summary))
                        for k in ["Architecture", "Dependencies", "Bugs", "Refactoring"]:
                            _safe_ui(lambda k=k: _set_box(k, "Run the specific analysis type for this report."))
                    elif analysis_type == "Full Report":
                        report = engine.get_full_report(directory)
                        sections = report.split("=" * 60)
                        labels = ["Full Report"]
                        for i, sec in enumerate(sections):
                            if i == 0:
                                _safe_ui(lambda: _set_box("Summary", sec.strip()))
                            elif i == 1:
                                _safe_ui(lambda: _set_box("Architecture", sec.strip()))
                            elif i == 2:
                                _safe_ui(lambda: _set_box("Dependencies", sec.strip()))
                            elif i == 3:
                                _safe_ui(lambda: _set_box("Bugs", sec.strip()))
                            elif i == 4:
                                _safe_ui(lambda: _set_box("Refactoring", sec.strip()))
                    elif analysis_type == "Bugs":
                        report = engine.get_bug_report(directory)
                        _safe_ui(lambda: _set_box("Bugs", report))
                        _safe_ui(lambda: _set_box("Summary", "Bug analysis complete."))
                    elif analysis_type == "Architecture":
                        report = engine.get_architecture_report(directory)
                        _safe_ui(lambda: _set_box("Architecture", report))
                        _safe_ui(lambda: _set_box("Summary", "Architecture analysis complete."))
                    elif analysis_type == "Dependencies":
                        report = engine.get_dependency_report(directory)
                        _safe_ui(lambda: _set_box("Dependencies", report))
                        _safe_ui(lambda: _set_box("Summary", "Dependency analysis complete."))
                    elif analysis_type == "Refactoring":
                        report = engine.get_refactoring_report(directory)
                        _safe_ui(lambda: _set_box("Refactoring", report))
                        _safe_ui(lambda: _set_box("Summary", "Refactoring analysis complete."))
                    _safe_ui(lambda: _set_status("Analysis complete", colors["success"]))
                except Exception as e:
                    logger.exception("Analysis failed")
                    _safe_ui(lambda e=e: _set_status(f"Error: {e}", colors["error"]))
                finally:
                    _safe_ui(lambda: _set_spinner(False))
                    _safe_ui(lambda: run_btn.configure(state="normal"))

            def _safe_ui(fn):
                app.after(0, fn)

            t = threading.Thread(target=_worker, daemon=True)
            t.start()

    # ------------------------------------------------------------------ #
    # Tools & Permissions Tab
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_tools_tab(app, parent):
        """Build the Tools & Permissions tab with registry, queue, and log."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        colors = app.colors

        def _get_pm():
            if not hasattr(app, "_phase5_pm"):
                try:
                    from tools.permission_manager import PermissionManager
                    app._phase5_pm = PermissionManager()
                except Exception as e:
                    logger.error(f"PermissionManager init: {e}")
                    return None
            return app._phase5_pm

        def _get_registry():
            if not hasattr(app, "_phase5_registry"):
                try:
                    from tools.registry import ToolRegistry
                    pm = _get_pm()
                    app._phase5_registry = ToolRegistry(permission_manager=pm)
                except Exception as e:
                    logger.error(f"ToolRegistry init: {e}")
                    return None
            return app._phase5_registry

        def _seed_tools():
            reg = _get_registry()
            if reg is None:
                return
            if reg.list_tools():
                return
            try:
                from tools.integration import create_tool_registry
                pm = _get_pm()
                full = create_tool_registry(permission_manager=pm)
                for t in full.list_tools():
                    reg.register(t)
                logger.info(f"Seeded {len(reg.list_tools())} tools into registry")
            except Exception as e:
                logger.warning(f"Tool seeding skipped: {e}")

        _seed_tools()

        tabview = ctk.CTkTabview(
            parent,
            fg_color=colors["bg"],
            segmented_button_fg_color=colors["card"],
            segmented_button_selected_color=colors["accent"],
            segmented_button_selected_hover_color=colors["accent_hover"],
            segmented_button_unselected_color=colors["card"],
            segmented_button_unselected_hover_color=colors["border_light"],
            text_color=colors["text"],
            corner_radius=0,
        )
        tabview.grid(row=0, column=0, sticky="nsew")

        # --- Tab 1: Tool Registry ---
        reg_frame = tabview.add("Tool Registry")
        reg_frame.grid_rowconfigure(0, weight=1)
        reg_frame.grid_columnconfigure(0, weight=1)

        reg_scroll = ctk.CTkScrollableFrame(
            reg_frame,
            fg_color=colors["panel"],
            scrollbar_button_color=colors["scrollbar"],
            scrollbar_button_hover_color=colors["border_light"],
            corner_radius=8,
        )
        reg_scroll.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        reg_scroll.grid_columnconfigure(0, weight=1)

        def _refresh_tool_list():
            for w in reg_scroll.winfo_children():
                w.destroy()
            reg = _get_registry()
            if not reg:
                ctk.CTkLabel(reg_scroll, text="Registry not available", text_color=colors["text_dim"]).pack(pady=20)
                return
            tools = reg.list_tools()
            if not tools:
                ctk.CTkLabel(reg_scroll, text="No tools registered.", text_color=colors["text_dim"]).pack(pady=20)
                return
            for tool in tools:
                level = tool.safety_level.value if hasattr(tool.safety_level, "value") else str(tool.safety_level)
                lcolor = SAFETY_COLORS.get(level, colors["text_dim"])
                card = ctk.CTkFrame(
                    reg_scroll,
                    fg_color=colors["card"],
                    corner_radius=8,
                    border_width=1,
                    border_color=colors["border"],
                )
                card.pack(fill="x", padx=8, pady=4)
                card.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(
                    card,
                    text=tool.name,
                    font=FONTS["name"],
                    text_color=colors["accent"],
                ).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 0))

                safety_label = ctk.CTkLabel(
                    card,
                    text=level.upper(),
                    font=FONTS["time"],
                    text_color=lcolor,
                )
                safety_label.grid(row=0, column=1, sticky="e", padx=10, pady=(6, 0))

                ctk.CTkLabel(
                    card,
                    text=tool.description or "",
                    font=FONTS["body_sm"],
                    text_color=colors["text_dim"],
                    wraplength=500,
                    justify="left",
                ).grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 6))

        _refresh_tool_list()

        # --- Tab 2: Permission Queue ---
        perm_frame = tabview.add("Permission Queue")
        perm_frame.grid_rowconfigure(1, weight=1)
        perm_frame.grid_columnconfigure(0, weight=1)

        perm_btn_row = ctk.CTkFrame(perm_frame, fg_color="transparent")
        perm_btn_row.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(
            perm_btn_row,
            text="Refresh Queue",
            width=100,
            height=28,
            font=FONTS["sidebar"],
            fg_color=colors["card"],
            hover_color=colors["border_light"],
            text_color=colors["text"],
            corner_radius=5,
            command=lambda: _refresh_perm_queue(),
        ).pack(side="left")

        perm_scroll = ctk.CTkScrollableFrame(
            perm_frame,
            fg_color=colors["panel"],
            scrollbar_button_color=colors["scrollbar"],
            scrollbar_button_hover_color=colors["border_light"],
            corner_radius=8,
        )
        perm_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        perm_scroll.grid_columnconfigure(0, weight=1)

        def _refresh_perm_queue():
            for w in perm_scroll.winfo_children():
                w.destroy()
            pm = _get_pm()
            if not pm:
                ctk.CTkLabel(perm_scroll, text="Permission manager not available", text_color=colors["text_dim"]).pack(pady=20)
                return
            requests = pm.get_pending_requests()
            if not requests:
                ctk.CTkLabel(perm_scroll, text="No pending permission requests.", text_color=colors["text_dim"]).pack(pady=20)
                return
            for req in requests:
                card = ctk.CTkFrame(
                    perm_scroll,
                    fg_color=colors["card"],
                    corner_radius=8,
                    border_width=1,
                    border_color=colors["border"],
                )
                card.pack(fill="x", padx=8, pady=4)
                card.grid_columnconfigure(1, weight=1)

                ctk.CTkLabel(
                    card,
                    text=req.tool_name,
                    font=FONTS["name"],
                    text_color=colors["accent"],
                ).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 0))

                params_str = ", ".join(f"{k}={v}" for k, v in (req.params or {}).items())
                ctk.CTkLabel(
                    card,
                    text=params_str,
                    font=FONTS["body_sm"],
                    text_color=colors["text_dim"],
                ).grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 4))

                btn_row = ctk.CTkFrame(card, fg_color="transparent")
                btn_row.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 6))

                rid = req.request_id
                ctk.CTkButton(
                    btn_row,
                    text="Approve",
                    width=70,
                    height=26,
                    font=FONTS["sidebar"],
                    fg_color=colors["success"],
                    hover_color="#2e9d5e",
                    text_color="#ffffff",
                    corner_radius=5,
                    command=lambda r=rid: _handle_perm(r, True),
                ).pack(side="left", padx=(0, 6))
                ctk.CTkButton(
                    btn_row,
                    text="Deny",
                    width=70,
                    height=26,
                    font=FONTS["sidebar"],
                    fg_color=colors["error"],
                    hover_color="#b94a4a",
                    text_color="#ffffff",
                    corner_radius=5,
                    command=lambda r=rid: _handle_perm(r, False),
                ).pack(side="left")

        def _handle_perm(request_id, approve):
            pm = _get_pm()
            if not pm:
                return
            if approve:
                pm.approve(request_id)
            else:
                pm.deny(request_id)
            _refresh_perm_queue()

        _refresh_perm_queue()

        # --- Tab 3: Execution Log ---
        log_frame = tabview.add("Execution Log")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        log_btn_row = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_btn_row.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(
            log_btn_row,
            text="Refresh Log",
            width=100,
            height=28,
            font=FONTS["sidebar"],
            fg_color=colors["card"],
            hover_color=colors["border_light"],
            text_color=colors["text"],
            corner_radius=5,
            command=lambda: _refresh_log(),
        ).pack(side="left")
        ctk.CTkButton(
            log_btn_row,
            text="Clear Log",
            width=80,
            height=28,
            font=FONTS["sidebar"],
            fg_color=colors["card"],
            hover_color=colors["border_light"],
            text_color=colors["text"],
            corner_radius=5,
            command=lambda: _clear_log(),
        ).pack(side="left", padx=(6, 0))

        log_text = ctk.CTkTextbox(
            log_frame,
            font=FONTS["mono"],
            fg_color=colors["input_bg"],
            text_color=colors["text"],
            border_color=colors["border"],
            border_width=1,
            corner_radius=8,
            wrap="none",
        )
        log_text.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        def _refresh_log():
            reg = _get_registry()
            if not reg:
                log_text.configure(state="normal")
                log_text.delete("1.0", "end")
                log_text.insert("end", "Registry not available.")
                log_text.configure(state="disabled")
                return
            log_entries = reg.get_execution_log(limit=100)
            log_text.configure(state="normal")
            log_text.delete("1.0", "end")
            if not log_entries:
                log_text.insert("end", "No tool executions yet.")
            else:
                lines = []
                for entry in reversed(log_entries):
                    ts = entry.get("timestamp", "")[11:19]
                    tool = entry.get("tool", "?")
                    status = "OK" if entry.get("success") else "FAIL"
                    elapsed = entry.get("elapsed_seconds", 0)
                    err = entry.get("error") or ""
                    lines.append(f"[{ts}] {status:4s} {tool} ({elapsed:.2f}s) {err}")
                log_text.insert("end", "\n".join(lines))
            log_text.configure(state="disabled")

        def _clear_log():
            reg = _get_registry()
            if reg:
                reg.clear_log()
            _refresh_log()

        _refresh_log()

        # --- Tab 4: Permission Settings ---
        settings_frame = tabview.add("Permission Settings")
        settings_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            settings_frame,
            text="Override Safety Level Per Tool",
            font=FONTS["name"],
            text_color=colors["accent"],
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(14, 8))

        ctk.CTkLabel(
            settings_frame,
            text="Tool Name:",
            font=FONTS["sidebar_h"],
            text_color=colors["text_dim"],
        ).grid(row=1, column=0, sticky="w", padx=14, pady=6)

        tool_name_var = tk.StringVar()
        tool_name_entry = ctk.CTkEntry(
            settings_frame,
            textvariable=tool_name_var,
            font=FONTS["body_sm"],
            height=28,
            fg_color=colors["input_bg"],
            border_color=colors["border"],
            text_color=colors["text"],
            corner_radius=6,
        )
        tool_name_entry.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=6)

        ctk.CTkLabel(
            settings_frame,
            text="Level:",
            font=FONTS["sidebar_h"],
            text_color=colors["text_dim"],
        ).grid(row=2, column=0, sticky="w", padx=14, pady=6)

        level_var = tk.StringVar(value="safe")
        level_combo = ctk.CTkComboBox(
            settings_frame,
            values=["safe", "confirm", "restricted", "dangerous"],
            variable=level_var,
            width=120,
            height=28,
            font=FONTS["body_sm"],
            fg_color=colors["input_bg"],
            border_color=colors["border"],
            button_color=colors["card"],
            button_hover_color=colors["border_light"],
            dropdown_fg_color=colors["panel"],
            dropdown_hover_color=colors["card"],
            dropdown_text_color=colors["text"],
            text_color=colors["text"],
            corner_radius=6,
        )
        level_combo.grid(row=2, column=1, sticky="w", padx=(0, 6), pady=6)

        def _set_override():
            pm = _get_pm()
            if not pm:
                return
            name = tool_name_var.get().strip()
            level_str = level_var.get().strip()
            if not name:
                return
            try:
                from tools.registry import SafetyLevel
                level = SafetyLevel(level_str)
                pm.set_tool_safety(name, level)
                _refresh_tool_list()
            except Exception as e:
                logger.error(f"Set override failed: {e}")

        ctk.CTkButton(
            settings_frame,
            text="Set Override",
            width=90,
            height=28,
            font=FONTS["sidebar"],
            fg_color=colors["accent"],
            hover_color=colors["accent_hover"],
            text_color="#ffffff",
            corner_radius=5,
            command=_set_override,
        ).grid(row=2, column=2, sticky="w", padx=(0, 14), pady=6)

        # --- Tab 5: Stats ---
        stats_frame = tabview.add("Stats")
        stats_frame.grid_rowconfigure(0, weight=1)
        stats_frame.grid_columnconfigure(0, weight=1)

        stats_text = ctk.CTkTextbox(
            stats_frame,
            font=FONTS["mono"],
            fg_color=colors["input_bg"],
            text_color=colors["text"],
            border_color=colors["border"],
            border_width=1,
            corner_radius=8,
            wrap="none",
        )
        stats_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        def _refresh_stats():
            reg = _get_registry()
            stats_text.configure(state="normal")
            stats_text.delete("1.0", "end")
            if not reg:
                stats_text.insert("end", "Registry not available.")
            else:
                s = reg.get_stats()
                lines = [
                    f"Total Executions: {s.get('total_executions', 0)}",
                    f"Successful: {s.get('successful', 0)}",
                    f"Failed: {s.get('failed', 0)}",
                    f"Registered Tools: {s.get('registered_tools', 0)}",
                    "",
                    "Usage by Tool:",
                ]
                for tool, count in s.get("tools_by_usage", {}).items():
                    lines.append(f"  {tool}: {count}")
                stats_text.insert("end", "\n".join(lines))
            stats_text.configure(state="disabled")

        _refresh_stats()

    # ------------------------------------------------------------------ #
    # Project Manager Tab
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_projects_tab(app, parent):
        """Build the Project Manager tab with sidebar list and detail views."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        colors = app.colors

        def _get_pm():
            if not hasattr(app, "_phase5_pmgr"):
                try:
                    from projects.project_manager import ProjectManager
                    app._phase5_pmgr = ProjectManager()
                except Exception as e:
                    logger.error(f"ProjectManager init: {e}")
                    return None
            return app._phase5_pmgr

        # --- Left sidebar: project list ---
        left_panel = ctk.CTkFrame(
            parent,
            fg_color=colors["panel"],
            corner_radius=0,
            width=220,
        )
        left_panel.grid(row=0, column=0, sticky="ns", padx=0, pady=0)
        left_panel.grid_propagate(False)
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        left_header = ctk.CTkFrame(left_panel, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        left_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            left_header,
            text="Projects",
            font=FONTS["name"],
            text_color=colors["accent"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            left_header,
            text="+",
            width=28,
            height=28,
            font=("Segoe UI", 14, "bold"),
            fg_color=colors["accent"],
            hover_color=colors["accent_hover"],
            text_color="#ffffff",
            corner_radius=5,
            command=lambda: _create_project_dialog(),
        ).grid(row=0, column=1, sticky="e")

        project_list = ctk.CTkScrollableFrame(
            left_panel,
            fg_color="transparent",
            scrollbar_button_color=colors["scrollbar"],
            scrollbar_button_hover_color=colors["border_light"],
            corner_radius=0,
        )
        project_list.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 8))
        project_list.grid_columnconfigure(0, weight=1)

        # --- Right side: detail view ---
        right_panel = ctk.CTkFrame(
            parent,
            fg_color=colors["bg"],
            corner_radius=0,
        )
        right_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        detail_header = ctk.CTkFrame(right_panel, fg_color=colors["panel"], corner_radius=0)
        detail_header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        detail_header.grid_columnconfigure(0, weight=1)

        detail_title_label = ctk.CTkLabel(
            detail_header,
            text="Select a project",
            font=FONTS["title"],
            text_color=colors["text"],
        )
        detail_title_label.grid(row=0, column=0, sticky="w", padx=14, pady=10)

        detail_btn_row = ctk.CTkFrame(detail_header, fg_color="transparent")
        detail_btn_row.grid(row=0, column=1, sticky="e", padx=14, pady=10)

        edit_btn = ctk.CTkButton(
            detail_btn_row,
            text="Edit",
            width=60,
            height=26,
            font=FONTS["sidebar"],
            fg_color=colors["card"],
            hover_color=colors["border_light"],
            text_color=colors["text"],
            corner_radius=5,
            command=lambda: _edit_project_dialog(),
        )
        edit_btn.pack(side="left", padx=(0, 6))

        delete_btn = ctk.CTkButton(
            detail_btn_row,
            text="Delete",
            width=60,
            height=26,
            font=FONTS["sidebar"],
            fg_color=colors["error"],
            hover_color="#b94a4a",
            text_color="#ffffff",
            corner_radius=5,
            command=lambda: _delete_project(),
        )
        delete_btn.pack(side="left")

        # Detail tab view
        detail_tabs = ctk.CTkTabview(
            right_panel,
            fg_color=colors["panel"],
            segmented_button_fg_color=colors["card"],
            segmented_button_selected_color=colors["accent"],
            segmented_button_selected_hover_color=colors["accent_hover"],
            segmented_button_unselected_color=colors["card"],
            segmented_button_unselected_hover_color=colors["border_light"],
            text_color=colors["text"],
            corner_radius=8,
        )
        detail_tabs.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        detail_tabs.grid_rowconfigure(0, weight=1)
        detail_tabs.grid_columnconfigure(0, weight=1)

        # Sub-tabs
        sub_tab_keys = ["Overview", "Goals", "Milestones", "Tasks", "Research"]
        sub_tab_data = {}
        for key in sub_tab_keys:
            frame = detail_tabs.add(key)
            frame.grid_rowconfigure(1, weight=1)
            frame.grid_columnconfigure(0, weight=1)
            box = ctk.CTkTextbox(
                frame,
                font=FONTS["body_sm"],
                fg_color=colors["input_bg"],
                text_color=colors["text"],
                border_color=colors["border"],
                border_width=1,
                corner_radius=8,
                wrap="word",
            )
            box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))

            add_btn_row = ctk.CTkFrame(frame, fg_color="transparent")
            add_btn_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
            ctk.CTkButton(
                add_btn_row,
                text=f"Add {key.rstrip('s')}",
                width=100,
                height=26,
                font=FONTS["sidebar"],
                fg_color=colors["accent"],
                hover_color=colors["accent_hover"],
                text_color="#ffffff",
                corner_radius=5,
                command=lambda k=key: _add_sub_item(k),
            ).pack(side="left")

            sub_tab_data[key] = box

        _selected_project_id = [None]

        def _refresh_project_list():
            for w in project_list.winfo_children():
                w.destroy()
            pm = _get_pm()
            if not pm:
                ctk.CTkLabel(project_list, text="Project Manager unavailable", text_color=colors["text_dim"]).pack(pady=20)
                return
            projects = pm.store.get_all_projects()
            if not projects:
                ctk.CTkLabel(project_list, text="No projects yet.\nClick + to create one.", text_color=colors["text_dim"], justify="center").pack(pady=20)
                return
            for p in projects:
                pid = p.id
                is_active = pid == _selected_project_id[0]
                btn = ctk.CTkButton(
                    project_list,
                    text=p.name,
                    anchor="w",
                    height=32,
                    font=FONTS["sidebar"],
                    fg_color=colors["accent"] if is_active else colors["card"],
                    hover_color=colors["border_light"],
                    text_color="#ffffff" if is_active else colors["text"],
                    corner_radius=6,
                    command=lambda pid=pid: _select_project(pid),
                )
                btn.pack(fill="x", padx=4, pady=2)

        def _select_project(pid):
            _selected_project_id[0] = pid
            pm = _get_pm()
            if not pm:
                return
            project = pm.store.get_project(pid)
            if not project:
                return
            detail_title_label.configure(text=project.name)
            _refresh_project_detail(pid)
            _refresh_project_list()

        def _refresh_project_detail(pid):
            pm = _get_pm()
            if not pm:
                return
            dashboard = pm.get_project_dashboard(pid)
            if "error" in dashboard:
                for box in sub_tab_data.values():
                    _set_tab_text(box, dashboard["error"])
                return

            # Overview
            proj = dashboard.get("project", {})
            goals_data = dashboard.get("goals", {})
            milestones_data = dashboard.get("milestones", {})
            tasks_data = dashboard.get("tasks", {})
            research_data = dashboard.get("research", {})

            overview_lines = [
                f"Name: {proj.get('name', '')}",
                f"Status: {proj.get('status', '')}",
                f"Description: {proj.get('description', '')}",
                f"Created: {str(proj.get('created_at', ''))[:10]}",
                "",
                f"Goals: {goals_data.get('count', 0)}  ({goals_data.get('stats', {}).get('by_status', {})})",
                f"Milestones: {milestones_data.get('count', 0)}",
                f"Tasks: {tasks_data.get('count', 0)}  ({tasks_data.get('stats', {}).get('by_status', {})})",
                f"Research Notes: {research_data.get('count', 0)}",
            ]
            # Add overdue
            overdue = milestones_data.get("overdue", [])
            if overdue:
                overview_lines.append("")
                overview_lines.append("Overdue Milestones:")
                for m in overdue:
                    overview_lines.append(f"  - {m.get('title')} (due {m.get('deadline', '')[:10]})")
            _set_tab_text(sub_tab_data["Overview"], "\n".join(overview_lines))

            # Goals
            goal_items = goals_data.get("items", [])
            goal_lines = []
            for g in goal_items:
                goal_lines.append(f"[{g.get('status', '')}] {g.get('title', '')} (priority: {g.get('priority', '')})")
            if not goal_lines:
                goal_lines.append("No goals defined.")
            _set_tab_text(sub_tab_data["Goals"], "\n".join(goal_lines))

            # Milestones
            ms_items = milestones_data.get("items", [])
            ms_lines = []
            for m in ms_items:
                dl = str(m.get("deadline", "") or "")[:10]
                ms_lines.append(f"[{m.get('status', '')}] {m.get('title', '')} (due: {dl})")
            if not ms_lines:
                ms_lines.append("No milestones defined.")
            _set_tab_text(sub_tab_data["Milestones"], "\n".join(ms_lines))

            # Tasks
            task_items = pm.tasks.get_tasks(pid)
            task_lines = []
            for t in task_items:
                due = str(t.due_date or "")[:10]
                task_lines.append(f"[{t.status}] {t.title} (priority: {t.priority})")
                if t.depends_on:
                    task_lines.append(f"  depends on: {', '.join(t.depends_on[:3])}")
            if not task_lines:
                task_lines.append("No tasks defined.")
            _set_tab_text(sub_tab_data["Tasks"], "\n".join(task_lines))

            # Research
            notes = pm.research.get_notes(pid)
            note_lines = []
            for n in notes:
                note_lines.append(f"[{n.relevance}/5] {n.title}")
                if n.source:
                    note_lines.append(f"  Source: {n.source}")
                if n.url:
                    note_lines.append(f"  URL: {n.url}")
                note_lines.append("")
            if not note_lines:
                note_lines.append("No research notes.")
            _set_tab_text(sub_tab_data["Research"], "\n".join(note_lines))

        def _set_tab_text(box, text):
            try:
                box.configure(state="normal")
                box.delete("1.0", "end")
                box.insert("end", text or "")
                box.configure(state="disabled")
            except Exception:
                pass

        def _create_project_dialog():
            pm = _get_pm()
            if not pm:
                return
            dialog = ctk.CTkToplevel(parent)
            dialog.title("Create Project")
            dialog.geometry("420x320")
            dialog.transient(parent)
            dialog.grab_set()
            dialog.configure(fg_color=colors["bg"])

            ctk.CTkLabel(dialog, text="Name:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(16, 4))
            name_var = tk.StringVar()
            ctk.CTkEntry(
                dialog,
                textvariable=name_var,
                font=FONTS["body_sm"],
                height=28,
                fg_color=colors["input_bg"],
                border_color=colors["border"],
                text_color=colors["text"],
                corner_radius=6,
            ).pack(fill="x", padx=16, pady=(0, 8))

            ctk.CTkLabel(dialog, text="Description:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(8, 4))
            desc_text = ctk.CTkTextbox(
                dialog,
                height=80,
                font=FONTS["body_sm"],
                fg_color=colors["input_bg"],
                text_color=colors["text"],
                border_color=colors["border"],
                border_width=1,
                corner_radius=6,
            )
            desc_text.pack(fill="x", padx=16, pady=(0, 8))

            ctk.CTkLabel(dialog, text="Path (optional):", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(8, 4))
            path_var = tk.StringVar()
            ctk.CTkEntry(
                dialog,
                textvariable=path_var,
                font=FONTS["body_sm"],
                height=28,
                fg_color=colors["input_bg"],
                border_color=colors["border"],
                text_color=colors["text"],
                corner_radius=6,
            ).pack(fill="x", padx=16, pady=(0, 12))

            btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_row.pack(fill="x", padx=16, pady=(0, 16))

            def _do_create():
                name = name_var.get().strip()
                if not name:
                    return
                desc = desc_text.get("1.0", "end-1c").strip()
                path = path_var.get().strip() or None
                pm.store.create_project(name, desc, path=path)
                dialog.destroy()
                _refresh_project_list()
                projects = pm.store.get_all_projects()
                if projects:
                    _select_project(projects[-1].id)

            ctk.CTkButton(
                btn_row,
                text="Cancel",
                width=80,
                height=28,
                font=FONTS["sidebar"],
                fg_color=colors["card"],
                hover_color=colors["border_light"],
                text_color=colors["text"],
                corner_radius=5,
                command=dialog.destroy,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                btn_row,
                text="Create",
                width=80,
                height=28,
                font=FONTS["sidebar"],
                fg_color=colors["accent"],
                hover_color=colors["accent_hover"],
                text_color="#ffffff",
                corner_radius=5,
                command=_do_create,
            ).pack(side="left")

        def _edit_project_dialog():
            pid = _selected_project_id[0]
            if not pid:
                return
            pm = _get_pm()
            if not pm:
                return
            project = pm.store.get_project(pid)
            if not project:
                return

            dialog = ctk.CTkToplevel(parent)
            dialog.title("Edit Project")
            dialog.geometry("420x320")
            dialog.transient(parent)
            dialog.grab_set()
            dialog.configure(fg_color=colors["bg"])

            ctk.CTkLabel(dialog, text="Name:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(16, 4))
            name_var = tk.StringVar(value=project.name)
            ctk.CTkEntry(
                dialog,
                textvariable=name_var,
                font=FONTS["body_sm"],
                height=28,
                fg_color=colors["input_bg"],
                border_color=colors["border"],
                text_color=colors["text"],
                corner_radius=6,
            ).pack(fill="x", padx=16, pady=(0, 8))

            ctk.CTkLabel(dialog, text="Description:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(8, 4))
            desc_text = ctk.CTkTextbox(
                dialog,
                height=80,
                font=FONTS["body_sm"],
                fg_color=colors["input_bg"],
                text_color=colors["text"],
                border_color=colors["border"],
                border_width=1,
                corner_radius=6,
            )
            desc_text.pack(fill="x", padx=16, pady=(0, 8))
            desc_text.insert("1.0", project.description)

            ctk.CTkLabel(dialog, text="Status:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(8, 4))
            status_var = tk.StringVar(value=project.status)
            ctk.CTkComboBox(
                dialog,
                values=["active", "archived", "completed"],
                variable=status_var,
                width=140,
                height=28,
                font=FONTS["body_sm"],
                fg_color=colors["input_bg"],
                border_color=colors["border"],
                button_color=colors["card"],
                button_hover_color=colors["border_light"],
                text_color=colors["text"],
                corner_radius=6,
            ).pack(anchor="w", padx=16, pady=(0, 12))

            btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_row.pack(fill="x", padx=16, pady=(0, 16))

            def _do_update():
                name = name_var.get().strip()
                if not name:
                    return
                desc = desc_text.get("1.0", "end-1c").strip()
                status = status_var.get()
                pm.store.update_project(pid, name=name, description=desc, status=status)
                dialog.destroy()
                _select_project(pid)

            ctk.CTkButton(
                btn_row,
                text="Cancel",
                width=80,
                height=28,
                font=FONTS["sidebar"],
                fg_color=colors["card"],
                hover_color=colors["border_light"],
                text_color=colors["text"],
                corner_radius=5,
                command=dialog.destroy,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                btn_row,
                text="Save",
                width=80,
                height=28,
                font=FONTS["sidebar"],
                fg_color=colors["accent"],
                hover_color=colors["accent_hover"],
                text_color="#ffffff",
                corner_radius=5,
                command=_do_update,
            ).pack(side="left")

        def _delete_project():
            pid = _selected_project_id[0]
            if not pid:
                return
            pm = _get_pm()
            if not pm:
                return
            project = pm.store.get_project(pid)
            if not project:
                return
            if not messagebox.askyesno("Delete Project", f"Permanently delete '{project.name}'?", parent=parent):
                return
            pm.store.delete_project(pid)
            pm.goals.delete_goal(pid)
            _selected_project_id[0] = None
            detail_title_label.configure(text="Select a project")
            for box in sub_tab_data.values():
                _set_tab_text(box, "Project deleted.")
            _refresh_project_list()

        def _add_sub_item(key):
            pid = _selected_project_id[0]
            if not pid:
                return
            pm = _get_pm()
            if not pm:
                return

            if key == "Overview":
                return
            label = key.rstrip("s")

            dialog = ctk.CTkToplevel(parent)
            dialog.title(f"Add {label}")
            dialog.geometry("400x300")
            dialog.transient(parent)
            dialog.grab_set()
            dialog.configure(fg_color=colors["bg"])

            ctk.CTkLabel(dialog, text=f"Title:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(16, 4))
            title_var = tk.StringVar()
            ctk.CTkEntry(
                dialog,
                textvariable=title_var,
                font=FONTS["body_sm"],
                height=28,
                fg_color=colors["input_bg"],
                border_color=colors["border"],
                text_color=colors["text"],
                corner_radius=6,
            ).pack(fill="x", padx=16, pady=(0, 8))

            extra_widgets = []
            if key in ("Tasks",):
                ctk.CTkLabel(dialog, text="Priority:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(8, 4))
                pri_var = tk.StringVar(value="medium")
                pri_combo = ctk.CTkComboBox(
                    dialog,
                    values=["low", "medium", "high", "critical"],
                    variable=pri_var,
                    width=120,
                    height=28,
                    font=FONTS["body_sm"],
                    fg_color=colors["input_bg"],
                    border_color=colors["border"],
                    button_color=colors["card"],
                    button_hover_color=colors["border_light"],
                    text_color=colors["text"],
                    corner_radius=6,
                )
                pri_combo.pack(anchor="w", padx=16, pady=(0, 8))
                extra_widgets.append(("priority", pri_var))

            if key in ("Goals", "Milestones", "Tasks"):
                ctk.CTkLabel(dialog, text="Deadline / Due (YYYY-MM-DD):", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(8, 4))
                date_var = tk.StringVar()
                ctk.CTkEntry(
                    dialog,
                    textvariable=date_var,
                    font=FONTS["body_sm"],
                    height=28,
                    fg_color=colors["input_bg"],
                    border_color=colors["border"],
                    text_color=colors["text"],
                    corner_radius=6,
                ).pack(fill="x", padx=16, pady=(0, 12))
                extra_widgets.append(("deadline", date_var))

            if key == "Research":
                ctk.CTkLabel(dialog, text="Content:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(8, 4))
                content_text = ctk.CTkTextbox(
                    dialog,
                    height=80,
                    font=FONTS["body_sm"],
                    fg_color=colors["input_bg"],
                    text_color=colors["text"],
                    border_color=colors["border"],
                    border_width=1,
                    corner_radius=6,
                )
                content_text.pack(fill="x", padx=16, pady=(0, 8))
                extra_widgets.append(("content", content_text))

                ctk.CTkLabel(dialog, text="URL:", font=FONTS["sidebar_h"], text_color=colors["text_dim"]).pack(anchor="w", padx=16, pady=(8, 4))
                url_var = tk.StringVar()
                ctk.CTkEntry(
                    dialog,
                    textvariable=url_var,
                    font=FONTS["body_sm"],
                    height=28,
                    fg_color=colors["input_bg"],
                    border_color=colors["border"],
                    text_color=colors["text"],
                    corner_radius=6,
                ).pack(fill="x", padx=16, pady=(0, 12))
                extra_widgets.append(("url", url_var))

            btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_row.pack(fill="x", padx=16, pady=(0, 16))

            def _do_add():
                title = title_var.get().strip()
                if not title:
                    return
                try:
                    if key == "Goals":
                        pm.goals.add_goal(pid, title=title, deadline=date_var.get().strip() or None)
                    elif key == "Milestones":
                        pm.milestones.add_milestone(pid, title=title, deadline=date_var.get().strip() or None)
                    elif key == "Tasks":
                        pm.tasks.add_task(pid, title=title, priority=pri_var.get(), due_date=date_var.get().strip() or None)
                    elif key == "Research":
                        content = content_text.get("1.0", "end-1c").strip()
                        url = url_var.get().strip() or None
                        pm.research.add_note(pid, title=title, content=content, url=url)
                except Exception as e:
                    logger.error(f"Add {key} failed: {e}")
                dialog.destroy()
                _refresh_project_detail(pid)

            ctk.CTkButton(
                btn_row,
                text="Cancel",
                width=80,
                height=28,
                font=FONTS["sidebar"],
                fg_color=colors["card"],
                hover_color=colors["border_light"],
                text_color=colors["text"],
                corner_radius=5,
                command=dialog.destroy,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                btn_row,
                text="Add",
                width=80,
                height=28,
                font=FONTS["sidebar"],
                fg_color=colors["accent"],
                hover_color=colors["accent_hover"],
                text_color="#ffffff",
                corner_radius=5,
                command=_do_add,
            ).pack(side="left")

        _refresh_project_list()

    # ------------------------------------------------------------------ #
    # Enhanced Voice Settings
    # ------------------------------------------------------------------ #

    @staticmethod
    def _patch_voice_settings(app):
        """Add enhanced voice settings to the existing Settings tab."""
        if not hasattr(app, "_settings_tab"):
            logger.warning("Settings tab not found, skipping voice settings patch")
            return

        colors = app.colors
        parent = app._settings_tab

        if not hasattr(app, "_phase5_voice_patched"):
            app._phase5_voice_patched = False
        if app._phase5_voice_patched:
            return

        card = ctk.CTkFrame(
            parent,
            fg_color=colors["panel"],
            corner_radius=12,
            border_width=1,
            border_color=colors["border"],
        )
        card.grid(row=99, column=0, sticky="ew", padx=6, pady=(8, 4))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="Enhanced Voice",
            font=FONTS["name"],
            text_color=colors["accent"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6))

        voice_vars = {}

        # Wake word
        row = 1
        ctk.CTkLabel(
            card,
            text="Wake Word",
            font=FONTS["sidebar"],
            text_color=colors["text_dim"],
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        wake_var = tk.StringVar(value=getattr(app, "_voice", None) and getattr(app._voice, "wake_word", "") or "joseph")
        wake_entry = ctk.CTkEntry(
            card,
            textvariable=wake_var,
            font=FONTS["body_sm"],
            height=28,
            fg_color=colors["input_bg"],
            border_color=colors["border"],
            text_color=colors["text"],
            corner_radius=6,
        )
        wake_entry.grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        voice_vars["wake_word"] = wake_var

        # Push-to-talk vs always-on
        row = 2
        ctk.CTkLabel(
            card,
            text="Push-to-Talk",
            font=FONTS["sidebar"],
            text_color=colors["text_dim"],
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        ptt_var = tk.BooleanVar(value=False)
        ptt_switch = ctk.CTkSwitch(
            card,
            text="",
            variable=ptt_var,
            onvalue=True,
            offvalue=False,
            command=lambda: _on_ptt_change(),
        )
        ptt_switch.grid(row=row, column=1, sticky="w", padx=12, pady=6)
        voice_vars["push_to_talk"] = ptt_var

        def _on_ptt_change():
            pass

        # Auto-speak responses
        row = 3
        ctk.CTkLabel(
            card,
            text="Auto-speak Responses",
            font=FONTS["sidebar"],
            text_color=colors["text_dim"],
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        speak_var = tk.BooleanVar(value=True)
        ctk.CTkSwitch(
            card,
            text="",
            variable=speak_var,
            onvalue=True,
            offvalue=False,
        ).grid(row=row, column=1, sticky="w", padx=12, pady=6)
        voice_vars["auto_speak"] = speak_var

        app._phase5_voice_vars = voice_vars
        app._phase5_voice_patched = True
        logger.info("Enhanced Voice settings added to Settings tab")
