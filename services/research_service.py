from typing import Optional, List, Dict
from anthropic import Anthropic
from tavily import TavilyClient

from config import Config


class ResearchService:
    """Service for research queries using Claude with Tavily web search."""

    def __init__(self):
        self.anthropic = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.tavily = TavilyClient(api_key=Config.TAVILY_API_KEY) if Config.TAVILY_API_KEY else None
        self.model = "claude-sonnet-4-20250514"

    def is_available(self) -> bool:
        """Check if research service is available."""
        return self.tavily is not None

    def search(self, query: str) -> str:
        """Perform a web search using Tavily."""
        if not self.tavily:
            return "Web search is not configured."

        try:
            response = self.tavily.search(
                query=query,
                search_depth="basic",
                max_results=5
            )

            # Format results
            results = []
            for item in response.get("results", []):
                title = item.get("title", "")
                content = item.get("content", "")
                url = item.get("url", "")
                results.append(f"Title: {title}\nContent: {content}\nSource: {url}")

            return "\n\n---\n\n".join(results) if results else "No results found."

        except Exception as e:
            print(f"Tavily search error: {e}")
            return f"Search error: {str(e)}"

    def research(self, question: str) -> str:
        """Answer a research question by searching and synthesizing results."""
        if not self.tavily:
            return "Web search is not configured. Please add TAVILY_API_KEY to your environment."

        # First, search for relevant information
        search_results = self.search(question)

        if "error" in search_results.lower() or search_results == "No results found.":
            return f"I couldn't find information about that. Search returned: {search_results}"

        # Now use Claude to synthesize the results
        prompt = f"""You're the Pillar VC bot doing some quick research.

TONE: Be concise and casual - this is Slack, not a memo. Use bullet points. Skip corporate speak.

Question: "{question}"

Web search results:
{search_results}

Give them the answer:
- Direct answer first
- Key details (bullets)
- Sources

Keep it tight. If search didn't fully answer it, say so briefly."""

        response = self.anthropic.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text
