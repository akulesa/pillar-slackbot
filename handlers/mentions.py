"""
Mention handler using Claude's agentic tool use.
Claude can call multiple tools in sequence for complex queries.
"""
from slack_bolt import App
import re
from typing import Dict, Any

from services import ClaudeService, FileService, WebService, ResearchService, AgentService
from utils import SlackUtils, MessageFormatter, markdown_to_slack
from database import save_user_last_active, add_agenda_item, get_pending_agenda_items


def register_mentions(app: App):
    """Register mention event handlers."""

    claude = ClaudeService()
    file_service = FileService()
    web_service = WebService()
    research_service = ResearchService()
    agent = AgentService()

    @app.event("app_mention")
    def handle_mention(event, client, say):
        """Handle @mentions of the bot using Claude's agentic tool use."""
        user_id = event.get("user")
        channel_id = event.get("channel")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        event_ts = event.get("ts")

        slack_utils = SlackUtils(client)

        # Remove the bot mention from the text
        clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

        if not clean_text:
            say(
                text="Hey! I'm the Pillar VC bot. Ask me to summarize this channel, analyze a file, fetch a link, find action items, or research something.",
                thread_ts=thread_ts
            )
            return

        # Gather context
        context = {
            "channel_id": channel_id,
            "user_id": user_id,
            "has_files": False,
            "files": [],
            "file_names": [],
            "urls": [],
            "parent_message": None,  # Text of message being replied to
            "slack_utils": slack_utils,
            "client": client,
        }

        # Check for files in the current message
        if event.get("files"):
            context["has_files"] = True
            context["files"] = event.get("files")
            context["file_names"] = [f.get("name", "file") for f in event.get("files")]

        # Check for files/URLs in parent message if this is a thread reply
        if thread_ts and thread_ts != event_ts:
            parent_text, parent_files = get_thread_parent_content(client, channel_id, thread_ts)

            # Store parent message text for agenda/context
            if parent_text:
                context["parent_message"] = parent_text

            if parent_files and not context["has_files"]:
                context["has_files"] = True
                context["files"] = parent_files
                context["file_names"] = [f.get("name", "file") for f in parent_files]

            if parent_text:
                parent_urls = web_service.extract_urls_from_text(parent_text)
                context["urls"].extend(parent_urls)

        # Check for URLs in current message
        urls_in_message = web_service.extract_urls_from_text(text)
        context["urls"].extend(urls_in_message)
        context["urls"] = list(set(context["urls"]))

        # Build tool executors
        tool_executors = build_tool_executors(
            file_service=file_service,
            web_service=web_service,
            research_service=research_service,
            claude=claude,
            slack_utils=slack_utils
        )

        # Status callback to show progress
        def on_status(message: str):
            say(text=message, thread_ts=thread_ts)

        say(text="_Thinking..._", thread_ts=thread_ts)

        try:
            # Run the agent loop
            result = agent.run(
                user_message=clean_text,
                tool_executors=tool_executors,
                context=context,
                max_steps=5,
                on_status=on_status
            )

            # Save user activity
            save_user_last_active(user_id)

            # Send final response
            formatted = markdown_to_slack(result)
            send_response(say, formatted, thread_ts)

        except Exception as e:
            print(f"Agent error: {e}")
            import traceback
            traceback.print_exc()
            say(text="Sorry, something went wrong. Try again?", thread_ts=thread_ts)


def get_thread_parent_content(client, channel_id: str, thread_ts: str):
    """Get text and files from the parent message of a thread."""
    try:
        result = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=1,
            inclusive=True
        )
        if result.get("messages"):
            parent_message = result["messages"][0]
            return parent_message.get("text", ""), parent_message.get("files", [])
    except Exception as e:
        print(f"Error getting thread parent: {e}")
    return "", []


def build_tool_executors(file_service, web_service, research_service, claude, slack_utils):
    """Build the tool executor functions for the agent."""

    # Store files found in channel history for later retrieval
    channel_files_cache = {}

    def execute_add_to_agenda(tool_input: dict, context: dict) -> str:
        """Add an item to the Monday Investment Review agenda."""
        content = tool_input.get("content", "")
        category = tool_input.get("category", "Other")
        user_id = context.get("user_id", "unknown")
        channel_id = context.get("channel_id", "unknown")

        if not content:
            return "No content provided for the agenda item."

        # Validate category
        valid_categories = ["Investment Decisions", "Pipeline", "Portfolio Updates", "Other"]
        if category not in valid_categories:
            category = "Other"

        # Add to database
        add_agenda_item(user_id, channel_id, category, content)

        return f"Added to Monday agenda under '{category}': {content}"

    def execute_view_agenda(tool_input: dict, context: dict) -> str:
        """View all pending agenda items."""
        items = get_pending_agenda_items()

        if not items:
            return "The Monday agenda is empty. No items have been added yet."

        # Group by category
        by_category = {}
        for item in items:
            cat = item["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)

        # Format output
        lines = ["Current Monday Investment Review Agenda:", ""]
        for category in ["Investment Decisions", "Pipeline", "Portfolio Updates", "Other"]:
            if category in by_category:
                lines.append(f"{category}:")
                for item in by_category[category]:
                    lines.append(f"  - {item['content']}")
                lines.append("")

        return "\n".join(lines)

    def execute_read_files(tool_input: dict, context: dict) -> str:
        """Read files attached to the current message."""
        files = context.get("files", [])
        question = tool_input.get("question", "summarize")

        if not files:
            return "No files are attached to this message. Use get_channel_history to find files shared earlier."

        results = []
        for file_info in files:
            file_name = file_info.get("name", "file")

            if file_service.is_image(file_info):
                # For images, describe them
                image_data = file_service.get_image_for_vision(file_info)
                if image_data:
                    results.append(f"[Image: {file_name}] - Image file attached, use vision to analyze")
                else:
                    results.append(f"[Image: {file_name}] - Could not process image")
            else:
                # Extract text from documents
                file_text = file_service.extract_text_from_file(file_info)
                if file_text:
                    # Truncate very long files
                    if len(file_text) > 30000:
                        file_text = file_text[:30000] + "\n[...truncated...]"
                    results.append(f"=== {file_name} ===\n{file_text}")
                else:
                    results.append(f"[{file_name}] - Could not extract text")

        return "\n\n".join(results)

    def execute_get_channel_history(tool_input: dict, context: dict) -> str:
        """Get recent channel message history."""
        channel_id = context.get("channel_id")
        hours = tool_input.get("hours", 24)
        hours = min(hours, 168)  # Cap at 1 week

        messages = slack_utils.get_channel_history(channel_id, hours=hours)

        if not messages:
            return "No messages found in the specified time period."

        # Format messages and track files
        formatted = []
        for msg in messages:
            line = f"[{msg['timestamp']}] {msg['user_name']}: {msg['text']}"

            # Track files for later retrieval
            if msg.get("files"):
                file_names = []
                for f in msg["files"]:
                    fname = f.get("name", "file")
                    file_names.append(fname)
                    # Cache file info for read_file_by_name
                    channel_files_cache[fname.lower()] = f
                    # Also cache without extension for fuzzy matching
                    base_name = fname.rsplit(".", 1)[0].lower()
                    channel_files_cache[base_name] = f

                line += f" [Files: {', '.join(file_names)}]"

            formatted.append(line)

        return "\n".join(formatted)

    def execute_read_file_by_name(tool_input: dict, context: dict) -> str:
        """Read a specific file from channel history by name."""
        file_name = tool_input.get("file_name", "")
        question = tool_input.get("question", "summarize")

        if not file_name:
            return "Please specify a file name."

        # Look for file in cache (populated by get_channel_history)
        file_name_lower = file_name.lower()
        file_info = None

        # Try exact match first
        if file_name_lower in channel_files_cache:
            file_info = channel_files_cache[file_name_lower]
        else:
            # Try partial match
            for cached_name, cached_file in channel_files_cache.items():
                if file_name_lower in cached_name or cached_name in file_name_lower:
                    file_info = cached_file
                    break

        if not file_info:
            # File not in cache - need to search channel history
            channel_id = context.get("channel_id")
            messages = slack_utils.get_channel_history(channel_id, hours=168)

            for msg in messages:
                for f in msg.get("files", []):
                    fname = f.get("name", "").lower()
                    if file_name_lower in fname or fname in file_name_lower:
                        file_info = f
                        break
                if file_info:
                    break

        if not file_info:
            return f"Could not find a file matching '{file_name}'. Try get_channel_history first to see available files."

        # Now read the file
        actual_name = file_info.get("name", "file")

        if file_service.is_image(file_info):
            # For images, we need to use vision - return a note
            return f"[{actual_name}] is an image. To analyze images, they need to be attached to the current message."

        file_text = file_service.extract_text_from_file(file_info)
        if file_text:
            if len(file_text) > 50000:
                file_text = file_text[:50000] + "\n[...truncated...]"
            return f"=== {actual_name} ===\n{file_text}"
        else:
            return f"Could not extract text from {actual_name}."

    def execute_fetch_url(tool_input: dict, context: dict) -> str:
        """Fetch content from a URL."""
        url = tool_input.get("url", "")

        if not url:
            return "Please provide a URL."

        content = web_service.fetch_url(url)
        if content:
            if len(content) > 50000:
                content = content[:50000] + "\n[...truncated...]"
            return content
        else:
            return f"Could not fetch content from {url}. The page may be blocked or unavailable."

    def execute_search_web(tool_input: dict, context: dict) -> str:
        """Search the web for information."""
        query = tool_input.get("query", "")

        if not query:
            return "Please provide a search query."

        if not research_service.is_available():
            return "Web search is not configured. TAVILY_API_KEY is required."

        return research_service.research(query)

    def execute_get_portfolio_channel(tool_input: dict, context: dict) -> str:
        """Get updates from a portfolio company's channel."""
        company_name = tool_input.get("company_name", "")

        if not company_name:
            return "Please specify a company name."

        channel_name = f"portfolio-{company_name.lower().replace(' ', '-')}"
        channel_id = slack_utils.get_channel_id_by_name(channel_name)

        if not channel_id:
            return f"Could not find a channel for '{company_name}'. Expected channel: #{channel_name}"

        messages = slack_utils.get_channel_history(channel_id, hours=168)

        if not messages:
            return f"No recent messages in #{channel_name}."

        # Format messages
        formatted = []
        for msg in messages:
            line = f"[{msg['timestamp']}] {msg['user_name']}: {msg['text']}"
            if msg.get("files"):
                file_names = [f.get("name", "file") for f in msg["files"]]
                line += f" [Files: {', '.join(file_names)}]"
            formatted.append(line)

        return f"Recent messages from #{channel_name}:\n" + "\n".join(formatted)

    return {
        "add_to_agenda": execute_add_to_agenda,
        "view_agenda": execute_view_agenda,
        "read_files": execute_read_files,
        "get_channel_history": execute_get_channel_history,
        "read_file_by_name": execute_read_file_by_name,
        "fetch_url": execute_fetch_url,
        "search_web": execute_search_web,
        "get_portfolio_company_channel": execute_get_portfolio_channel,
    }


def send_response(say, content: str, thread_ts: str):
    """Send a response, handling long content with blocks."""
    if len(content) <= 3000:
        say(text=content, thread_ts=thread_ts)
    else:
        # Use blocks for longer content
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": content[:3000]}}
        ]
        if len(content) > 3000:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": content[3000:6000]}})
        if len(content) > 6000:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": content[6000:9000]}})

        say(text=content[:200], blocks=blocks, thread_ts=thread_ts)
