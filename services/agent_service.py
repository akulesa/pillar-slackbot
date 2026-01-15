"""
Agentic service using Claude's tool use capability.
Supports multi-step reasoning - Claude can call multiple tools in sequence.
"""
from typing import List, Dict, Any, Optional, Callable
from anthropic import Anthropic
from config import Config


# Tool definitions for Claude
TOOLS = [
    {
        "name": "add_to_agenda",
        "description": "Add an item to the Monday Investment Review meeting agenda. Use this when someone asks to add something to the agenda, or says 'agenda this', 'add to monday meeting', etc. The item will be stored and included in the next agenda document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The agenda item content - what should be discussed"
                },
                "category": {
                    "type": "string",
                    "enum": ["Investment Decisions", "Pipeline", "Portfolio Updates", "Other"],
                    "description": "Category for the agenda item"
                }
            },
            "required": ["content", "category"]
        }
    },
    {
        "name": "view_agenda",
        "description": "View all pending items on the Monday Investment Review agenda. Use when someone asks to see the agenda, what's on the agenda, etc.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "read_files",
        "description": "Read and analyze files that are attached to the current Slack message or thread. Returns the text content of PDFs and documents, or describes images.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "What to look for or extract from the files"
                }
            },
            "required": ["question"]
        }
    },
    {
        "name": "get_channel_history",
        "description": "Get recent message history from the current Slack channel. Use this to see what's been discussed, find shared files, or understand context. Returns messages with timestamps, authors, and any file attachments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "How many hours of history to fetch (default 24, max 168)",
                    "default": 24
                }
            },
            "required": []
        }
    },
    {
        "name": "read_file_by_name",
        "description": "Read a specific file from the channel history by its name. Use this after get_channel_history if you need to read a file that was shared earlier in the channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "The name of the file to read (or partial match)"
                },
                "question": {
                    "type": "string",
                    "description": "What to look for in this file"
                }
            },
            "required": ["file_name"]
        }
    },
    {
        "name": "fetch_url",
        "description": "Fetch and read content from a URL or webpage. Returns the page text content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "search_web",
        "description": "Search the web for current/real-time information. Use for stock prices, recent news, current events, or anything requiring up-to-date information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_portfolio_company_channel",
        "description": "Get recent updates from a portfolio company's dedicated Slack channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Name of the portfolio company"
                }
            },
            "required": ["company_name"]
        }
    }
]

SYSTEM_PROMPT = """You are the Pillar VC Slack bot - a helpful assistant for a venture capital firm.

You have access to tools that let you:
- Add items to the Monday Investment Review agenda
- View the current agenda
- Read files attached to messages
- Get channel history to see recent discussions and find shared files
- Read specific files from channel history by name
- Fetch web pages
- Search the web for current information
- Get portfolio company updates

IMPORTANT: You can use multiple tools in sequence to answer complex questions. For example:
- If asked about files shared in a channel, first use get_channel_history to find them, then use read_file_by_name to read specific ones
- If asked to add something to the agenda, extract the key point and add it with the appropriate category
- If someone replies to a message and says "add this to the agenda", use the context from the parent message

After gathering all the information you need, provide a final answer.

TONE: Be concise and casual - this is Slack, not a memo. Use bullet points. Keep it tight. A little wit is ok but stay helpful."""


class AgentService:
    """
    Agentic service that runs a tool-use loop.
    Claude can call multiple tools in sequence until it has enough info to answer.
    """

    def __init__(self):
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"

    def run(
        self,
        user_message: str,
        tool_executors: Dict[str, Callable],
        context: Dict[str, Any],
        max_steps: int = 5,
        on_status: Callable[[str], None] = None
    ) -> str:
        """
        Run the agent loop until Claude provides a final answer.

        Args:
            user_message: The user's request
            tool_executors: Dict mapping tool names to executor functions
                           Each executor takes (tool_input, context) and returns str
            context: Context dict with channel_id, files, urls, etc.
            max_steps: Maximum number of tool calls before forcing an answer
            on_status: Optional callback to report status updates

        Returns:
            Final response text
        """
        # Build initial context description
        context_parts = []
        if context.get("parent_message"):
            context_parts.append(f"User is replying to this message: \"{context['parent_message']}\"")
        if context.get("has_files"):
            file_names = context.get("file_names", [])
            context_parts.append(f"Files attached: {', '.join(file_names)}")
        if context.get("urls"):
            context_parts.append(f"URLs in message: {', '.join(context['urls'])}")

        context_str = "\n".join(context_parts) if context_parts else "No files or URLs in the current message."

        messages = [
            {
                "role": "user",
                "content": f"""Current context:
{context_str}

User's request: {user_message}

Use the available tools to gather information and answer the request. You can call multiple tools if needed."""
            }
        ]

        # Agent loop
        for step in range(max_steps):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

            # Check if Claude wants to use tools
            tool_uses = [block for block in response.content if block.type == "tool_use"]

            if not tool_uses:
                # No tool calls - Claude is done, extract final text
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return "I couldn't find the information you need."

            # Execute each tool call
            tool_results = []
            for tool_use in tool_uses:
                tool_name = tool_use.name
                tool_input = tool_use.input

                if on_status:
                    on_status(f"_{self._get_status_message(tool_name, tool_input)}_")

                # Execute the tool
                if tool_name in tool_executors:
                    try:
                        result = tool_executors[tool_name](tool_input, context)
                    except Exception as e:
                        result = f"Error: {str(e)}"
                else:
                    result = f"Tool '{tool_name}' is not available."

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result[:50000]  # Truncate very long results
                })

            # Add assistant's tool calls and results to conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        # Max steps reached - ask for final answer
        messages.append({
            "role": "user",
            "content": "Please provide your final answer based on the information gathered so far."
        })

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=messages
        )

        for block in response.content:
            if hasattr(block, "text"):
                return block.text

        return "I gathered some information but couldn't formulate a complete answer."

    def _get_status_message(self, tool_name: str, tool_input: dict) -> str:
        """Generate a user-friendly status message for a tool call."""
        if tool_name == "add_to_agenda":
            return "Adding to Monday agenda..."
        elif tool_name == "view_agenda":
            return "Checking the agenda..."
        elif tool_name == "get_channel_history":
            hours = tool_input.get("hours", 24)
            return f"Scanning last {hours} hours of channel history..."
        elif tool_name == "read_files":
            return "Reading attached files..."
        elif tool_name == "read_file_by_name":
            file_name = tool_input.get("file_name", "file")
            return f"Reading {file_name}..."
        elif tool_name == "fetch_url":
            url = tool_input.get("url", "")[:50]
            return f"Fetching {url}..."
        elif tool_name == "search_web":
            query = tool_input.get("query", "")[:30]
            return f"Searching: {query}..."
        elif tool_name == "get_portfolio_company_channel":
            company = tool_input.get("company_name", "company")
            return f"Getting updates on {company}..."
        else:
            return f"Working..."
