import re
from datetime import datetime


def markdown_to_slack(text: str) -> str:
    """Convert standard Markdown to Slack's mrkdwn format.

    Slack mrkdwn differences:
    - Bold: *text* (not **text**)
    - Italic: _text_ (not *text*)
    - No headers - use bold instead
    - Links: <url|text> (not [text](url))
    """
    # Convert headers to bold (must do before other conversions)
    # Handle ###, ##, # in that order
    text = re.sub(r'^###\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)

    # Convert **bold** to *bold* (Slack style)
    # Be careful not to affect already-correct *single asterisk* bold
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)

    # Convert markdown links [text](url) to Slack format <url|text>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)

    # Convert `code` - Slack uses the same format, so this is fine

    # Clean up any double bold markers that might have been created
    text = re.sub(r'\*\*+', '*', text)

    return text


class MessageFormatter:
    """Format messages for Slack output."""

    @staticmethod
    def format_summary(summary: str, channel_name: str, period: str) -> dict:
        """Format a channel summary for Slack display."""
        # Convert markdown to Slack format
        summary = markdown_to_slack(summary)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Summary: #{channel_name}",
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Period: {period}"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary[:3000]  # Slack block text limit
                }
            }
        ]

        # Add continuation if summary is long
        if len(summary) > 3000:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary[3000:6000]
                }
            })

        return {
            "text": f"Summary of #{channel_name} ({period})",
            "blocks": blocks
        }

    @staticmethod
    def format_action_items(action_items: str, channel_name: str = None) -> dict:
        """Format action items for Slack display."""
        # Convert markdown to Slack format
        action_items = markdown_to_slack(action_items)

        header = "Action Items"
        if channel_name:
            header += f": #{channel_name}"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header,
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": action_items[:3000]
                }
            }
        ]

        return {
            "text": header,
            "blocks": blocks
        }

    @staticmethod
    def format_agenda_confirmation(category: str, content: str) -> dict:
        """Format agenda item confirmation."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Added to Monday agenda under *{category}*:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f">{content}"
                }
            }
        ]

        return {
            "text": f"Added to agenda: {content[:50]}...",
            "blocks": blocks
        }

    @staticmethod
    def format_agenda_prompt() -> dict:
        """Format the agenda collection prompt."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Monday Meeting Agenda Builder",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Add items to this week's agenda by selecting a category:"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Investment Decision"},
                        "value": "investment_decision",
                        "action_id": "agenda_investment"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Pipeline Update"},
                        "value": "pipeline_update",
                        "action_id": "agenda_pipeline"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Portfolio Update"},
                        "value": "portfolio_update",
                        "action_id": "agenda_portfolio"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Other"},
                        "value": "other",
                        "action_id": "agenda_other"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Or use `/pillar agenda add [category] [item]` to add directly"
                    }
                ]
            }
        ]

        return {
            "text": "Monday Meeting Agenda Builder",
            "blocks": blocks
        }

    @staticmethod
    def format_google_doc_created(title: str, url: str) -> dict:
        """Format Google Doc creation confirmation."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Created Google Doc: *<{url}|{title}>*"
                }
            }
        ]

        return {
            "text": f"Created: {title}",
            "blocks": blocks
        }

    @staticmethod
    def format_google_auth_prompt(auth_url: str) -> dict:
        """Format Google OAuth prompt."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "To create Google Docs, I need access to your Google account."
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Connect Google Account"},
                        "url": auth_url,
                        "action_id": "google_auth"
                    }
                ]
            }
        ]

        return {
            "text": "Please connect your Google account",
            "blocks": blocks
        }

    @staticmethod
    def format_portfolio_update(company_name: str, update: str, airtable_data: dict = None) -> dict:
        """Format portfolio company update."""
        # Convert markdown to Slack format
        update = markdown_to_slack(update)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Portfolio Update: {company_name}",
                }
            }
        ]

        # Add Airtable data if available
        if airtable_data:
            fields_text = []
            if airtable_data.get("stage"):
                fields_text.append(f"*Stage:* {airtable_data['stage']}")
            if airtable_data.get("sector"):
                fields_text.append(f"*Sector:* {airtable_data['sector']}")
            if airtable_data.get("lead_partner"):
                fields_text.append(f"*Lead:* {airtable_data['lead_partner']}")

            if fields_text:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": " | ".join(fields_text)}]
                })

        blocks.extend([
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": update[:3000]
                }
            }
        ])

        return {
            "text": f"Portfolio Update: {company_name}",
            "blocks": blocks
        }

    @staticmethod
    def format_help() -> dict:
        """Format help message."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Pillar VC Bot - Help",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Available Commands:*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "`/pillar summarize [time]` - Summarize this channel (default: 24h)\n"
                        "`/pillar catchup` - Personal catch-up since your last visit\n"
                        "`/pillar actions [@user]` - Extract action items\n"
                        "`/pillar agenda` - Start building Monday meeting agenda\n"
                        "`/pillar agenda add [category] [item]` - Add item to agenda\n"
                        "`/pillar agenda finalize` - Generate agenda Google Doc\n"
                        "`/pillar portfolio [company]` - Get portfolio company update\n"
                        "`/pillar lp-letter [quarter]` - Generate LP letter draft\n"
                        "`/pillar help` - Show this help message"
                    )
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Mention Commands:*\nYou can also @mention me with natural language:\n"
                           "- \"@PillarBot summarize the last week\"\n"
                           "- \"@PillarBot what action items are there?\"\n"
                           "- \"@PillarBot catch me up\""
                }
            }
        ]

        return {
            "text": "Pillar VC Bot Help",
            "blocks": blocks
        }

    @staticmethod
    def format_error(message: str) -> dict:
        """Format error message."""
        return {
            "text": f"Error: {message}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:* {message}"
                    }
                }
            ]
        }

    @staticmethod
    def format_loading(action: str) -> dict:
        """Format loading message."""
        return {
            "text": f"{action}...",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"_{action}..._"
                    }
                }
            ]
        }
