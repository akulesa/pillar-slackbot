from datetime import datetime, timedelta
from slack_bolt import App

from services import ClaudeService, GoogleService, AirtableService
from utils import SlackUtils, MessageFormatter
from database import (
    add_agenda_item, get_pending_agenda_items, mark_agenda_items_included,
    save_user_last_active, get_user_last_active
)


def register_commands(app: App):
    """Register all slash command handlers."""

    claude = ClaudeService()
    google = GoogleService()
    airtable = AirtableService()

    @app.command("/pillar")
    def handle_pillar_command(ack, command, client, respond):
        """Main command handler for /pillar."""
        ack()

        user_id = command["user_id"]
        channel_id = command["channel_id"]
        text = command.get("text", "").strip()

        slack_utils = SlackUtils(client)

        # Parse the command
        parts = text.split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "help"
        args = parts[1] if len(parts) > 1 else ""

        # Route to appropriate handler
        if subcommand == "summarize":
            handle_summarize(respond, slack_utils, claude, channel_id, args, user_id)
        elif subcommand == "catchup":
            handle_catchup(respond, slack_utils, claude, channel_id, user_id)
        elif subcommand == "actions":
            handle_actions(respond, slack_utils, claude, channel_id, args)
        elif subcommand == "agenda":
            handle_agenda(respond, slack_utils, claude, google, channel_id, user_id, args)
        elif subcommand == "portfolio":
            handle_portfolio(respond, slack_utils, claude, airtable, args)
        elif subcommand == "lp-letter":
            handle_lp_letter(respond, slack_utils, claude, google, airtable, user_id, args)
        elif subcommand == "help":
            respond(**MessageFormatter.format_help())
        else:
            respond(**MessageFormatter.format_error(
                f"Unknown command: `{subcommand}`. Use `/pillar help` for available commands."
            ))


def handle_summarize(respond, slack_utils: SlackUtils, claude: ClaudeService,
                     channel_id: str, args: str, user_id: str):
    """Handle /pillar summarize command."""
    # Show loading message
    respond(**MessageFormatter.format_loading("Analyzing channel history"))

    # Parse time period
    hours = slack_utils.parse_time_period(args) if args else None
    if hours is None:
        hours = 24

    # Format period for display
    if hours <= 24:
        period = f"last {hours} hours"
    elif hours <= 168:
        period = f"last {hours // 24} days"
    else:
        period = f"last {hours // 168} weeks"

    # Fetch messages
    messages = slack_utils.get_channel_history(channel_id, hours=hours)

    if not messages:
        respond(**MessageFormatter.format_error("No messages found in the specified time period."))
        return

    # Get channel name
    channel_name = slack_utils.get_channel_name(channel_id)

    # Generate summary
    summary = claude.summarize_messages(messages)

    # Update user's last active time
    save_user_last_active(user_id)

    # Send response
    respond(**MessageFormatter.format_summary(summary, channel_name, period))


def handle_catchup(respond, slack_utils: SlackUtils, claude: ClaudeService,
                   channel_id: str, user_id: str):
    """Handle /pillar catchup command."""
    # Get user's last active time
    last_active = get_user_last_active(user_id)

    if last_active is None:
        # Default to 24 hours if no record
        hours = 24
        period = "last 24 hours (first time catch-up)"
    else:
        # Calculate hours since last active
        delta = datetime.now() - last_active
        hours = max(1, int(delta.total_seconds() / 3600))
        if hours > 168:  # Cap at 1 week
            hours = 168
        period = f"since {last_active.strftime('%Y-%m-%d %H:%M')}"

    respond(**MessageFormatter.format_loading("Preparing your catch-up"))

    # Fetch messages
    messages = slack_utils.get_channel_history(channel_id, hours=hours)

    if not messages:
        respond(text="You're all caught up! No new messages since your last visit.")
        return

    # Get channel name
    channel_name = slack_utils.get_channel_name(channel_id)

    # Generate summary with catch-up context
    summary = claude.summarize_messages(
        messages,
        context="This is a personal catch-up for a team member who has been away. "
                "Focus on decisions made, action items that might involve them, and important updates."
    )

    # Update last active
    save_user_last_active(user_id)

    respond(**MessageFormatter.format_summary(summary, channel_name, period))


def handle_actions(respond, slack_utils: SlackUtils, claude: ClaudeService,
                   channel_id: str, args: str):
    """Handle /pillar actions command."""
    respond(**MessageFormatter.format_loading("Extracting action items"))

    # Check for user filter
    user_filter = None
    if args:
        user_id = slack_utils.parse_user_mention(args)
        if user_id:
            user_filter = slack_utils._get_user_name(user_id)

    # Parse time period from args (if present after user mention)
    hours = slack_utils.parse_time_period(args) if args else 24

    # Fetch messages
    messages = slack_utils.get_channel_history(channel_id, hours=hours)

    if not messages:
        respond(**MessageFormatter.format_error("No messages found in the specified time period."))
        return

    # Extract action items
    action_items = claude.extract_action_items(messages, user_filter=user_filter)

    channel_name = slack_utils.get_channel_name(channel_id)
    respond(**MessageFormatter.format_action_items(action_items, channel_name))


def handle_agenda(respond, slack_utils: SlackUtils, claude: ClaudeService,
                  google: GoogleService, channel_id: str, user_id: str, args: str):
    """Handle /pillar agenda commands."""
    parts = args.split(maxsplit=1) if args else []
    subcommand = parts[0].lower() if parts else ""
    sub_args = parts[1] if len(parts) > 1 else ""

    if subcommand == "add":
        # Add item to agenda: /pillar agenda add [category] [content]
        add_parts = sub_args.split(maxsplit=1)
        if len(add_parts) < 2:
            respond(**MessageFormatter.format_error(
                "Usage: `/pillar agenda add [category] [item]`\n"
                "Categories: investment, pipeline, portfolio, other"
            ))
            return

        category_input = add_parts[0].lower()
        content = add_parts[1]

        # Map category aliases
        category_map = {
            "investment": "Investment Decisions",
            "decision": "Investment Decisions",
            "pipeline": "Pipeline Review",
            "deal": "Pipeline Review",
            "portfolio": "Portfolio Company Updates",
            "company": "Portfolio Company Updates",
            "other": "Other Business",
        }
        category = category_map.get(category_input, "Other Business")

        # Save to database
        add_agenda_item(user_id, channel_id, category, content)

        respond(**MessageFormatter.format_agenda_confirmation(category, content))

    elif subcommand == "finalize":
        # Generate the agenda document
        respond(**MessageFormatter.format_loading("Generating Monday meeting agenda"))

        # Check Google auth
        if not google.is_user_authenticated(user_id):
            auth_url = google.get_auth_url(user_id, "http://localhost:8080/oauth/callback")
            respond(**MessageFormatter.format_google_auth_prompt(auth_url))
            return

        # Get pending items
        items = get_pending_agenda_items()

        if not items:
            respond(**MessageFormatter.format_error("No agenda items to include. Add items with `/pillar agenda add`"))
            return

        # Generate formatted agenda
        agenda_content = claude.generate_meeting_agenda(items)

        # Create Google Doc
        doc = google.create_meeting_agenda_doc(user_id, agenda_content)

        if doc:
            # Mark items as included
            mark_agenda_items_included([item["id"] for item in items])
            respond(**MessageFormatter.format_google_doc_created(doc["title"], doc["url"]))
        else:
            respond(**MessageFormatter.format_error("Failed to create Google Doc. Please check your Google connection."))

    elif subcommand == "view":
        # View current pending items
        items = get_pending_agenda_items()
        if not items:
            respond(text="No pending agenda items. Add items with `/pillar agenda add`")
            return

        # Group by category
        by_category = {}
        for item in items:
            cat = item["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item["content"])

        text = "*Pending Agenda Items:*\n\n"
        for category, contents in by_category.items():
            text += f"*{category}*\n"
            for content in contents:
                text += f"  - {content}\n"
            text += "\n"

        respond(text=text)

    else:
        # Show the agenda builder prompt
        respond(**MessageFormatter.format_agenda_prompt())


def handle_portfolio(respond, slack_utils: SlackUtils, claude: ClaudeService,
                     airtable: AirtableService, args: str):
    """Handle /pillar portfolio command."""
    if not args:
        # List all portfolio companies
        if airtable.is_configured():
            companies = airtable.get_all_portfolio_companies()
            if companies:
                text = "*Portfolio Companies:*\n"
                for company in companies:
                    text += f"  - {company['name']}"
                    if company.get("sector"):
                        text += f" ({company['sector']})"
                    text += "\n"
                text += "\nUse `/pillar portfolio [company name]` for details."
                respond(text=text)
                return

        # Fall back to listing portfolio channels
        channels = slack_utils.get_portfolio_channels()
        if channels:
            text = "*Portfolio Channels:*\n"
            for ch in channels:
                text += f"  - #{ch['name']} ({ch['company_name']})\n"
            text += "\nUse `/pillar portfolio [company name]` for details."
            respond(text=text)
        else:
            respond(**MessageFormatter.format_error("No portfolio channels found."))
        return

    company_name = args.strip()
    respond(**MessageFormatter.format_loading(f"Gathering updates for {company_name}"))

    # Get Airtable data if available
    airtable_data = None
    if airtable.is_configured():
        airtable_data = airtable.get_portfolio_company(company_name)

    # Find the company's Slack channel
    channel_name = f"portfolio-{company_name.lower().replace(' ', '-')}"
    channel_id = slack_utils.get_channel_id_by_name(channel_name)

    if not channel_id and airtable_data:
        # Try to get channel from Airtable
        alt_channel = airtable.get_company_slack_channel(company_name)
        if alt_channel:
            channel_id = slack_utils.get_channel_id_by_name(alt_channel)

    messages = []
    if channel_id:
        messages = slack_utils.get_channel_history(channel_id, hours=168)  # Last week

    if not messages and not airtable_data:
        respond(**MessageFormatter.format_error(
            f"Could not find channel or data for '{company_name}'. "
            f"Check the company name or ensure channel #{channel_name} exists."
        ))
        return

    # Generate update
    update = claude.generate_portfolio_update(company_name, messages, airtable_data)

    respond(**MessageFormatter.format_portfolio_update(company_name, update, airtable_data))


def handle_lp_letter(respond, slack_utils: SlackUtils, claude: ClaudeService,
                     google: GoogleService, airtable: AirtableService,
                     user_id: str, args: str):
    """Handle /pillar lp-letter command."""
    # Parse quarter from args or default to current
    if args:
        quarter = args.strip()
    else:
        now = datetime.now()
        q = (now.month - 1) // 3 + 1
        quarter = f"Q{q} {now.year}"

    respond(**MessageFormatter.format_loading(f"Generating LP letter for {quarter}"))

    # Check Google auth
    if not google.is_user_authenticated(user_id):
        auth_url = google.get_auth_url(user_id, "http://localhost:8080/oauth/callback")
        respond(**MessageFormatter.format_google_auth_prompt(auth_url))
        return

    # Get all portfolio channels
    portfolio_channels = slack_utils.get_portfolio_channels()

    if not portfolio_channels:
        respond(**MessageFormatter.format_error("No portfolio channels found. Cannot generate LP letter."))
        return

    # Gather updates from each company
    portfolio_updates = {}

    for channel in portfolio_channels[:20]:  # Limit to 20 companies
        messages = slack_utils.get_channel_history(channel["id"], hours=24*90)  # Last ~quarter

        if messages:
            # Get Airtable data if available
            airtable_data = None
            if airtable.is_configured():
                airtable_data = airtable.get_portfolio_company(channel["company_name"])

            # Generate update for this company
            update = claude.generate_portfolio_update(
                channel["company_name"],
                messages,
                airtable_data
            )

            # Convert to LP letter style
            lp_section = claude.generate_lp_letter_section(channel["company_name"], update)
            portfolio_updates[channel["company_name"]] = lp_section

    if not portfolio_updates:
        respond(**MessageFormatter.format_error("No portfolio activity found for this quarter."))
        return

    # Generate full LP letter
    letter_content = claude.generate_full_lp_letter(portfolio_updates, quarter)

    # Create Google Doc
    doc = google.create_lp_letter_doc(user_id, letter_content, quarter)

    if doc:
        respond(**MessageFormatter.format_google_doc_created(doc["title"], doc["url"]))
    else:
        respond(**MessageFormatter.format_error("Failed to create Google Doc. Please check your Google connection."))
