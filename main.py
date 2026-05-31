"""
main.py
--------
JOSEPH AI Assistant — Entry Point

Run modes:
    python main.py          → Desktop GUI (default)
    python main.py --cli    → Terminal CLI interface

Phase 1 features:
  - Modern dark gray desktop UI
  - Terminal CLI fallback
  - Streaming LLM responses
  - Short + long-term memory
  - ChromaDB semantic search
  - Personality system
"""

import logging
import sys
import time

# ------------------------------------------------------------------ #
# Step 1: Setup logging FIRST
# ------------------------------------------------------------------ #
from configs.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Step 2: Import everything else
# ------------------------------------------------------------------ #
from brain.llm_interface import LLMInterface
from brain.personality import PersonalityEngine
from brain.prompts import get_system_prompt
from configs.settings import settings
from memory.memory_manager import MemoryManager
from hyper.bootstrap import (
    create_hyper_engine,
    finalize_hyper_turn,
    enhance_response,
    get_context_enhancement,
    prepare_hyper_turn,
    shutdown_hyper,
)
from brain.orchestrator import create_router

# Phase 7: advanced capability engines
from brain.activity_tracker import ActivityTracker
from brain.project_awareness import ProjectAwareness
from brain.insight_engine import InsightEngine
from brain.research_workspace import ResearchWorkspace
from brain.followup_engine import FollowUpEngine
from brain.ambient_intelligence import AmbientIntelligence

# Phase 8: Personal Operating System
from brain.workspace_manager import WorkspaceManager
from brain.project_commander import ProjectCommander
from brain.roadmap_engine import RoadmapEngine
from brain.weekly_review import WeeklyReview
from brain.briefing_v2 import BriefingV2
from brain.project_memory import ProjectMemory
from brain.research_pipeline import ResearchPipeline
from brain.learning_companion import LearningCompanion
from brain.decision_history import DecisionHistory
from brain.continuity_engine import ContinuityEngine
from brain.memory_consolidation import MemoryConsolidationEngine

# Phase X: Cognitive Architecture
from brain.cognitive_router import CognitiveRouter, CognitivePath, quality_check
from brain.memory_relevance import MemoryRelevanceEngine
from brain.smart_cache import SmartCache

# Phase 9: Vision, Document Intelligence, Computer Awareness
from brain.document_intelligence import DocumentIntelligence
from brain.vision_engine import VisionEngine
from brain.paper_analyzer import PaperAnalyzer
from brain.screen_awareness import ScreenAwareness
from brain.code_vision import CodeVision
from brain.diagram_analyzer import DiagramAnalyzer
from brain.multimodal_memory import MultimodalMemory
from brain.background_research import BackgroundResearch


def run_gui(
    llm: LLMInterface,
    memory: MemoryManager,
    personality: PersonalityEngine,
    hyper_engine=None,
    router=None,
    activity_tracker=None,
    project_awareness=None,
    insight_engine=None,
    research_workspace=None,
    followup_engine=None,
    ambient_intel=None,
    workspace_manager=None,
    project_commander=None,
    roadmap_engine=None,
    weekly_review=None,
    briefing_v2=None,
    project_memory=None,
    research_pipeline=None,
    learning_companion=None,
    decision_history=None,
    continuity_engine=None,
    consolidation_engine=None,
    document_intelligence=None,
    vision_engine=None,
    paper_analyzer=None,
    screen_awareness=None,
    code_vision=None,
    diagram_analyzer=None,
    multimodal_memory=None,
    background_research=None,
    cognitive_router=None,
    memory_relevance=None,
    smart_cache=None,
):
    """Launch the desktop GUI."""
    try:
        from ui.app import JosephApp
        app = JosephApp(
            llm=llm,
            memory=memory,
            personality=personality,
            hyper_engine=hyper_engine,
            router=router,
            activity_tracker=activity_tracker,
            project_awareness=project_awareness,
            insight_engine=insight_engine,
            research_workspace=research_workspace,
            followup_engine=followup_engine,
            ambient_intel=ambient_intel,
            workspace_manager=workspace_manager,
            project_commander=project_commander,
            roadmap_engine=roadmap_engine,
            weekly_review=weekly_review,
            briefing_v2=briefing_v2,
            project_memory=project_memory,
            research_pipeline=research_pipeline,
            learning_companion=learning_companion,
            decision_history=decision_history,
            continuity_engine=continuity_engine,
            consolidation_engine=consolidation_engine,
            document_intelligence=document_intelligence,
            vision_engine=vision_engine,
            paper_analyzer=paper_analyzer,
            screen_awareness=screen_awareness,
            code_vision=code_vision,
            diagram_analyzer=diagram_analyzer,
            multimodal_memory=multimodal_memory,
        )
        app.mainloop()
    except ImportError as e:
        logger.error(f"GUI failed to import: {e}")
        print(f"\nGUI unavailable: {e}")
        print("Falling back to CLI. Run with --cli to skip this message.\n")
        run_cli(
            llm, memory, personality,
            hyper_engine=hyper_engine,
            continuity_engine=continuity_engine,
            consolidation_engine=consolidation_engine,
        )

def run_cli(
    llm: LLMInterface,
    memory: MemoryManager,
    personality: PersonalityEngine,
    hyper_engine=None,
    continuity_engine=None,
    consolidation_engine=None,
    cognitive_router=None,
    memory_relevance=None,
    smart_cache=None,
):
    """Launch the terminal CLI interface with cognitive routing."""
    from ui.cli_interface import CLIInterface

    cli = CLIInterface()
    memory.start_session()
    if continuity_engine:
        continuity_engine.record_session_start()
    if hyper_engine and hasattr(hyper_engine, "set_session_context"):
        hyper_engine.set_session_context(memory.session_id)

    cli.show_welcome(memory_status=memory.format_status())
    cli.show_joseph_response(personality.get_greeting())

    logger.info("CLI chat loop started (Phase X cognitive routing)")

    while True:
        try:
            user_input = cli.get_user_input()
            if not user_input:
                continue

            command, argument = cli.parse_command(user_input)

            if command:
                if command in ("quit", "exit", "bye"):
                    break
                elif command == "help":
                    cli.show_help()
                elif command == "memory":
                    cli.show_memory_info(memory.format_status())
                elif command == "facts":
                    cli.show_facts(memory.long_term.get_all_facts())
                elif command == "clear":
                    memory.short_term.clear()
                    cli.show_system_message("Conversation history cleared.")
                elif command == "status":
                    cli.show_system_message(
                        memory.format_status() + "\n" + personality.get_session_summary()
                    )
                elif command == "remember" and argument:
                    memory.save_explicit_memory(argument)
                    cli.show_success(f"Saved to memory: {argument}")
                elif command == "search" and argument:
                    results = memory.search(argument)
                    cli.show_memories(
                        results.get("semantic_results") or results.get("keyword_results", [])
                    )
                else:
                    cli.show_error(f"Unknown command: /{command}. Type /help.")
                continue

            memory.add_user_message(user_input)
            request_start = time.perf_counter()

            decision = cognitive_router.classify(user_input, llm_interface=llm) if cognitive_router else None
            depth = decision.response_depth if decision else 0.5
            path = decision.path if decision else CognitivePath.FAST

            # Phase X: Build memory context with relevance engine + smart cache
            _cache_key = f"memctx:{user_input[:50]}"
            if smart_cache:
                memory_context = smart_cache.get_memory(_cache_key)
            if not memory_context:
                memory_context = memory.get_context_for_llm(query=user_input)
                if memory_relevance and depth >= 0.4:
                    try:
                        raw_search = memory.search(user_input)
                        semantic = raw_search.get("semantic_results") or []
                        if len(semantic) > 2:
                            ranked = memory_relevance.rank_memories(
                                query=user_input,
                                semantic_results=semantic,
                                active_project=getattr(memory, '_active_project', None),
                            )
                            selected = memory_relevance.select_top(
                                ranked,
                                max_items=3 if depth < 0.5 else 5,
                                max_estimate_chars=int(depth * 2000),
                            )
                            ranked_text = memory_relevance.format_for_prompt(selected)
                            if ranked_text:
                                memory_context = f"{memory_context}\n\n## Ranked Memories\n{ranked_text}"
                    except Exception:
                        pass
                if smart_cache:
                    smart_cache.set_memory(_cache_key, memory_context, ttl=120)

            extra_context = get_context_enhancement(hyper_engine, user_input)
            if extra_context:
                memory_context = f"{memory_context}\n\n{extra_context}" if memory_context else extra_context

            hyper_packet = prepare_hyper_turn(hyper_engine, user_input, memory=memory)
            if hyper_packet.get("system_context"):
                memory_context = (
                    f"{memory_context}\n\n{hyper_packet['system_context']}"
                    if memory_context
                    else hyper_packet["system_context"]
                )

            depth_instruction = cognitive_router.get_depth_instruction(decision) if cognitive_router else ""
            path_instruction = cognitive_router.get_path_instruction(decision) if cognitive_router else ""
            if depth_instruction or path_instruction:
                instr = "\n".join(filter(None, [depth_instruction, path_instruction]))
                memory_context = f"{memory_context}\n\n{instr}" if memory_context else instr

            system_prompt = get_system_prompt(
                user_name=settings.USER_NAME,
                memory_context=memory_context,
            )
            messages = memory.get_conversation_history()

            cli.start_joseph_response()
            full_response = ""

            try:
                for chunk in llm.chat_stream(messages=messages, system_prompt=system_prompt):
                    cli.print_stream_chunk(chunk)
                    full_response += chunk
            except (ConnectionError, ValueError) as e:
                cli.end_joseph_response()
                cli.show_error(str(e))
                memory.short_term._messages.pop() if memory.short_term._messages else None
                continue

            cli.end_joseph_response()
            final_response = personality.format_response(full_response)
            final_response = enhance_response(hyper_engine, user_input, final_response, context={"mode": "cli"})

            final_response = quality_check(final_response, user_input)

            memory.add_assistant_message(final_response)
            latency_ms = (time.perf_counter() - request_start) * 1000

            if decision is not None:
                decision.latency.total_ms = latency_ms
                decision.latency.llm_ms = latency_ms * 0.7

            finalize_hyper_turn(
                hyper_engine,
                user_input,
                final_response,
                elapsed_seconds=latency_ms / 1000,
                memory=memory,
            )

            try:
                memory.extract_and_save_facts(user_input, llm)
                memory.maybe_summarize(llm)
            except Exception:
                pass

            if continuity_engine:
                try:
                    continuity_engine.record_turn(user_input, final_response)
                except Exception:
                    pass

            if consolidation_engine:
                try:
                    consolidation_engine.consolidate_conversation(
                        user_messages=[user_input],
                        assistant_messages=[final_response],
                        session_id=memory.session_id,
                    )
                except Exception:
                    pass

        except KeyboardInterrupt:
            print()
            cli.show_system_message("Use /quit to exit.")
        except Exception as e:
            logger.exception(f"CLI loop error: {e}")

    if continuity_engine:
        continuity_engine.record_session_end()
    try:
        memory.end_session()
    except Exception:
        pass

    if consolidation_engine and memory.short_term.total_added >= 2:
        try:
            summary = memory.short_term.get_conversation_text()[:500]
            consolidation_engine.consolidate_session_end(
                session_id=memory.session_id,
                summary=summary,
                message_count=memory.short_term.total_added,
            )
        except Exception:
            pass

    shutdown_hyper(hyper_engine)

    from ui.cli_interface import CLIInterface
    CLIInterface().show_goodbye()


def main():
    """Main startup sequence."""
    logger.info("=" * 60)
    logger.info(f"Starting {settings.JOSEPH_NAME} v1.0 — Phase 1")
    logger.info("=" * 60)

    settings.ensure_directories()

    # Parse args
    use_cli = "--cli" in sys.argv

    # Initialize core components
    llm = LLMInterface()
    memory = MemoryManager()
    personality = PersonalityEngine()
    hyper_engine = create_hyper_engine(llm=llm, memory=memory, personality=personality)

    # Phase X: Cognitive Architecture (initialized early so all subsystems can use it)
    cognitive_router = CognitiveRouter()
    memory_relevance = MemoryRelevanceEngine()
    smart_cache = SmartCache()
    logger.info("Phase X: Cognitive architecture initialized")

    # Phase 6: assistant router (orchestration layer)
    router = create_router(llm=llm, memory=memory, hyper_engine=hyper_engine,
                          memory_relevance=memory_relevance, smart_cache=smart_cache)
    logger.info("Phase 6: AssistantRouter created")

    # Phase 7: advanced capability engines
    activity_tracker = ActivityTracker()
    insight_engine = InsightEngine(activity_tracker=activity_tracker)
    research_workspace = ResearchWorkspace()
    followup_engine = FollowUpEngine(
        research_workspace=research_workspace,
    )
    ambient_intel = AmbientIntelligence(
        activity_tracker=activity_tracker,
    )
    project_awareness = ProjectAwareness()
    logger.info("Phase 7: Capability engines initialized")

    # Phase 8: Personal Operating System
    decision_history = DecisionHistory()
    workspace_manager = WorkspaceManager(
        research_workspace=research_workspace,
    )
    project_commander = ProjectCommander(
        workspace_manager=workspace_manager,
    )
    roadmap_engine = RoadmapEngine(
        workspace_manager=workspace_manager,
    )
    weekly_review = WeeklyReview(
        workspace_manager=workspace_manager,
        project_commander=project_commander,
        activity_tracker=activity_tracker,
        insight_engine=insight_engine,
        research_workspace=research_workspace,
    )
    briefing_v2 = BriefingV2(
        workspace_manager=workspace_manager,
        project_commander=project_commander,
        weekly_review=weekly_review,
        activity_tracker=activity_tracker,
        insight_engine=insight_engine,
        research_workspace=research_workspace,
    )
    project_memory = ProjectMemory(
        memory_manager=memory,
        workspace_manager=workspace_manager,
        project_store=None,
    )
    research_pipeline = ResearchPipeline(
        research_workspace=research_workspace,
    )
    learning_companion = LearningCompanion(
        roadmap_engine=roadmap_engine,
        workspace_manager=workspace_manager,
    )
    continuity_engine = ContinuityEngine(
        workspace_manager=workspace_manager,
        project_commander=project_commander,
        activity_tracker=activity_tracker,
        decision_history=decision_history,
    )
    consolidation_engine = MemoryConsolidationEngine()
    logger.info(f"Memory consolidation loaded: {consolidation_engine.memory_count} memories")

    # Phase 9: Vision, Document Intelligence, Computer Awareness
    document_intelligence = DocumentIntelligence()
    vision_engine = VisionEngine()
    paper_analyzer = PaperAnalyzer(
        document_intelligence=document_intelligence,
        research_workspace=research_workspace,
    )
    screen_awareness = ScreenAwareness()
    code_vision = CodeVision(vision_engine=vision_engine)
    diagram_analyzer = DiagramAnalyzer(vision_engine=vision_engine)
    multimodal_memory = MultimodalMemory()
    background_research = BackgroundResearch(
        llm=llm,
        research_workspace=research_workspace,
        research_pipeline=research_pipeline,
    )
    logger.info("Phase 9: Vision/Document engines initialized")

    # Health check
    if use_cli:
        from ui.cli_interface import CLIInterface
        cli = CLIInterface()
        cli.show_system_message(f"Connecting to Ollama ({settings.OLLAMA_BASE_URL})...")
        if not llm.health_check():
            cli.show_error(
                f"Cannot connect to Ollama or model '{settings.OLLAMA_MODEL}' not found.\n"
                f"  1. Ollama should be running automatically on Windows.\n"
                f"  2. Pull the model: ollama pull {settings.OLLAMA_MODEL}"
            )
            sys.exit(1)
        cli.show_success(f"Connected to {llm.get_active_model()}")
    else:
        if not llm.health_check():
            # Show error in a simple popup if GUI fails before launching
            try:
                import customtkinter as ctk
                import tkinter.messagebox as mb
                root = ctk.CTk()
                root.withdraw()
                mb.showerror(
                    "JOSEPH — Connection Error",
                    f"Cannot connect to Ollama.\n\n"
                    f"Make sure Ollama is installed and the model is pulled:\n"
                    f"  ollama pull {settings.OLLAMA_MODEL}\n\n"
                    f"Ollama runs automatically on Windows after install.",
                )
                root.destroy()
            except Exception:
                print(f"ERROR: Cannot connect to Ollama. Run: ollama pull {settings.OLLAMA_MODEL}")
            sys.exit(1)

    # Launch
    if use_cli:
        run_cli(
            llm, memory, personality,
            hyper_engine=hyper_engine,
            continuity_engine=continuity_engine,
            consolidation_engine=consolidation_engine,
            cognitive_router=cognitive_router,
            memory_relevance=memory_relevance,
            smart_cache=smart_cache,
        )
    else:
        run_gui(
            llm, memory, personality,
            hyper_engine=hyper_engine,
            router=router,
            activity_tracker=activity_tracker,
            project_awareness=project_awareness,
            insight_engine=insight_engine,
            research_workspace=research_workspace,
            followup_engine=followup_engine,
            ambient_intel=ambient_intel,
            workspace_manager=workspace_manager,
            project_commander=project_commander,
            roadmap_engine=roadmap_engine,
            weekly_review=weekly_review,
            briefing_v2=briefing_v2,
            project_memory=project_memory,
            research_pipeline=research_pipeline,
            learning_companion=learning_companion,
            decision_history=decision_history,
            continuity_engine=continuity_engine,
            consolidation_engine=consolidation_engine,
            document_intelligence=document_intelligence,
            vision_engine=vision_engine,
            paper_analyzer=paper_analyzer,
            screen_awareness=screen_awareness,
            code_vision=code_vision,
            diagram_analyzer=diagram_analyzer,
            multimodal_memory=multimodal_memory,
            background_research=background_research,
            cognitive_router=cognitive_router,
            memory_relevance=memory_relevance,
            smart_cache=smart_cache,
        )

    shutdown_hyper(hyper_engine)
    logger.info(f"{settings.JOSEPH_NAME} shutdown complete.")


if __name__ == "__main__":
    main()
