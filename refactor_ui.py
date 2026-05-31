"""
Comprehensive Phase 4 UI refactoring script.
Applies all changes to ui/app.py in one pass.
"""
import re, os, shutil

SRC = r'C:\Users\Grayson\Desktop\Joseph\ui\app.py'
BAK = SRC + '.bak2'
# We already have .bak from the first backup, use .bak2
shutil.copy2(SRC, BAK)
print(f"Backed up to {BAK}")

with open(SRC, 'r', encoding='utf-8') as f:
    content = f.read()

original = content
changes = 0

# ============================================================
# 1. Replace COLORS dict with THEMES (dark + light)
# ============================================================
old_colors = '''COLORS = {
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
}'''

new_colors = '''THEMES = {
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
}'''

if old_colors in content:
    content = content.replace(old_colors, new_colors)
    changes += 1
    print("1. COLORS -> THEMES: done")
else:
    print("1. COLORS -> THEMES: NOT FOUND (may already be applied)")
    # Check if THEMES already exists
    if "THEMES" in content:
        print("   (THEMES already present)")

# ============================================================
# 2. Add theme-related instance vars in __init__
# ============================================================
# After `self._font_scale = float(...` add self.colors
init_marker = "self._font_scale = float(self._layout_state.get(\"font_scale\", 1.0))"
theme_vars = '''        self.colors = dict(THEMES[self._theme_name])
        self._graph_pan_offset_x = 0
        self._graph_pan_offset_y = 0
        self._graph_pan_start_pos = None
        self._graph_drag_start = None'''

if init_marker in content:
    content = content.replace(init_marker, init_marker + '\n' + theme_vars)
    changes += 1
    print("2. Added theme vars: done")
else:
    print("2. Added theme vars: marker not found")

# ============================================================
# 3. Replace all COLORS[ references with self.colors[
# ============================================================
count_colors_ref = content.count("COLORS[")
count_colors_dot = content.count("COLORS.")
content = content.replace("COLORS[", "self.colors[")
content = content.replace("COLORS.", "self.colors.")
if count_colors_ref > 0 or count_colors_dot > 0:
    print(f"3. Replaced COLORS references: {count_colors_ref + count_colors_dot}")
    changes += 1

# ============================================================
# 4. Replace all COLORS_ references (if any remain)
# ============================================================
# None should remain after step 3

# ============================================================
# 5. Add _apply_theme method after _apply_layout_state
# ============================================================
apply_marker = "        self._sync_panel_controls()"
# Find the _apply_layout_state method - it's called from _apply_layout_state
# Let's find the end of _normalize_theme_mode and add _apply_theme before it

theme_add = '''
    def _apply_theme(self):
        """Apply current theme to all runtime colors."""
        self.colors.update(THEMES[self._theme_name])
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
            self._refresh_context_panel()
            self._update_sidebar()
        except Exception:
            pass

'''

# Insert after the _normalize_theme_mode method (before its next method)
norm_marker = "        return \"dark\"\n\n"
norm_replacement = norm_marker + theme_add

if norm_marker in content:
    content = content.replace(norm_marker, norm_replacement, 1)
    print("5. Added _apply_theme methods: done")
    changes += 1
else:
    print("5. _apply_theme methods: marker not found")

# ============================================================
# 6. Modify _apply_layout_state to call _apply_theme
# ============================================================
old_apply = '''        self._theme_mode = self._normalize_theme_mode(self._theme_mode)
            ctk.set_appearance_mode(self._theme_mode)'''
new_apply = '''        self._theme_mode = self._normalize_theme_mode(self._theme_mode)
            ctk.set_appearance_mode(self._theme_mode)
            self._apply_theme()'''

if old_apply in content:
    content = content.replace(old_apply, new_apply)
    print("6. _apply_layout_state calls _apply_theme: done")
    changes += 1
else:
    print("6. _apply_layout_state: pattern not found")

# ============================================================
# 7. Replace B1-Motion in graph for panning (replace graph canvas binds)
# ============================================================
# Add wheel zoom and pan to graph canvas
old_graph_bind = '''        self._graph_canvas.bind("<Button-1>", self._on_graph_click)'''
new_graph_bind = '''        self._graph_canvas.bind("<Button-1>", self._on_graph_click)
        self._graph_canvas.bind("<MouseWheel>", self._on_graph_scroll)
        self._graph_canvas.bind("<ButtonPress-3>", self._on_graph_pan_start)
        self._graph_canvas.bind("<B3-Motion>", self._on_graph_pan_move)'''

if old_graph_bind in content:
    content = content.replace(old_graph_bind, new_graph_bind)
    print("7. Graph canvas binds (wheel + pan): done")
    changes += 1
else:
    print("7. Graph canvas binds: not found")

# ============================================================
# 8. Add _on_graph_scroll and _on_graph_pan methods after _set_graph_zoom
# ============================================================
zoom_end = '''    def _set_graph_zoom(self, value: float):
        self._graph_zoom = float(value)
        self._refresh_graph_tab()'''

zoom_replace = '''    def _set_graph_zoom(self, value: float):
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

    def _on_graph_pan_start(self, event):
        self._graph_pan_start_pos = (event.x, event.y)

    def _on_graph_pan_move(self, event):
        if self._graph_pan_start_pos:
            dx = event.x - self._graph_pan_start_pos[0]
            dy = event.y - self._graph_pan_start_pos[1]
            self._graph_pan_offset_x += dx
            self._graph_pan_offset_y += dy
            self._graph_pan_start_pos = (event.x, event.y)
            self._refresh_graph_tab()'''

if zoom_end in content:
    content = content.replace(zoom_end, zoom_replace, 1)
    print("8. Graph zoom/pan methods: done")
    changes += 1
else:
    print("8. Graph zoom/pan: not found")

# ============================================================
# 9. Update _refresh_graph_tab to use pan offsets
# ============================================================
# Find the center_x/y lines and add pan offset
old_center = '''        center_x = width / 2
        center_y = height / 2'''
new_center = '''        center_x = width / 2 + getattr(self, '_graph_pan_offset_x', 0)
        center_y = height / 2 + getattr(self, '_graph_pan_offset_y', 0)'''

if old_center in content:
    content = content.replace(old_center, new_center)
    print("9. Graph pan offsets: done")
    changes += 1
else:
    print("9. Graph pan offsets: not found")

# ============================================================
# 10. Add copy/regenerate buttons to message bubbles
# ============================================================
# Find the rating buttons section and add copy/regenerate before it
old_rating = '''    def _add_rating_buttons(self, parent, textbox: ctk.CTkTextbox) -> None:
        """Add rating buttons below a Joseph message."""
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(2, 0))

        def rate(value: int, row=btn_row):
            """Handle rating click."""
            if self._personality_learning:
                self._personality_learning.rate_last_response(value)
            # Visual feedback
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
        ).pack(side="left")'''

new_rating = '''    def _add_rating_buttons(self, parent, textbox: ctk.CTkTextbox) -> None:
        """Add copy, regenerate, and rating buttons below a Joseph message."""
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(2, 0))

        text_content = textbox.get("1.0", "end-1c") if textbox else ""

        # Copy button
        ctk.CTkButton(
            btn_row, text="📋", font=("Segoe UI", 10),
            width=26, height=20, fg_color="transparent",
            hover_color=self.colors["card_hover"],
            text_color=self.colors["text_dim"], corner_radius=4,
            command=lambda t=text_content: self._copy_to_clipboard(t),
        ).pack(side="left", padx=(0, 2))

        # Regenerate button
        ctk.CTkButton(
            btn_row, text="🔄", font=("Segoe UI", 10),
            width=26, height=20, fg_color="transparent",
            hover_color=self.colors["card_hover"],
            text_color=self.colors["text_dim"], corner_radius=4,
            command=self._regenerate_last,
        ).pack(side="left", padx=(0, 4))

        def rate(value: int):
            if self._personality_learning:
                self._personality_learning.rate_last_response(value)
            logger.debug(f"Response rated: {value}")

        ctk.CTkButton(
            btn_row, text="👍", font=("Segoe UI", 10),
            width=26, height=20, fg_color="transparent",
            hover_color=self.colors["card_hover"],
            text_color=self.colors["text_dim"], corner_radius=4,
            command=lambda: rate(1),
        ).pack(side="left", padx=(0, 2))

        ctk.CTkButton(
            btn_row, text="👎", font=("Segoe UI", 10),
            width=26, height=20, fg_color="transparent",
            hover_color=self.colors["card_hover"],
            text_color=self.colors["text_dim"], corner_radius=4,
            command=lambda: rate(-1),
        ).pack(side="left")'''

if old_rating in content:
    content = content.replace(old_rating, new_rating)
    print("10. Message buttons (copy/regenerate/rating): done")
    changes += 1
else:
    print("10. Message buttons: not found (checking _add_rating_buttons)")
    # Check if it exists with self.colors already
    if "_add_rating_buttons" in content:
        print("   (_add_rating_buttons exists with self.colors)")

# ============================================================
# 11. Add _copy_to_clipboard and _regenerate_last methods
# ============================================================
# Add before _add_system_message
add_marker = '''    def _add_system_message(self, text: str, color: Optional[str] = None, icon: Optional[str] = None):'''

add_methods = '''    def _copy_to_clipboard(self, text: str):
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

'''

if add_marker in content:
    content = content.replace(add_marker, add_methods + add_marker, 1)
    print("11. Copy/Regen methods: done")
    changes += 1
else:
    print("11. Copy/Regen methods: marker not found")

# ============================================================
# 12. Add sort/filter to Memory tab
# ============================================================
# Add sort combo box after the search/refresh buttons
old_mem_top = '''        ctk.CTkButton(
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
        ).grid(row=0, column=2, padx=(0, 12), pady=10)'''

new_mem_top = '''        ctk.CTkButton(
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
                        command=lambda v: self._refresh_memory_tab()).pack(side="left")'''

if old_mem_top in content:
    content = content.replace(old_mem_top, new_mem_top)
    print("12. Memory sort/filter: done")
    changes += 1
else:
    print("12. Memory sort/filter: not found")

# ============================================================
# 13. Update _refresh_memory_tab to use sort/filter
# ============================================================
# Add sort/filter logic after the query line
old_refresh_mem = '''    def _refresh_memory_tab(self):
        """Refresh the memory explorer list and detail pane."""
        if not hasattr(self, "_memory_list_frame"):
            return
        query = self._memory_search_box.get().strip() if hasattr(self, "_memory_search_box") else ""
        for widget in self._memory_list_frame.winfo_children():'''

new_refresh_mem = '''    def _refresh_memory_tab(self):
        """Refresh the memory explorer list and detail pane."""
        if not hasattr(self, "_memory_list_frame"):
            return
        query = self._memory_search_box.get().strip() if hasattr(self, "_memory_search_box") else ""
        sort_mode = self._memory_sort_var.get() if hasattr(self, "_memory_sort_var") else "recent"
        cat_filter = self._memory_cat_var.get() if hasattr(self, "_memory_cat_var") else "all"
        for widget in self._memory_list_frame.winfo_children():'''

if old_refresh_mem in content:
    content = content.replace(old_refresh_mem, new_refresh_mem)
    print("13. Memory refresh sort vars: done")
    changes += 1
else:
    print("13. Memory refresh sort vars: not found")

# ============================================================
# 14. Add category filter / sort logic in memory refresh
# ============================================================
# After the dedup loop, add sort/filter before the assignment
old_normalized = '''        self._memory_memory_rows = normalized
        for item in normalized:'''

new_normalized = '''        # Apply category filter
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
        for item in normalized:'''

if old_normalized in content:
    content = content.replace(old_normalized, new_normalized)
    print("14. Memory filter/sort logic: done")
    changes += 1
else:
    print("14. Memory filter/sort logic: not found")

# ============================================================
# 15. Add tags display to memory list items
# ============================================================
# Replace the memory row construction to show tags
old_mem_row = '''            preview = str(item.get("content", ""))[:120].replace("\\n", " ")
            row = ctk.CTkButton(
                self._memory_list_frame,
                text=f"#{memory_id}  {preview}",'''

new_mem_row = '''            preview = str(item.get("content", ""))[:100].replace("\\n", " ")
            tags = item.get("tags") or (item.get("metadata") or {}).get("tags") or []
            tag_str = f" [{', '.join(tags[:3])}]" if tags else ""
            row = ctk.CTkButton(
                self._memory_list_frame,
                text=f"#{memory_id}{tag_str}  {preview}",'''

if old_mem_row in content:
    content = content.replace(old_mem_row, new_mem_row)
    print("15. Memory tags display: done")
    changes += 1
else:
    print("15. Memory tags display: not found")

# ============================================================
# 16. Add agent workflow visualization to Agents tab
# ============================================================
old_agents_build = '''    def _build_agents_tab(self, parent):
        """Build the agent collaboration center."""
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
        ctk.CTkLabel(card, text="Agent Collaboration Flow", font=FONTS["name"], text_color=self.colors["accent"]).pack(anchor="w", padx=12, pady=(10, 6))
        self._agents_box = ctk.CTkTextbox(
            card,
            height=360,
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
        self._refresh_agents_tab()'''

new_agents_build = '''    def _build_agents_tab(self, parent):
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
        self._refresh_agents_tab()'''

if old_agents_build in content:
    content = content.replace(old_agents_build, new_agents_build)
    print("16. Agent workflow visualization: done")
    changes += 1
else:
    print("16. Agent workflow: not found")

# ============================================================
# 17. Update _refresh_agents_tab to update workflow status dots
# ============================================================
old_agents_refresh = '''    def _refresh_agents_tab(self):
        """Refresh agent logs and the collaboration flow."""
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
                content = entry.get("content", "")
                if content:
                    lines.append(content[:600])
                    lines.append("")
        self._set_textbox_content(self._agents_box, "\\n".join(lines).strip())'''

new_agents_refresh = '''    def _refresh_agents_tab(self):
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

        self._set_textbox_content(self._agents_box, "\\n".join(lines).strip())'''

if old_agents_refresh in content:
    content = content.replace(old_agents_refresh, new_agents_refresh)
    print("17. Agent refresh with status dots: done")
    changes += 1
else:
    print("17. Agent refresh: not found")

# ============================================================
# 18. Improve Settings - add more categories (Voice, Appearance)
# ============================================================
old_settings_build = '''        sections = [
            ("AI Settings", [
                ("hyper_enabled", "Enable Hyper Layer", bool(self._active_hyper_engine()), self._on_toggle_hyper),
                ("research_sources", "Research Sources", self._ui_settings.get("research_sources", 3), self._on_research_sources_change),
            ]),
            ("Performance Settings", [
                ("refresh_interval_ms", "Refresh Interval (ms)", self._ui_settings.get("refresh_interval_ms", 2500), self._on_refresh_interval_change),
                ("compact_panels", "Compact Panels", self._ui_settings.get("compact_panels", False), self._on_compact_panels_change),
            ]),
            ("Appearance Settings", [
                ("theme_mode", "Theme Mode", self._theme_mode, self._on_theme_mode_change),
                ("density", "Layout Density", self._ui_settings.get("density", "comfortable"), self._on_density_change),
                ("animations", "Animations", self._ui_settings.get("animations", True), self._on_animations_change),
            ]),
        ]'''

new_settings_build = '''        sections = [
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
        ]'''

if old_settings_build in content:
    content = content.replace(old_settings_build, new_settings_build)
    print("18. Settings categories: done")
    changes += 1
else:
    print("18. Settings categories: not found")

# ============================================================
# 19. Add font_scale and voice_enabled setting handlers
# ============================================================
old_on_anim = '''    def _on_animations_change(self, key: str, value):
        self._ui_settings[key] = bool(value)'''

new_on_anim = '''    def _on_animations_change(self, key: str, value):
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
                self._voice.stop()'''

if old_on_anim in content:
    content = content.replace(old_on_anim, new_on_anim)
    print("19. Settings handlers (font, voice): done")
    changes += 1
else:
    print("19. Settings handlers: not found")

# ============================================================
# 20. Update _refresh_settings_tab to include new keys
# ============================================================
old_sync = '''        if "animations" in self._setting_vars:
                self._setting_vars["animations"].set(bool(self._ui_settings.get("animations", True)))'''

new_sync = '''        if "animations" in self._setting_vars:
                self._setting_vars["animations"].set(bool(self._ui_settings.get("animations", True)))
            if "font_size" in self._setting_vars:
                self._setting_vars["font_size"].set(str(self._font_scale))
            if "voice_enabled" in self._setting_vars:
                self._setting_vars["voice_enabled"].set(bool(self._voice_enabled))'''

if old_sync in content:
    content = content.replace(old_sync, new_sync)
    print("20. Settings sync new keys: done")
    changes += 1
else:
    print("20. Settings sync: not found")

# ============================================================
# Write the transformed file
# ============================================================
if changes > 0:
    with open(SRC, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\nTotal changes: {changes}")
    print(f"File size: {len(content)} bytes")
else:
    print("\nNo changes made.")
