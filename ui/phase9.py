"""
ui/phase9.py
---------------
Phase 9 UI widgets — Vision, Document Intelligence, and Computer Awareness.

Frames:
- DocumentsView: document analysis and research notes
- VisionView: image upload and analysis
- AnalysisView: combined analysis results
- Phase9Integration: hooks all into JosephApp
"""

import logging
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

logger = logging.getLogger(__name__)


class DocumentIntelligenceFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Document analysis UI."""

    def __init__(self, master, document_intelligence=None, paper_analyzer=None,
                 research_workspace=None, **kwargs):
        super().__init__(master, **kwargs)
        self._di = document_intelligence
        self._pa = paper_analyzer
        self._rw = research_workspace
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Document Intelligence",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            self, text="Analyze PDF, DOCX, TXT, Markdown, and code files.",
            font=("Segoe UI", 10), text_color="gray", anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 8))

        # Controls
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=8, pady=4)

        self._open_btn = ctk.CTkButton(
            ctrl_frame, text="Open Document",
            command=self._on_open, width=140,
        )
        self._open_btn.pack(side="left", padx=(0, 8))

        self._analyze_type = tk.StringVar(value="Analyze")
        self._analyze_menu = ctk.CTkOptionMenu(
            ctrl_frame, variable=self._analyze_type,
            values=["Analyze", "Paper Analysis", "Research Notes"],
            width=140,
        )
        self._analyze_menu.pack(side="left", padx=(0, 8))

        self._save_btn = ctk.CTkButton(
            ctrl_frame, text="Save to Research",
            command=self._on_save, width=140,
            fg_color="#555",
        )
        self._save_btn.pack(side="left")

        self._file_label = ctk.CTkLabel(
            self, text="No file selected", font=("Segoe UI", 9),
            text_color="gray", anchor="w",
        )
        self._file_label.pack(fill="x", padx=8, pady=2)

        self._content = ctk.CTkTextbox(
            self, wrap="word", font=("Consolas", 11),
            fg_color="#1a1a1a", text_color="#e0e0e0",
        )
        self._content.pack(fill="both", expand=True, padx=8, pady=4)

        self._current_path = ""
        self._current_analysis = ""

    def refresh(self, document_intelligence=None, paper_analyzer=None):
        if document_intelligence:
            self._di = document_intelligence
        if paper_analyzer:
            self._pa = paper_analyzer

    def _on_open(self):
        path = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[
                ("Documents", "*.pdf *.docx *.txt *.md"),
                ("Code", "*.py *.js *.ts *.rs *.c *.cpp *.java"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        self._current_path = path
        self._file_label.configure(text=f"File: {os.path.basename(path)}")
        self._analyze_file(path)

    def _analyze_file(self, path: str):
        self._content.delete("1.0", "end")
        self._content.insert("1.0", f"Analyzing {os.path.basename(path)}...\n")
        self.update_idletasks()

        mode = self._analyze_type.get()

        try:
            if mode == "Paper Analysis" and self._pa:
                result = self._pa.create_research_entry(path)
            elif mode == "Research Notes" and self._di:
                result = self._di.generate_research_notes(path)
            else:
                if self._di:
                    result_obj = self._di.analyze(path)
                    if result_obj.error:
                        result = f"Error: {result_obj.error}"
                    else:
                        lines = [
                            f"File: {os.path.basename(path)}",
                            f"Type: {result_obj.file_type}",
                            f"Words: {result_obj.word_count}",
                            "",
                        ]
                        if result_obj.summary:
                            lines.append("## Summary")
                            lines.append(result_obj.summary)
                            lines.append("")
                        if result_obj.key_points:
                            lines.append("## Key Points")
                            for p in result_obj.key_points:
                                lines.append(f"- {p}")
                            lines.append("")
                        if result_obj.topics:
                            lines.append("## Topics")
                            lines.append(", ".join(result_obj.topics))
                            lines.append("")
                        result = "\n".join(lines)
                else:
                    result = "Document Intelligence engine not available."

            self._current_analysis = result
            self._content.delete("1.0", "end")
            self._content.insert("1.0", result)

        except Exception as e:
            self._content.delete("1.0", "end")
            self._content.insert("1.0", f"Analysis failed: {e}")

    def _on_save(self):
        if not self._current_analysis or not self._rw:
            return
        try:
            self._rw.add_entry(
                query=f"Document: {os.path.basename(self._current_path)}",
                notes=self._current_analysis[:2000],
            )
            logger.info("Document analysis saved to research workspace")
        except Exception as e:
            logger.warning(f"Save failed: {e}")


class VisionAnalysisFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Image analysis UI."""

    def __init__(self, master, vision_engine=None, diagram_analyzer=None,
                 code_vision=None, **kwargs):
        super().__init__(master, **kwargs)
        self._ve = vision_engine
        self._da = diagram_analyzer
        self._cv = code_vision
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Vision & Image Analysis",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            self, text="Analyze images, screenshots, diagrams, and code screenshots.",
            font=("Segoe UI", 10), text_color="gray", anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 8))

        # Controls
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=8, pady=4)

        self._open_btn = ctk.CTkButton(
            ctrl_frame, text="Open Image",
            command=self._on_open, width=120,
        )
        self._open_btn.pack(side="left", padx=(0, 8))

        self._mode_var = tk.StringVar(value="Describe")
        self._mode_menu = ctk.CTkOptionMenu(
            ctrl_frame, variable=self._mode_var,
            values=["Describe", "Screenshot", "Diagram", "Code", "Chart"],
            width=120,
        )
        self._mode_menu.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            ctrl_frame, text="Multimodal:",
            font=("Segoe UI", 9), text_color="gray",
        ).pack(side="left", padx=(8, 4))

        self._mm_status = ctk.CTkLabel(
            ctrl_frame, text="checking...",
            font=("Segoe UI", 9), text_color="#d4924a",
        )
        self._mm_status.pack(side="left")

        self._file_label = ctk.CTkLabel(
            self, text="No image selected", font=("Segoe UI", 9),
            text_color="gray", anchor="w",
        )
        self._file_label.pack(fill="x", padx=8, pady=2)

        self._content = ctk.CTkTextbox(
            self, wrap="word", font=("Consolas", 11),
            fg_color="#1a1a1a", text_color="#e0e0e0",
        )
        self._content.pack(fill="both", expand=True, padx=8, pady=4)

        self._current_path = ""

        # Check multimodal availability
        self._check_multimodal()

    def refresh(self, vision_engine=None, diagram_analyzer=None, code_vision=None):
        if vision_engine:
            self._ve = vision_engine
        if diagram_analyzer:
            self._da = diagram_analyzer
        if code_vision:
            self._cv = code_vision
        self._check_multimodal()

    def _check_multimodal(self):
        if not self._ve:
            self._mm_status.configure(text="not available", text_color="#d95f5f")
            return
        try:
            avail = self._ve.check_multimodal()
            if avail:
                self._mm_status.configure(text="available", text_color="#3dba7a")
            else:
                self._mm_status.configure(text="not found", text_color="#d4924a")
        except Exception:
            self._mm_status.configure(text="error", text_color="#d95f5f")

    def _on_open(self):
        path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        self._current_path = path
        self._file_label.configure(
            text=f"Image: {os.path.basename(path)} ({self._format_size(os.path.getsize(path))})"
        )
        self._analyze_image(path)

    def _analyze_image(self, path: str):
        self._content.delete("1.0", "end")
        self._content.insert("1.0", f"Analyzing {os.path.basename(path)}...\n")
        self.update_idletasks()

        mode = self._mode_var.get()

        try:
            if mode == "Diagram" and self._da:
                result = self._da.explain(path)
            elif mode == "Code" and self._cv:
                analysis = self._cv.analyze_code_image(path)
                lines = [f"Language: {analysis.language}"]
                if analysis.code:
                    lines.append(f"\nExtracted Code:\n{analysis.code[:2000]}")
                if analysis.explanation:
                    lines.append(f"\nExplanation:\n{analysis.explanation}")
                if analysis.bugs:
                    lines.append(f"\nPotential Issues:")
                    for b in analysis.bugs:
                        lines.append(f"  - {b}")
                if analysis.suggestions:
                    lines.append(f"\nSuggestions:")
                    for s in analysis.suggestions:
                        lines.append(f"  - {s}")
                result = "\n".join(lines)
            elif mode == "Screenshot" and self._ve:
                vresult = self._ve.analyze_screenshot(path)
                result = vresult.description or "No description generated."
            elif mode == "Chart" and self._ve:
                vresult = self._ve.analyze_chart(path)
                result = vresult.description or "No description generated."
            else:
                if self._ve:
                    vresult = self._ve.describe(path)
                    result = vresult.description or "No description generated."
                    if vresult.error:
                        result = f"Error: {vresult.error}"
                else:
                    result = "Vision engine not available."

            self._content.delete("1.0", "end")
            self._content.insert("1.0", result)

        except Exception as e:
            self._content.delete("1.0", "end")
            self._content.insert("1.0", f"Analysis failed: {e}")

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB"):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}GB"


class AnalysisLogFrame(ctk.CTkScrollableFrame if ctk else tk.Frame):
    """Combined analysis results log."""

    def __init__(self, master, multimodal_memory=None, **kwargs):
        super().__init__(master, **kwargs)
        self._mm = multimodal_memory
        self._build_ui()

    def _build_ui(self):
        self._header = ctk.CTkLabel(
            self, text="Multimodal Memory",
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self._header.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            self, text="Stored images, documents, and analysis results.",
            font=("Segoe UI", 10), text_color="gray", anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 8))

        self._stats_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 10), text_color="gray", anchor="w",
        )
        self._stats_label.pack(fill="x", padx=8, pady=4)

        self._results_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._results_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._refresh()

    def refresh(self, multimodal_memory=None):
        if multimodal_memory:
            self._mm = multimodal_memory
        self._refresh()

    def _refresh(self):
        for w in self._results_frame.winfo_children():
            w.destroy()

        if not self._mm:
            ctk.CTkLabel(
                self._results_frame, text="Multimodal memory not available.",
                text_color="gray",
            ).pack(pady=20)
            return

        stats = self._mm.get_stats()
        self._stats_label.configure(
            text=f"{stats['total_entries']} media entries "
            f"({', '.join(f'{k}: {v}' for k, v in stats['by_type'].items())})"
        )

        entries = self._mm.get_recent(limit=20)
        if not entries:
            ctk.CTkLabel(
                self._results_frame, text="No media stored yet.",
                text_color="gray",
            ).pack(pady=20)
            return

        for entry in entries:
            frame = ctk.CTkFrame(
                self._results_frame, fg_color="#252525", corner_radius=4,
            )
            frame.pack(fill="x", pady=2, padx=4)

            ctk.CTkLabel(
                frame, text=f"[{entry.media_type}] {os.path.basename(entry.path)}",
                font=("Segoe UI", 10, "bold"), anchor="w",
            ).pack(fill="x", padx=8, pady=(4, 0))

            if entry.description:
                ctk.CTkLabel(
                    frame, text=entry.description[:100],
                    font=("Segoe UI", 9), text_color="#ccc", anchor="w",
                    wraplength=400,
                ).pack(fill="x", padx=8)

            meta = entry.created_at[:10]
            if entry.project_id:
                meta += f" | Project: {entry.project_id[:8]}"
            if entry.tags:
                meta += f" | {' '.join(entry.tags)}"
            ctk.CTkLabel(
                frame, text=meta,
                font=("Segoe UI", 8), text_color="#888", anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 4))


# ------------------------------------------------------------------ #
# Phase 9 Integration
# ------------------------------------------------------------------ #

class Phase9Integration:
    """
    Hooks Phase 9 widgets into JosephApp.

    Adds 3 new pages: Documents, Vision, Analysis.
    """

    @staticmethod
    def hook_into(app):
        if ctk is None:
            logger.warning("customtkinter not available, skipping Phase 9 UI")
            return

        try:
            pages = [
                ("Documents", DocumentIntelligenceFrame, {
                    "document_intelligence": getattr(app, "_document_intelligence", None),
                    "paper_analyzer": getattr(app, "_paper_analyzer", None),
                    "research_workspace": getattr(app, "_research_workspace", None),
                }),
                ("Vision", VisionAnalysisFrame, {
                    "vision_engine": getattr(app, "_vision_engine", None),
                    "diagram_analyzer": getattr(app, "_diagram_analyzer", None),
                    "code_vision": getattr(app, "_code_vision", None),
                }),
                ("Analysis", AnalysisLogFrame, {
                    "multimodal_memory": getattr(app, "_multimodal_memory", None),
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

                ref_name = f"_phase9_{page_name.lower()}"
                setattr(app, ref_name, frame)

            logger.info("Phase 9 integration complete")
        except Exception as e:
            logger.warning(f"Phase 9 integration failed: {e}")
