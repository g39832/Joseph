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


def run_gui(
    llm: LLMInterface,
    memory: MemoryManager,
    personality: PersonalityEngine,
    hyper_engine=None,
):
    """Launch the desktop GUI."""
    try:
        from ui.app import JosephApp
        app = JosephApp(
            llm=llm,
            memory=memory,
            personality=personality,
            hyper_engine=hyper_engine,
        )
        app.mainloop()
    except ImportError as e:
        logger.error(f"GUI failed to import: {e}")
        print(f"\nGUI unavailable: {e}")
        print("Falling back to CLI. Run with --cli to skip this message.\n")
        run_cli(llm, memory, personality, hyper_engine=hyper_engine)

def run_cli(
    llm: LLMInterface,
    memory: MemoryManager,
    personality: PersonalityEngine,
    hyper_engine=None,
):
    """Launch the terminal CLI interface."""
    from ui.cli_interface import CLIInterface

    cli = CLIInterface()
    memory.start_session()
    if hyper_engine and hasattr(hyper_engine, "set_session_context"):
        hyper_engine.set_session_context(memory.session_id)

    cli.show_welcome(memory_status=memory.format_status())
    cli.show_joseph_response(personality.get_greeting())

    logger.info("CLI chat loop started")

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
            memory_context = memory.get_context_for_llm(query=user_input)
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
            system_prompt = get_system_prompt(
                user_name=settings.USER_NAME,
                memory_context=memory_context,
            )
            messages = memory.get_conversation_history()

            cli.start_joseph_response()
            full_response = ""
            response_started = time.perf_counter()

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
            memory.add_assistant_message(final_response)
            finalize_hyper_turn(
                hyper_engine,
                user_input,
                final_response,
                elapsed_seconds=time.perf_counter() - response_started,
                memory=memory,
            )

            try:
                memory.extract_and_save_facts(user_input, llm)
                memory.maybe_summarize(llm)
            except Exception:
                pass

        except KeyboardInterrupt:
            print()
            cli.show_system_message("Use /quit to exit.")
        except Exception as e:
            logger.exception(f"CLI loop error: {e}")

    try:
        memory.end_session()
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
        run_cli(llm, memory, personality, hyper_engine=hyper_engine)
    else:
        run_gui(llm, memory, personality, hyper_engine=hyper_engine)

    shutdown_hyper(hyper_engine)
    logger.info(f"{settings.JOSEPH_NAME} shutdown complete.")


if __name__ == "__main__":
    main()
