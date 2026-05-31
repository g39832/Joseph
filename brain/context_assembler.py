"""
brain/context_assembler.py
--------------------------
Unified memory pipeline — Phase 6 / Phase X.

Retrieves and combines context from all subsystems into a single
context package for the LLM, scoring each source by relevance.

Now includes:
  - Token budgeting to avoid prompt bloat
  - Memory relevance engine for ranked memory selection
  - Response-depth-aware context trimming
  - Continuity and consolidated memory context
"""

import logging
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONTEXT_CHARS = 2500
DEPTH_CHAR_BUDGETS = {0.3: 800, 0.5: 1500, 0.7: 2500, 0.85: 3500, 1.0: 4000}


class UnifiedContext:
    """
    Container for a single assembled context result.
    """

    def __init__(
        self,
        memory_context: str = "",
        graph_context: str = "",
        project_context: str = "",
        research_context: str = "",
        personality_modifier: str = "",
        continuity_context: str = "",
        consolidation_context: str = "",
        insight_context: str = "",
        sources: Optional[list[dict]] = None,
    ):
        self.memory_context = memory_context
        self.graph_context = graph_context
        self.project_context = project_context
        self.research_context = research_context
        self.personality_modifier = personality_modifier
        self.continuity_context = continuity_context
        self.consolidation_context = consolidation_context
        self.insight_context = insight_context
        self.sources = sources or []

    def assemble(self, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS) -> str:
        sections = []
        budget = max_chars

        priority_ordered = [
            ("continuity", self.continuity_context),
            ("consolidation", self.consolidation_context),
            ("research", self.research_context),
            ("graph", self.graph_context),
            ("memory", self.memory_context),
            ("project", self.project_context),
            ("insight", self.insight_context),
        ]

        for section_type, section_content in priority_ordered:
            if not section_content:
                continue

            formatted = section_content
            if section_type in ("research", "graph", "project", "insight"):
                header = {
                    "research": "## Research Context",
                    "graph": "## Knowledge Graph",
                    "project": "## Project Context",
                    "insight": "## Insights",
                }.get(section_type, "")
                formatted = f"{header}\n{section_content}" if header else section_content

            if section_type == "memory":
                formatted = section_content

            if section_type == "continuity":
                formatted = section_content

            if section_type == "consolidation":
                formatted = section_content

            estimated = len(formatted) + 2
            if estimated <= budget:
                sections.append(formatted)
                budget -= estimated
            else:
                trimmed = formatted[:max(0, budget - 3)] + "..."
                if trimmed.strip("."):
                    sections.append(trimmed)
                break

        result = "\n\n".join(sections)
        if self.personality_modifier and len(result) + len(self.personality_modifier) + 2 <= max_chars:
            result += f"\n\n{self.personality_modifier}"
        elif self.personality_modifier:
            result += f"\n\n{self.personality_modifier[:200]}"
        return result

    def to_dict(self) -> dict:
        return {
            "has_memory": bool(self.memory_context),
            "has_graph": bool(self.graph_context),
            "has_project": bool(self.project_context),
            "has_research": bool(self.research_context),
            "has_personality": bool(self.personality_modifier),
            "has_continuity": bool(self.continuity_context),
            "has_consolidation": bool(self.consolidation_context),
            "has_insights": bool(self.insight_context),
            "sources": self.sources,
            "total_length": len(self.assemble()),
        }


class ContextAssembler:
    """
    Unified memory pipeline — retrieves context from every subsystem
    and assembles a single enriched context package.

    Now supports token budgeting via response_depth and relevance-ranked
    memory selection via MemoryRelevanceEngine.
    """

    def __init__(
        self,
        llm=None,
        memory=None,
        hyper_engine=None,
        continuity_engine=None,
        consolidation_engine=None,
        insight_engine=None,
        memory_relevance=None,
        smart_cache=None,
    ):
        self.llm = llm
        self.memory = memory
        self.hyper_engine = hyper_engine
        self.continuity_engine = continuity_engine
        self.consolidation_engine = consolidation_engine
        self.insight_engine = insight_engine
        self._relevance = memory_relevance
        self._cache = smart_cache
        self._graph = None
        self._project_manager = None

    def _lazy_graph(self):
        if self._graph is None:
            try:
                from hyper.knowledge_graph import KnowledgeGraph
                self._graph = KnowledgeGraph()
            except Exception as e:
                logger.debug(f"KnowledgeGraph unavailable: {e}")
        return self._graph

    def _lazy_project_manager(self):
        if self._project_manager is None:
            try:
                from projects.project_manager import ProjectManager
                self._project_manager = ProjectManager()
            except Exception as e:
                logger.debug(f"ProjectManager unavailable: {e}")
        return self._project_manager

    def _compute_max_chars(self, response_depth: float) -> int:
        budgets = DEPTH_CHAR_BUDGETS
        closest = min(budgets.keys(), key=lambda k: abs(k - response_depth))
        return budgets[closest]

    def assemble(
        self,
        user_input: str,
        include_memory: bool = True,
        include_graph: bool = True,
        include_project: bool = True,
        include_research: bool = True,
        include_personality: bool = True,
        include_continuity: bool = True,
        include_consolidation: bool = True,
        include_insights: bool = True,
        response_depth: float = 0.5,
        active_project: Optional[str] = None,
    ) -> UnifiedContext:
        sources = []
        ctx = UnifiedContext()
        max_chars = self._compute_max_chars(response_depth)

        if include_continuity and self.continuity_engine:
            try:
                cache_key = f"continuity:{len(self.continuity_engine._sessions) if hasattr(self.continuity_engine, '_sessions') else 0}"
                continuity_ctx = None
                if self._cache:
                    continuity_ctx = self._cache.get_system_context(cache_key)
                if continuity_ctx is None:
                    continuity_ctx = self.continuity_engine.get_continuity_context()
                    if self._cache and continuity_ctx:
                        self._cache.set_system_context(cache_key, continuity_ctx[:500])
                if continuity_ctx:
                    ctx.continuity_context = continuity_ctx
                    sources.append({"type": "continuity", "length": len(continuity_ctx)})
            except Exception as e:
                logger.debug(f"Continuity context error: {e}")

        if include_consolidation and self.consolidation_engine:
            try:
                consolidation_ctx = self.consolidation_engine.build_consolidation_context(limit=3 if response_depth < 0.5 else 5)
                if consolidation_ctx:
                    ctx.consolidation_context = consolidation_ctx
                    sources.append({"type": "consolidation", "length": len(consolidation_ctx)})
            except Exception as e:
                logger.debug(f"Consolidation context error: {e}")

        if include_memory and self.memory:
            try:
                memory_ctx = self.memory.get_context_for_llm(query=user_input)
                companion_ctx = self.memory.get_companion_context()
                if companion_ctx:
                    memory_ctx = companion_ctx + "\n\n" + memory_ctx
                ctx.memory_context = memory_ctx
                sources.append({"type": "memory", "length": len(memory_ctx)})
            except Exception as e:
                logger.debug(f"Memory context error: {e}")

            try:
                from hyper.bootstrap import get_context_enhancement
                extra = get_context_enhancement(self.hyper_engine, user_input)
                if extra:
                    ctx.memory_context = (
                        f"{ctx.memory_context}\n\n{extra}" if ctx.memory_context else extra
                    )
                    sources.append({"type": "hyper", "length": len(extra)})
            except Exception:
                pass

        if include_insights and self.insight_engine:
            try:
                insight_summary = self.insight_engine.get_summary()
                if insight_summary and insight_summary != "No insights yet.":
                    ctx.insight_context = insight_summary
                    sources.append({"type": "insight", "length": len(insight_summary)})
            except Exception as e:
                logger.debug(f"Insight context error: {e}")

        if include_graph:
            graph = self._lazy_graph()
            if graph:
                try:
                    graph_ctx = graph.build_context(user_input, limit=3 if response_depth < 0.5 else 5)
                    ctx.graph_context = graph_ctx
                    if graph_ctx:
                        sources.append({"type": "graph", "length": len(graph_ctx)})
                except Exception as e:
                    logger.debug(f"Graph context error: {e}")

        if include_project:
            pm = self._lazy_project_manager()
            if pm:
                try:
                    project_cache_key = None
                    if active_project and self._cache:
                        project_cache_key = f"project_dashboard:{active_project}"
                        cached = self._cache.get_project_context(project_cache_key)
                        if cached:
                            ctx.project_context = cached
                            sources.append({"type": "project_cached", "length": len(cached)})
                    if ctx.project_context is None:
                        project_info = pm.get_dashboard_data()
                        if project_info:
                            lines = []
                            for p in project_info.get("projects", [])[:2 if response_depth < 0.5 else 3]:
                                lines.append(f"- {p.get('name', '?')}: {p.get('status', '?')}")
                            if lines:
                                proj_ctx = "Active projects:\n" + "\n".join(lines)
                                ctx.project_context = proj_ctx
                                sources.append({"type": "project", "length": len(proj_ctx)})
                                if project_cache_key and self._cache:
                                    self._cache.set_project_context(project_cache_key, proj_ctx)
                except Exception as e:
                    logger.debug(f"Project context error: {e}")

        if include_research:
            try:
                memory_search = self.memory.search(user_input) if self.memory else {}
                semantic = memory_search.get("semantic_results") or []
                if semantic:
                    if self._relevance and len(semantic) > 3:
                        ranked = self._relevance.rank_memories(
                            query=user_input,
                            semantic_results=semantic,
                            active_project=active_project,
                        )
                        selected = self._relevance.select_top(
                            ranked,
                            max_items=3 if response_depth < 0.5 else 5,
                            max_estimate_chars=int(max_chars * 0.3),
                        )
                        fmt = self._relevance.format_for_prompt(selected)
                    else:
                        fmt = self.memory.chroma.format_search_results(semantic) if self.memory and hasattr(self.memory, 'chroma') else str(semantic)
                    ctx.research_context = fmt if fmt else ""
                    if ctx.research_context:
                        sources.append({"type": "research", "length": len(ctx.research_context)})
            except Exception as e:
                logger.debug(f"Research context error: {e}")

        ctx.sources = sources
        return ctx


def assemble_context(
    user_input: str,
    llm=None,
    memory=None,
    hyper_engine=None,
    continuity_engine=None,
    consolidation_engine=None,
    insight_engine=None,
    memory_relevance=None,
    smart_cache=None,
    **kwargs,
) -> UnifiedContext:
    assembler = ContextAssembler(
        llm=llm,
        memory=memory,
        hyper_engine=hyper_engine,
        continuity_engine=continuity_engine,
        consolidation_engine=consolidation_engine,
        insight_engine=insight_engine,
        memory_relevance=memory_relevance,
        smart_cache=smart_cache,
    )
    return assembler.assemble(user_input, **kwargs)
