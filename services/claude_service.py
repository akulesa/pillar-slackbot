from typing import List, Dict
from anthropic import Anthropic
from config import Config

# Personality for Slack responses - casual, concise, fun
SLACK_TONE = """IMPORTANT TONE GUIDELINES:
- Be VERY concise - this is Slack, not a memo
- Use casual, friendly language (think smart millennial colleague)
- Add occasional wit or humor when appropriate
- Use bullet points, not paragraphs
- Skip the corporate speak
- Emoji sparingly is ok
- Get to the point fast"""


class ClaudeService:
    """Service for interacting with Claude API for summarization and content generation."""

    def __init__(self):
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"

    def summarize_messages(self, messages: List[Dict], context: str = "") -> str:
        """Summarize a list of Slack messages."""
        formatted_messages = self._format_messages_for_prompt(messages)

        prompt = f"""You're the Pillar VC bot helping the team catch up on Slack convos.

{SLACK_TONE}

{f"Context: {context}" if context else ""}

Slack messages to summarize:
{formatted_messages}

Give a quick, scannable summary:
- What was discussed (key topics only)
- Any decisions made
- Action items (who owes what)
- Important links/files shared

Keep it tight - nobody wants to read a wall of text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def extract_action_items(self, messages: List[Dict], user_filter: str = None) -> str:
        """Extract action items from messages."""
        formatted_messages = self._format_messages_for_prompt(messages)

        filter_instruction = ""
        if user_filter:
            filter_instruction = f"\nOnly show items for: {user_filter}"

        prompt = f"""You're the Pillar VC bot. Extract action items from this Slack convo.{filter_instruction}

{SLACK_TONE}

Slack messages:
{formatted_messages}

List action items as:
- What needs doing + who owns it (if mentioned)

Keep it short. If nothing actionable, just say "No action items - you're all clear!" """

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def generate_meeting_agenda(self, items: List[Dict], meeting_type: str = "Monday Investment Review") -> str:
        """Generate a formatted meeting agenda from collected items."""
        items_text = "\n".join([
            f"- [{item['category']}] {item['content']}"
            for item in items
        ])

        prompt = f"""You are a helpful assistant for Pillar VC, a venture capital firm.
Create a simple meeting agenda for the {meeting_type}.

Collected agenda items:
{items_text}

IMPORTANT FORMATTING RULES:
- Use PLAIN TEXT only, no markdown (no #, **, -, etc.)
- Keep it simple and minimal - just list the items
- Do NOT add placeholder text like [Meeting Date] or [Presenter]
- Do NOT add estimated times or durations
- Do NOT add extra sections beyond what's submitted
- Do NOT add Next Steps, Action Items, or administrative boilerplate

Format like this simple example:

Monday Investment Review

Investment Decisions
  • Company A - Series A discussion
  • Company B - Follow-on decision

Pipeline
  • New intro from Partner X

Portfolio Updates
  • Company C board deck review

Other
  • Team offsite planning

Just organize the submitted items into the right sections. If a section has no items, omit it entirely. Keep it brief."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def generate_portfolio_update(self, company_name: str, messages: List[Dict], airtable_data: dict = None) -> str:
        """Generate a portfolio company update summary."""
        formatted_messages = self._format_messages_for_prompt(messages)

        airtable_context = ""
        if airtable_data:
            airtable_context = f"(Stage: {airtable_data.get('stage', '?')}, Last board: {airtable_data.get('last_board', '?')})"

        prompt = f"""Quick update on {company_name} for the Pillar team. {airtable_context}

{SLACK_TONE}

Recent Slack activity:
{formatted_messages}

Hit the highlights:
- What's new / any news
- Metrics or milestones
- Red flags or concerns (if any)
- Files shared worth looking at
- Follow-ups needed

Keep it snappy - just the stuff that matters."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def generate_lp_letter_section(self, company_name: str, updates: str) -> str:
        """Generate an LP letter section for a portfolio company."""
        prompt = f"""You are a helpful assistant for Pillar VC, a venture capital firm.
Write a brief LP letter section for {company_name} based on these updates:

{updates}

IMPORTANT: Use PLAIN TEXT only, no markdown formatting (no #, **, -, etc.)

Write in a professional but engaging tone suitable for Limited Partners.
Focus on key achievements, growth metrics, and outlook.
Keep it to 2-3 paragraphs. Be optimistic but honest."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def generate_full_lp_letter(self, portfolio_updates: Dict[str, str], quarter: str) -> str:
        """Generate a full LP letter from portfolio updates."""
        updates_text = "\n\n".join([
            f"{company}:\n{update}"
            for company, update in portfolio_updates.items()
        ])

        prompt = f"""You are a helpful assistant for Pillar VC, a venture capital firm.
Create a quarterly LP letter for {quarter}.

Portfolio company updates:
{updates_text}

IMPORTANT FORMATTING RULES:
- Use PLAIN TEXT only, no markdown (no #, **, -, bullet points, etc.)
- Use blank lines to separate sections
- Use simple section headers like "Executive Summary" on their own line
- Write in flowing paragraphs, not bullet points

Structure:
1. Executive Summary - overall fund performance and highlights
2. Market Commentary - brief observations
3. Portfolio Highlights - top performing companies
4. Portfolio Updates - section for each company
5. Looking Ahead - outlook

Write in a professional, confident tone suitable for Limited Partners."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def parse_command(self, text: str) -> dict:
        """Parse natural language commands from mentions."""
        prompt = f"""Parse this Slack message into a command for the Pillar VC bot.

Message: {text}

Identify:
1. intent: One of [summarize, actions, agenda, portfolio, lp_letter, research, help, unknown]
   - Use "research" for questions that need current/real-time information like stock prices, recent news, market data, or anything requiring web search
2. target: channel name, company name, or user mentioned (if any)
3. time_period: time range mentioned (e.g., "7 days", "this week", "since Monday")
4. additional_context: any other relevant details

Respond in this exact format:
intent: <intent>
target: <target or "none">
time_period: <period or "none">
additional_context: <context or "none">"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse the response
        result = {"intent": "unknown", "target": None, "time_period": None, "additional_context": None}
        for line in response.content[0].text.strip().split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if value.lower() == "none":
                    value = None
                if key in result:
                    result[key] = value
        return result

    def _format_messages_for_prompt(self, messages: List[Dict]) -> str:
        """Format Slack messages for inclusion in a prompt."""
        formatted = []
        for msg in messages:
            user = msg.get("user_name", msg.get("user", "Unknown"))
            text = msg.get("text", "")
            timestamp = msg.get("timestamp", "")
            files = msg.get("files", [])

            line = f"[{timestamp}] {user}: {text}"
            if files:
                file_names = [f.get("name", "file") for f in files]
                line += f" [Attached: {', '.join(file_names)}]"
            formatted.append(line)

        return "\n".join(formatted)
