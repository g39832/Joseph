"""
ui/app.py
---------
JOSEPH Desktop UI — Phase 4: Responsive, polished, professional.
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
    enhance_response,
    finalize_hyper_turn,
    get_context_enhancement,
    prepare_hyper_turn,
    shutdown_hyper,
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
