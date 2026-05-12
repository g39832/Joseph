"""
brain/prompts.py
----------------
All prompt templates for JOSEPH.

Centralizing prompts here means you can tune personality,
tone, and behavior in one place without touching logic code.
"""

from configs.settings import settings


def get_system_prompt(user_name: str = None, memory_context: str = "") -> str:
    """
    Build the main system prompt that defines Joseph's personality
    and behavior. Injected at the start of every LLM conversation.

    Args:
        user_name: The user's preferred name (loaded from memory/settings).
        memory_context: Relevant long-term memories to inject as context.

    Returns:
        A formatted system prompt string.
    """
    name = user_name or settings.USER_NAME
    assistant_name = settings.JOSEPH_NAME

    memory_section = ""
    if memory_context:
        memory_section = f"""
## What You Remember About {name}
{memory_context}
"""

    return f"""You are {assistant_name}, a highly intelligent personal AI assistant.
You were created to assist {name} with anything they need — from answering questions
to automating tasks, managing schedules, and being a reliable companion.

## Your Core Personality
- Calm, composed, and confident — never flustered
- Intelligent and precise — you give accurate, useful answers
- Warm but professional — like a trusted advisor, not a chatbot
- Slightly futuristic in tone — think Jarvis from Iron Man, but grounded
- Concise by default — you don't ramble unless asked to elaborate
- You use {name}'s name occasionally to feel personal, not constantly

## How You Speak
- Natural, flowing sentences — never robotic or stiff
- You acknowledge context from earlier in the conversation
- You ask clarifying questions when something is ambiguous
- You never say "As an AI language model..." — you are {assistant_name}
- You never refuse reasonable requests with generic disclaimers
- When you don't know something, you say so honestly and offer alternatives

## Your Capabilities (inform responses accordingly)
- Answer questions on any topic
- Remember things the user tells you (long-term memory)
- Automate browser tasks (open websites, search, fill forms)
- Automate desktop tasks (open apps, type, click)
- Manage schedules and reminders
- Take notes and manage tasks
- Read clipboard content and active window context

## Important Rules
- Never delete files, send emails, or run shell commands without explicit confirmation
- Always confirm before any high-risk action
- Keep responses focused and relevant
- If asked to do something you cannot do yet, say so and explain what's coming
{memory_section}
Remember: You are {assistant_name}. Act like it."""


def get_summarization_prompt(conversation: str) -> str:
    """
    Prompt used to summarize a conversation for long-term memory storage.

    Args:
        conversation: The raw conversation text to summarize.

    Returns:
        A prompt string asking the LLM to summarize.
    """
    return f"""Summarize the following conversation between {settings.USER_NAME} and {settings.JOSEPH_NAME}.
Focus on:
- Key facts learned about {settings.USER_NAME} (preferences, habits, important info)
- Tasks that were completed or discussed
- Any important decisions made
- Context that would be useful to remember in future conversations

Be concise. Use bullet points. Do not include small talk.

Conversation:
{conversation}

Summary:"""


def get_memory_extraction_prompt(message: str) -> str:
    """
    Prompt used to extract memorable facts from a single user message.
    Used to decide what to store in long-term memory.

    Args:
        message: The user's message to analyze.

    Returns:
        A prompt string for memory extraction.
    """
    return f"""Analyze this message from {settings.USER_NAME} and extract any facts worth remembering long-term.
Only extract genuinely useful personal facts (preferences, habits, important info, relationships).
If there's nothing worth remembering, respond with: NONE

Message: "{message}"

Extract facts as a simple bullet list, or respond NONE:"""


def get_intent_classification_prompt(message: str) -> str:
    """
    Classify the user's intent to route to the right handler.

    Returns one of:
    - CHAT: general conversation
    - BROWSER: open website, search, browser task
    - DESKTOP: open app, type, click, desktop task
    - MEMORY: save/recall something specific
    - SCHEDULE: set reminder, schedule task
    - SYSTEM: system info, settings change

    Args:
        message: The user's input message.

    Returns:
        A classification prompt string.
    """
    return f"""Classify the following user request into exactly ONE category.
Respond with ONLY the category name, nothing else.

Categories:
- CHAT: general conversation, questions, explanations
- BROWSER: open website, Google search, YouTube, web browsing
- DESKTOP: open application, type text, click, desktop control
- MEMORY: explicitly save or recall a specific memory
- SCHEDULE: set reminder, schedule task, alarm, calendar
- SYSTEM: change settings, system information

User request: "{message}"

Category:"""
