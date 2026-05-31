"""
projects/project_manager.py
----------------------------
Orchestrator for the JOSEPH Project Manager module.

Combines ProjectStore, GoalTracker, MilestoneTracker, TaskManager,
and ResearchTracker into a unified interface with dashboard,
timeline, search, summary, and optional memory/knowledge-graph
integration.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from projects.project_store import ProjectStore, _now
from projects.goal_tracker import GoalTracker
from projects.milestone_tracker import MilestoneTracker
from projects.task_manager import TaskManager
from projects.research_tracker import ResearchTracker

logger = logging.getLogger(__name__)

_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class ProjectManager:
    """
    Unified orchestrator for all project-related functionality.

    Combines every sub-manager into one interface and provides
    high-level operations like dashboard, timeline, search, and
    optional external integrations.

    Usage:
        pm = ProjectManager()
        project = pm.create_complete_project(
            name="My App",
            description="Building something great",
            goals=[...],
            milestones=[...],
            tasks=[...],
        )
        dashboard = pm.get_project_dashboard(project.id)
    """

    def __init__(
        self,
        memory_manager: Optional[Any] = None,
        knowledge_graph: Optional[Any] = None,
    ):
        self.store = ProjectStore()
        self.goals = GoalTracker()
        self.milestones = MilestoneTracker()
        self.tasks = TaskManager()
        self.research = ResearchTracker()
        self._memory = memory_manager
        self._kg = knowledge_graph

    # ------------------------------------------------------------------ #
    # One-shot project creation
    # ------------------------------------------------------------------ #

    def create_complete_project(
        self,
        name: str,
        description: str,
        path: Optional[str] = None,
        goals: Optional[list[dict]] = None,
        milestones: Optional[list[dict]] = None,
        tasks: Optional[list[dict]] = None,
    ) -> Any:
        """
        Create a project with optional goals, milestones, and tasks in one call.

        Args:
            name: Project name.
            description: Project description.
            path: Optional filesystem path.
            goals: Optional list of goal dicts (title, description, priority, deadline).
            milestones: Optional list of milestone dicts (title, description, deadline, goal_id).
            tasks: Optional list of task dicts (title, description, priority, due_date, goal_id).

        Returns:
            The newly created Project.
        """
        project = self.store.create_project(name, description, path=path)

        for g in goals or []:
            self.goals.add_goal(
                project_id=project.id,
                title=g.get("title", "Untitled Goal"),
                description=g.get("description", ""),
                priority=g.get("priority", "medium"),
                deadline=g.get("deadline"),
            )

        for m in milestones or []:
            self.milestones.add_milestone(
                project_id=project.id,
                title=m.get("title", "Untitled Milestone"),
                description=m.get("description", ""),
                deadline=m.get("deadline"),
                goal_id=m.get("goal_id"),
            )

        for t in tasks or []:
            self.tasks.add_task(
                project_id=project.id,
                title=t.get("title", "Untitled Task"),
                description=t.get("description", ""),
                priority=t.get("priority", "medium"),
                due_date=t.get("due_date"),
                goal_id=t.get("goal_id"),
                tags=t.get("tags"),
                depends_on=t.get("depends_on"),
            )

        logger.info(f"Complete project created: {project.name} ({project.id[:8]}...)")
        return project

    # ------------------------------------------------------------------ #
    # Dashboard
    # ------------------------------------------------------------------ #

    def get_project_dashboard(self, project_id: str) -> dict:
        """
        Return a full project overview.

        Args:
            project_id: The project's unique ID.

        Returns:
            Dict with keys: project, goals, goal_stats, milestones,
            tasks, task_stats, research_notes, overdue_milestones.
        """
        project = self.store.get_project(project_id)
        if not project:
            return {"error": f"Project not found: {project_id}"}

        project_goals = self.goals.get_goals(project_id)
        project_milestones = self.milestones.get_milestones(project_id)
        project_tasks = self.tasks.get_tasks(project_id)
        project_notes = self.research.get_notes(project_id)
        overdue = self.milestones.get_overdue_milestones()
        project_overdue = [m for m in overdue if m.project_id == project_id]

        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "created_at": project.created_at,
                "tags": project.tags,
            },
            "goals": {
                "count": len(project_goals),
                "stats": self.goals.get_goal_stats(project_id),
                "items": [
                    {"id": g.id, "title": g.title, "status": g.status, "priority": g.priority}
                    for g in project_goals
                ],
            },
            "milestones": {
                "count": len(project_milestones),
                "items": [
                    {"id": m.id, "title": m.title, "status": m.status, "deadline": m.deadline}
                    for m in project_milestones
                ],
                "overdue": [
                    {"id": m.id, "title": m.title, "deadline": m.deadline}
                    for m in project_overdue
                ],
            },
            "tasks": {
                "count": len(project_tasks),
                "stats": self.tasks.get_task_stats(project_id),
                "blocked": [
                    {"id": t.id, "title": t.title}
                    for t in self.tasks.get_blocked_tasks()
                    if t.project_id == project_id
                ],
            },
            "research": {
                "count": len(project_notes),
                "recent": [
                    {"id": n.id, "title": n.title, "relevance": n.relevance}
                    for n in project_notes[:5]
                ],
            },
        }

    # ------------------------------------------------------------------ #
    # Timeline
    # ------------------------------------------------------------------ #

    def get_project_timeline(self, project_id: str) -> str:
        """
        Build a human-readable text timeline for a project.

        Includes milestones, goals with deadlines, and tasks with due dates,
        ordered chronologically.

        Args:
            project_id: The project's unique ID.

        Returns:
            Formatted timeline string.
        """
        project = self.store.get_project(project_id)
        if not project:
            return f"Project not found: {project_id}"

        lines = [f"Timeline: {project.name}", "=" * 40]

        events: list[tuple[str, str, str]] = []  # (date, type, label)

        for m in self.milestones.get_milestones(project_id):
            if m.deadline:
                events.append((m.deadline, "MILESTONE", m.title))

        for g in self.goals.get_goals(project_id):
            if g.deadline:
                events.append((g.deadline, "GOAL", g.title))

        for t in self.tasks.get_tasks(project_id):
            if t.due_date:
                events.append((t.due_date, "TASK", t.title))

        events.sort(key=lambda x: x[0])

        if not events:
            lines.append("No dated events.")
        else:
            for date_str, etype, label in events:
                lines.append(f"  [{date_str[:10]}] ({etype}) {label}")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search_everything(self, query: str) -> dict:
        """
        Search across all project entities.

        Args:
            query: Case-insensitive search string.

        Returns:
            Dict with keys: projects, goals, milestones, tasks, research_notes.
        """
        return {
            "projects": [
                {"id": p.id, "name": p.name}
                for p in self.store.search_projects(query)
            ],
            "goals": [
                {"id": g.id, "title": g.title, "project_id": g.project_id}
                for g in self.goals._goals.values()
                if (
                    query.lower() in g.title.lower()
                    or query.lower() in g.description.lower()
                )
            ],
            "milestones": [
                {"id": m.id, "title": m.title, "project_id": m.project_id}
                for m in self.milestones._milestones.values()
                if (
                    query.lower() in m.title.lower()
                    or query.lower() in m.description.lower()
                )
            ],
            "tasks": [
                {"id": t.id, "title": t.title, "project_id": t.project_id}
                for t in self.tasks._tasks.values()
                if (
                    query.lower() in t.title.lower()
                    or query.lower() in t.description.lower()
                )
            ],
            "research_notes": [
                {"id": n.id, "title": n.title, "project_id": n.project_id}
                for n in self.research.search_notes(query)
            ],
        }

    # ------------------------------------------------------------------ #
    # Summaries
    # ------------------------------------------------------------------ #

    def get_summary(self, project_id: str) -> str:
        """
        Build a text summary of a single project, suitable for display or LLM context.

        Args:
            project_id: The project's unique ID.

        Returns:
            Formatted summary string.
        """
        project = self.store.get_project(project_id)
        if not project:
            return f"Project not found: {project_id}"

        project_goals = self.goals.get_goals(project_id)
        project_milestones = self.milestones.get_milestones(project_id)
        project_tasks = self.tasks.get_tasks(project_id)

        total_goals = len(project_goals)
        done_goals = sum(1 for g in project_goals if g.status == "completed")
        total_tasks = len(project_tasks)
        done_tasks = sum(1 for t in project_tasks if t.status == "done")
        total_milestones = len(project_milestones)
        reached_milestones = sum(1 for m in project_milestones if m.status == "reached")
        overdue_milestones = [
            m for m in project_milestones
            if m.status == "pending" and m.deadline
        ]

        lines = [
            f"Project: {project.name}",
            f"  Status: {project.status}",
            f"  Description: {project.description}",
            f"  Path: {project.path or 'N/A'}",
            f"  Created: {project.created_at[:10] if project.created_at else 'N/A'}",
            f"  Tags: {', '.join(project.tags) if project.tags else 'None'}",
            "",
            f"  Goals: {done_goals}/{total_goals} completed",
            f"  Milestones: {reached_milestones}/{total_milestones} reached",
            f"  Tasks: {done_tasks}/{total_tasks} done",
        ]

        if overdue_milestones:
            lines.append(
                f"  Overdue milestones: {', '.join(m.title for m in overdue_milestones[:3])}"
            )

        return "\n".join(lines)

    def get_all_summaries(self) -> str:
        """
        Build a summary of all projects.

        Returns:
            Formatted string with one block per project.
        """
        projects = self.store.get_all_projects()
        if not projects:
            return "No projects found."

        blocks = [f"Projects Overview ({len(projects)} total)", "=" * 40]
        for p in projects:
            blocks.append("")
            blocks.append(self.get_summary(p.id))

        return "\n".join(blocks)

    # ------------------------------------------------------------------ #
    # External integrations
    # ------------------------------------------------------------------ #

    def memory_integration(self) -> None:
        """
        Optionally sync project data with the memory manager.

        If a memory manager was provided at init, this saves a summary
        of all active projects as an explicit memory.
        """
        if not self._memory:
            logger.debug("No memory manager available for integration")
            return

        try:
            active = self.store.get_active_projects()
            if not active:
                return

            lines = ["Active projects:"]
            for p in active:
                task_stats = self.tasks.get_task_stats(p.id)
                done = task_stats["by_status"].get("done", 0)
                total = task_stats["total"]
                lines.append(f"- {p.name}: {done}/{total} tasks done")

            summary = "\n".join(lines)
            self._memory.save_explicit_memory(
                content=summary,
                tags=["projects", "active"],
            )
            logger.info("Project data synced to memory manager")
        except Exception as e:
            logger.warning(f"Memory integration failed: {e}")

    def knowledge_graph_integration(self) -> None:
        """
        Optionally link project entities to a knowledge graph.

        If a knowledge_graph was provided at init, this creates nodes
        and edges for projects, goals, milestones, and tasks.
        """
        if not self._kg:
            logger.debug("No knowledge graph available for integration")
            return

        try:
            kg = self._kg

            for project in self.store.get_all_projects():
                kg.add_node(
                    node_id=f"project:{project.id}",
                    label="Project",
                    properties={
                        "name": project.name,
                        "status": project.status,
                        "created_at": project.created_at,
                    },
                )

                for goal in self.goals.get_goals(project.id):
                    kg.add_node(
                        node_id=f"goal:{goal.id}",
                        label="Goal",
                        properties={
                            "title": goal.title,
                            "status": goal.status,
                            "priority": goal.priority,
                        },
                    )
                    kg.add_edge(
                        source=f"project:{project.id}",
                        target=f"goal:{goal.id}",
                        relation="has_goal",
                    )

                for task in self.tasks.get_tasks(project.id):
                    kg.add_node(
                        node_id=f"task:{task.id}",
                        label="Task",
                        properties={
                            "title": task.title,
                            "status": task.status,
                            "priority": task.priority,
                        },
                    )
                    kg.add_edge(
                        source=f"project:{project.id}",
                        target=f"task:{task.id}",
                        relation="has_task",
                    )

                    if task.goal_id:
                        kg.add_edge(
                            source=f"goal:{task.goal_id}",
                            target=f"task:{task.id}",
                            relation="supports",
                        )

                    for dep_id in task.depends_on:
                        kg.add_edge(
                            source=f"task:{task.id}",
                            target=f"task:{dep_id}",
                            relation="depends_on",
                        )

            logger.info("Project data synced to knowledge graph")
        except Exception as e:
            logger.warning(f"Knowledge graph integration failed: {e}")

    # ------------------------------------------------------------------ #
    # Bulk persistence
    # ------------------------------------------------------------------ #

    def save_all(self) -> None:
        """Persist all project data to disk."""
        self.store.save()
        self.goals.save()
        self.milestones.save()
        self.tasks.save()
        self.research.save()
        logger.info("All project data saved")

    def load_all(self) -> None:
        """Load all project data from disk."""
        self.store.load()
        self.goals.load()
        self.milestones.load()
        self.tasks.load()
        self.research.load()
        logger.info("All project data loaded")
