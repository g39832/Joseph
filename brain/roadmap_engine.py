"""
brain/roadmap_engine.py
-------------------------
Roadmap Generator — creates learning plans, development plans,
research plans, and project plans with milestones, dependencies,
estimated effort, and progress tracking.

Rule-based templates — no LLM calls required.
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RoadmapMilestone:
    id: str
    title: str
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    estimated_hours: float = 1.0
    status: str = "pending"
    due_date: str = ""


@dataclass
class Roadmap:
    id: str
    title: str
    roadmap_type: str  # learning | development | research | project
    milestones: list[dict] = field(default_factory=list)
    total_effort_hours: float = 0.0
    progress_pct: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


# --- Learning templates ---

LEARNING_TEMPLATES = {
    "python": {
        "title": "Python Mastery",
        "milestones": [
            ("Python Basics", "Syntax, data types, control flow, functions", 5),
            ("Data Structures", "Lists, dicts, sets, tuples, comprehensions", 4),
            ("OOP & Modules", "Classes, inheritance, modules, packages", 5),
            ("Standard Library", "File I/O, datetime, re, collections, itertools", 6),
            ("Testing & Debugging", "unittest, pytest, logging, debugging techniques", 4),
            ("Advanced Topics", "Decorators, generators, context managers, async", 8),
            ("Project: CLI Tool", "Build a command-line tool with argparse", 6),
            ("Project: API Client", "Build an API client with requests/aiohttp", 8),
        ],
    },
    "rust": {
        "title": "Rust Programming",
        "milestones": [
            ("Rust Fundamentals", "Ownership, borrowing, lifetimes, pattern matching", 10),
            ("Data Types & Collections", "Structs, enums, Vec, HashMap, Option, Result", 6),
            ("Error Handling & Modules", "Panic, Result, modules, crates", 5),
            ("Traits & Generics", "Traits, generics, trait objects, dyn", 8),
            ("Memory Management", "Box, Rc, Arc, RefCell, smart pointers", 8),
            ("Concurrency", "Threads, channels, Mutex, async/await, tokio", 10),
            ("Project: CLI Tool", "Build a CLI with clap", 8),
            ("Project: Web Server", "Build a simple HTTP server with axum/actix", 12),
        ],
    },
    "embedded": {
        "title": "Embedded Systems",
        "milestones": [
            ("C/ C++ Refresher", "Pointers, memory management, bit manipulation", 6),
            ("Microcontroller Basics", "GPIO, timers, interrupts, ADC, PWM", 10),
            ("Communication Protocols", "UART, I2C, SPI, CAN", 8),
            ("RTOS Concepts", "Tasks, scheduling, semaphores, queues", 8),
            ("ARM Cortex-M", "Register model, NVIC, systick, linker scripts", 10),
            ("Project: Sensor Interface", "Read temperature/humidity sensor via I2C", 8),
            ("Project: Motor Control", "PWM-based motor controller with feedback", 10),
            ("Project: RTOS Application", "Multi-task sensor/logging system", 12),
        ],
    },
    "computer_science": {
        "title": "Computer Science Foundations",
        "milestones": [
            ("Discrete Mathematics", "Logic, set theory, graph theory, combinatorics", 15),
            ("Data Structures & Algorithms", "Arrays, trees, graphs, sorting, searching, DP", 20),
            ("Computer Architecture", "CPU, memory, cache, pipelining, assembly basics", 12),
            ("Operating Systems", "Processes, threads, scheduling, memory mgmt, file systems", 15),
            ("Networking", "TCP/IP, HTTP, DNS, routing, sockets", 10),
            ("Databases", "SQL, normalization, indexing, transactions", 10),
            ("Compiler Basics", "Lexing, parsing, AST, code generation", 12),
            ("Capstone: OS Project", "Build a simple OS component or compiler stage", 20),
        ],
    },
}


class RoadmapEngine:
    """
    Generates and tracks roadmaps.

    Usage:
        engine = RoadmapEngine()
        roadmap = engine.create_learning_plan("python")
        engine.update_progress(roadmap.id, milestone_id, "completed")
    """

    def __init__(self, workspace_manager=None):
        self._wm = workspace_manager
        self._roadmaps: dict[str, Roadmap] = {}

    def create_learning_plan(
        self, topic: str, custom_title: str = "",
    ) -> Optional[Roadmap]:
        template = LEARNING_TEMPLATES.get(topic.lower().replace(" ", "_"))
        if not template:
            return None

        title = custom_title or template["title"]
        rid = str(uuid.uuid4())
        total_hours = sum(m[2] for m in template["milestones"])

        milestones = []
        for i, (mtitle, mdesc, hours) in enumerate(template["milestones"]):
            deps = []
            if i > 0:
                deps = [template["milestones"][i - 1][0]]
            milestones.append(asdict(RoadmapMilestone(
                id=str(uuid.uuid4()),
                title=mtitle,
                description=mdesc,
                dependencies=deps,
                estimated_hours=hours,
            )))

        roadmap = Roadmap(
            id=rid,
            title=title,
            roadmap_type="learning",
            milestones=milestones,
            total_effort_hours=total_hours,
        )
        self._roadmaps[rid] = roadmap
        return roadmap

    def create_project_plan(
        self, title: str, milestones: list[dict],
    ) -> Roadmap:
        """Create a custom project roadmap from milestone definitions."""
        rid = str(uuid.uuid4())
        total_hours = sum(m.get("hours", 1) for m in milestones)

        milestone_objs = []
        for i, m in enumerate(milestones):
            deps = m.get("dependencies", [])
            if not deps and i > 0:
                deps = [milestones[i - 1].get("title", "")]
            milestone_objs.append(asdict(RoadmapMilestone(
                id=str(uuid.uuid4()),
                title=m.get("title", "Untitled"),
                description=m.get("description", ""),
                dependencies=deps,
                estimated_hours=m.get("hours", 1),
            )))

        roadmap = Roadmap(
            id=rid,
            title=title,
            roadmap_type="project",
            milestones=milestone_objs,
            total_effort_hours=total_hours,
        )
        self._roadmaps[rid] = roadmap
        return roadmap

    def get_roadmap(self, roadmap_id: str) -> Optional[Roadmap]:
        return self._roadmaps.get(roadmap_id)

    def update_milestone(
        self, roadmap_id: str, milestone_id: str, status: str,
    ) -> bool:
        roadmap = self._roadmaps.get(roadmap_id)
        if not roadmap:
            return False
        for m in roadmap.milestones:
            if m.get("id") == milestone_id:
                m["status"] = status
                roadmap.updated_at = datetime.now().isoformat()
                self._recalculate_progress(roadmap)
                return True
        return False

    def _recalculate_progress(self, roadmap: Roadmap) -> None:
        total = len(roadmap.milestones)
        done = sum(
            1 for m in roadmap.milestones if m.get("status") == "completed"
        )
        roadmap.progress_pct = int((done / total) * 100) if total else 0

    def get_available_templates(self) -> list[str]:
        return list(LEARNING_TEMPLATES.keys())

    def suggest_next_topics(self, completed_topics: list[str]) -> list[str]:
        """From completed topics, suggest next logical topic."""
        for template_key, template in LEARNING_TEMPLATES.items():
            titles = [m[0] for m in template["milestones"]]
            if any(t in completed_topics for t in titles):
                remaining = [
                    t for t in titles if t not in completed_topics
                ]
                if remaining:
                    return [f"{template_key}: {remaining[0]}"]
        return list(LEARNING_TEMPLATES.keys())
