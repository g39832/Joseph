"""
brain/background_research.py
------------------------------
Background Research Engine — researches topics without opening a browser.

Searches the web via DuckDuckGo API, reads top result pages, synthesizes
findings with LLM, and stores results in ResearchWorkspace + ResearchPipeline.
Runs in a background thread with progress callbacks.

Usage:
    br = BackgroundResearch(llm=llm, research_workspace=rw)
    def on_progress(stage, msg):
        print(f"[{stage}] {msg}")
    br.research("Python async programming", on_progress=on_progress)
"""

import logging
import re
import threading
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class BackgroundResearch:
    """
    Background web research engine.

    Researches topics without opening a browser by using web APIs
    and HTTP requests. Progress is reported via callbacks.
    """

    def __init__(
        self,
        llm=None,
        research_workspace=None,
        research_pipeline=None,
    ):
        self._llm = llm
        self._rw = research_workspace
        self._rp = research_pipeline
        self._active_research: dict[str, threading.Thread] = {}

    def research(
        self,
        query: str,
        on_progress: Optional[Callable[[str, str], None]] = None,
        on_complete: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """
        Start background research on a topic.

        Args:
            query: The research topic or question.
            on_progress: Callback(stage, message) where stage is one of:
                "searching", "reading", "synthesizing", "storing", "complete"
            on_complete: Callback(topic, summary) when research finishes.

        Returns:
            "Research started" confirmation message.
        """
        if self.is_researching(query):
            return f"Already researching '{query}' — I'll update you when I find something."
        thread = threading.Thread(
            target=self._run_research,
            args=(query, on_progress, on_complete),
            daemon=True,
        )
        thread.start()
        self._active_research[query] = thread
        return f"Researching '{query}' in the background — I'll show progress as I go."

    def _run_research(
        self,
        query: str,
        on_progress: Optional[Callable[[str, str], None]],
        on_complete: Optional[Callable[[str, str], None]],
    ):
        """Run the full research pipeline in a background thread."""
        try:
            self._report(on_progress, "searching", f"Searching for information about '{query}'...")

            results = self._search_web(query)
            if not results:
                self._report(on_progress, "complete", f"No results found for '{query}'.")
                return

            self._report(on_progress, "reading", f"Reading top {len(results)} sources...")
            enriched = self._enrich_results(results)

            self._report(on_progress, "synthesizing", "Synthesizing findings...")
            summary = self._synthesize(query, enriched)

            self._report(on_progress, "storing", "Saving research findings...")
            self._store_results(query, summary, enriched)

            self._report(on_progress, "complete", summary)

            if on_complete:
                on_complete(query, summary)

        except Exception as e:
            logger.error(f"Background research error: {e}")
            self._report(
                on_progress, "error",
                f"Research failed: {e}",
            )

    def _search_web(self, query: str) -> list[dict]:
        """Search the web using DuckDuckGo API — no browser needed."""
        try:
            import requests
            from urllib.parse import quote_plus

            url = (
                f"https://api.duckduckgo.com/"
                f"?q={quote_plus(query)}&format=json&no_html=1&t=joseph_assistant"
            )
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            })
            if not resp.ok:
                logger.warning(f"DuckDuckGo API returned {resp.status_code}")
                return []

            data = resp.json()
            results = []

            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", "Summary"),
                    "source": data.get("AbstractSource", "DuckDuckGo"),
                    "url": data.get("AbstractURL", ""),
                    "content": data["AbstractText"],
                })

            for topic in data.get("RelatedTopics", []):
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "").split(" - ")[0],
                        "source": "DuckDuckGo Related",
                        "url": topic.get("FirstURL", ""),
                        "content": topic["Text"],
                    })
                if len(results) >= 5:
                    break

            return results

        except Exception as e:
            logger.debug(f"Web search error: {e}")
            return []

    def _enrich_results(self, results: list[dict]) -> list[dict]:
        """Fetch full page content for top results."""
        import requests
        from urllib.parse import urlparse

        enriched = []
        for r in results[:3]:
            url = r.get("url", "")
            if not url or not urlparse(url).scheme:
                enriched.append(r)
                continue
            try:
                page_resp = requests.get(
                    url, timeout=8,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if page_resp.ok:
                    text = self._extract_text(page_resp.text)
                    r["content"] = text[:3000]
            except Exception:
                pass
            enriched.append(r)
        return enriched

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML."""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        lines = []
        for line in text.split("."):
            line = line.strip()
            if len(line) > 30:
                lines.append(line)
        return ". ".join(lines[:50])

    def _synthesize(self, query: str, results: list[dict]) -> str:
        """Synthesize findings into a coherent summary using LLM."""
        if not results:
            return f"No information found about '{query}'."

        if not self._llm:
            parts = [f"From {r['source']}: {r['content'][:500]}" for r in results]
            return "\n\n".join(parts)

        sources_text = "\n\n".join([
            f"Source {i+1} ({r['source']}):\n{r['content'][:1000]}"
            for i, r in enumerate(results)
        ])

        prompt = f"""You are a research assistant. Synthesize the following search results
into a clear, informative answer about the topic.

Topic: {query}

Sources:
{sources_text}

Provide a well-structured summary covering the key points. Keep it concise but thorough.
If the user asked a specific question, answer it directly.

Summary:"""

        try:
            raw = self._llm.generate(prompt, temperature=0.3)
            return raw.strip()
        except Exception as e:
            logger.debug(f"Synthesis error: {e}")
            return results[0]["content"][:1000] if results else "No results."

    def _store_results(
        self,
        query: str,
        summary: str,
        results: list[dict],
    ):
        """Store research findings to workspace and pipeline."""
        # Store to ResearchWorkspace
        entry_id = None
        if self._rw:
            try:
                sources_list = [
                    {"title": r.get("title", ""), "url": r.get("url", "")}
                    for r in results if r.get("url")
                ]
                entry_id = self._rw.add_entry(
                    query=query,
                    notes=summary[:2000],
                    sources=sources_list if sources_list else None,
                    tags=["web_research", "background"],
                )
                logger.info(f"Research saved to workspace: {entry_id}")
            except Exception as e:
                logger.warning(f"Failed to store to workspace: {e}")

        # Create/update ResearchPipeline thread
        if self._rp:
            try:
                thread_id = self._rp.create_thread(
                    topic=query,
                )
                self._rp.add_note(thread_id, summary[:2000], author="web")
                for r in results:
                    if r.get("url"):
                        self._rp.add_source(thread_id, r["content"][:500], url=r["url"])
                self._rp.close_thread(thread_id)
                logger.info(f"Research thread created: {thread_id}")
            except Exception as e:
                logger.warning(f"Failed to create research thread: {e}")

    def _report(
        self,
        callback: Optional[Callable[[str, str], None]],
        stage: str,
        message: str,
    ):
        """Report progress via callback."""
        if callback:
            try:
                callback(stage, message)
            except Exception:
                pass
        logger.debug(f"[{stage}] {message[:100]}")

    def is_researching(self, query: str = "") -> bool:
        """Check if research is active."""
        if query:
            t = self._active_research.get(query)
            return t is not None and t.is_alive()
        return any(t.is_alive() for t in self._active_research.values())
