from slack_bolt import App

from database import save_user_last_active


def register_events(app: App):
    """Register Slack event handlers."""

    @app.event("message")
    def handle_message(event, client):
        """Handle message events for tracking user activity."""
        # Skip bot messages and message changes
        if event.get("subtype") in ["bot_message", "message_changed", "message_deleted"]:
            return

        # Track user activity for catch-up feature
        user_id = event.get("user")
        if user_id:
            save_user_last_active(user_id)

    @app.event("member_joined_channel")
    def handle_member_joined(event, client, say):
        """Welcome new members to portfolio channels."""
        from config import Config

        channel_id = event.get("channel")
        user_id = event.get("user")

        # Get channel info
        try:
            result = client.conversations_info(channel=channel_id)
            channel_name = result["channel"]["name"]

            # Check if this is a portfolio channel
            if channel_name.startswith(Config.PORTFOLIO_CHANNEL_PREFIX):
                company_name = channel_name[len(Config.PORTFOLIO_CHANNEL_PREFIX):].replace("-", " ").title()

                say(
                    text=f"Welcome to the {company_name} portfolio channel! "
                         f"Use `/pillar summarize` to catch up on recent activity, "
                         f"or `/pillar portfolio {company_name}` for a comprehensive update.",
                    channel=channel_id
                )
        except Exception:
            pass  # Silently fail for non-accessible channels

    @app.action("agenda_investment")
    def handle_agenda_investment(ack, body, client):
        """Handle investment agenda button click."""
        ack()
        _prompt_for_agenda_item(body, client, "Investment Decisions")

    @app.action("agenda_pipeline")
    def handle_agenda_pipeline(ack, body, client):
        """Handle pipeline agenda button click."""
        ack()
        _prompt_for_agenda_item(body, client, "Pipeline Review")

    @app.action("agenda_portfolio")
    def handle_agenda_portfolio(ack, body, client):
        """Handle portfolio agenda button click."""
        ack()
        _prompt_for_agenda_item(body, client, "Portfolio Company Updates")

    @app.action("agenda_other")
    def handle_agenda_other(ack, body, client):
        """Handle other agenda button click."""
        ack()
        _prompt_for_agenda_item(body, client, "Other Business")

    @app.action("google_auth")
    def handle_google_auth(ack, body):
        """Handle Google auth button click."""
        ack()
        # The button opens the auth URL directly, no additional handling needed


def _prompt_for_agenda_item(body, client, category: str):
    """Open a modal to collect agenda item details."""
    trigger_id = body.get("trigger_id")

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "agenda_item_modal",
            "private_metadata": category,
            "title": {
                "type": "plain_text",
                "text": "Add Agenda Item"
            },
            "submit": {
                "type": "plain_text",
                "text": "Add"
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Category:* {category}"
                    }
                },
                {
                    "type": "input",
                    "block_id": "agenda_content",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "content",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Describe the agenda item..."
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Item Details"
                    }
                }
            ]
        }
    )


def register_view_handlers(app: App):
    """Register view submission handlers."""

    @app.view("agenda_item_modal")
    def handle_agenda_modal_submit(ack, body, client, view):
        """Handle agenda item modal submission."""
        from database import add_agenda_item
        from utils import MessageFormatter

        ack()

        user_id = body["user"]["id"]
        category = view["private_metadata"]
        content = view["state"]["values"]["agenda_content"]["content"]["value"]

        # Get the channel from the original message (stored in body)
        # For simplicity, we'll use a default or the user's DM
        channel_id = body.get("channel", {}).get("id", user_id)

        # Save the agenda item
        add_agenda_item(user_id, channel_id, category, content)

        # Send confirmation via DM
        try:
            result = client.conversations_open(users=[user_id])
            dm_channel = result["channel"]["id"]

            formatted = MessageFormatter.format_agenda_confirmation(category, content)
            client.chat_postMessage(
                channel=dm_channel,
                **formatted
            )
        except Exception as e:
            print(f"Error sending confirmation: {e}")
