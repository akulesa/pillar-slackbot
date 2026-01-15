from datetime import datetime, timedelta
from typing import Optional, List, Dict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import Config


class SlackUtils:
    """Utility functions for Slack operations."""

    def __init__(self, client: WebClient = None):
        self.client = client or WebClient(token=Config.SLACK_BOT_TOKEN)
        self._user_cache = {}

    def get_channel_history(
        self,
        channel_id: str,
        hours: int = None,
        since: datetime = None,
        limit: int = None
    ) -> List[Dict]:
        """Fetch channel message history."""
        if limit is None:
            limit = Config.MAX_MESSAGES_TO_FETCH

        # Calculate oldest timestamp
        if since:
            oldest = since.timestamp()
        elif hours:
            oldest = (datetime.now() - timedelta(hours=hours)).timestamp()
        else:
            oldest = (datetime.now() - timedelta(hours=Config.DEFAULT_SUMMARY_HOURS)).timestamp()

        messages = []
        cursor = None

        try:
            while len(messages) < limit:
                result = self.client.conversations_history(
                    channel=channel_id,
                    oldest=str(oldest),
                    limit=min(200, limit - len(messages)),
                    cursor=cursor
                )

                for msg in result["messages"]:
                    if msg.get("subtype") in ["channel_join", "channel_leave"]:
                        continue

                    user_name = self._get_user_name(msg.get("user", ""))
                    # Resolve @mentions in the message text to actual names
                    text = self.resolve_user_mentions(msg.get("text", ""))
                    messages.append({
                        "user": msg.get("user"),
                        "user_name": user_name,
                        "text": text,
                        "timestamp": datetime.fromtimestamp(float(msg["ts"])).strftime("%Y-%m-%d %H:%M"),
                        "ts": msg["ts"],
                        "files": msg.get("files", []),
                        "reactions": msg.get("reactions", []),
                    })

                if not result.get("has_more"):
                    break
                cursor = result.get("response_metadata", {}).get("next_cursor")

        except SlackApiError as e:
            print(f"Error fetching channel history: {e}")

        # Return in chronological order (oldest first)
        return list(reversed(messages))

    def get_thread_messages(self, channel_id: str, thread_ts: str) -> List[Dict]:
        """Fetch messages from a thread."""
        try:
            result = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=100
            )

            messages = []
            for msg in result["messages"]:
                user_name = self._get_user_name(msg.get("user", ""))
                text = self.resolve_user_mentions(msg.get("text", ""))
                messages.append({
                    "user": msg.get("user"),
                    "user_name": user_name,
                    "text": text,
                    "timestamp": datetime.fromtimestamp(float(msg["ts"])).strftime("%Y-%m-%d %H:%M"),
                    "ts": msg["ts"],
                    "files": msg.get("files", []),
                })
            return messages

        except SlackApiError as e:
            print(f"Error fetching thread: {e}")
            return []

    def _get_user_name(self, user_id: str) -> str:
        """Get user display name from user ID with caching."""
        if not user_id:
            return "Unknown"

        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            result = self.client.users_info(user=user_id)
            user = result["user"]
            name = user.get("real_name") or user.get("name") or user_id
            self._user_cache[user_id] = name
            return name
        except SlackApiError:
            return user_id

    def resolve_user_mentions(self, text: str) -> str:
        """Replace <@USER_ID> mentions with actual user names."""
        import re

        def replace_mention(match):
            user_id = match.group(1)
            user_name = self._get_user_name(user_id)
            return f"@{user_name}"

        # Replace <@U123ABC> patterns with @username
        return re.sub(r'<@([A-Z0-9]+)>', replace_mention, text)

    def get_channel_name(self, channel_id: str) -> str:
        """Get channel name from channel ID."""
        try:
            result = self.client.conversations_info(channel=channel_id)
            return result["channel"]["name"]
        except SlackApiError:
            return channel_id

    def get_channel_id_by_name(self, channel_name: str) -> Optional[str]:
        """Find channel ID by name."""
        # Remove # prefix if present
        channel_name = channel_name.lstrip("#")

        try:
            cursor = None
            while True:
                result = self.client.conversations_list(
                    types="public_channel,private_channel",
                    limit=200,
                    cursor=cursor
                )

                for channel in result["channels"]:
                    if channel["name"] == channel_name:
                        return channel["id"]

                if not result.get("has_more"):
                    break
                cursor = result.get("response_metadata", {}).get("next_cursor")

        except SlackApiError as e:
            print(f"Error finding channel: {e}")

        return None

    def get_portfolio_channels(self) -> List[Dict]:
        """Get all channels that match the portfolio channel prefix."""
        prefix = Config.PORTFOLIO_CHANNEL_PREFIX
        channels = []

        try:
            cursor = None
            while True:
                result = self.client.conversations_list(
                    types="public_channel,private_channel",
                    limit=200,
                    cursor=cursor
                )

                for channel in result["channels"]:
                    if channel["name"].startswith(prefix):
                        company_name = channel["name"][len(prefix):].replace("-", " ").title()
                        channels.append({
                            "id": channel["id"],
                            "name": channel["name"],
                            "company_name": company_name,
                        })

                if not result.get("has_more"):
                    break
                cursor = result.get("response_metadata", {}).get("next_cursor")

        except SlackApiError as e:
            print(f"Error listing channels: {e}")

        return channels

    def send_dm(self, user_id: str, text: str, blocks: list = None) -> bool:
        """Send a direct message to a user."""
        try:
            # Open DM channel
            result = self.client.conversations_open(users=[user_id])
            channel_id = result["channel"]["id"]

            # Send message
            self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks
            )
            return True
        except SlackApiError as e:
            print(f"Error sending DM: {e}")
            return False

    def post_message(
        self,
        channel_id: str,
        text: str,
        blocks: list = None,
        thread_ts: str = None
    ) -> Optional[str]:
        """Post a message to a channel, optionally in a thread."""
        try:
            result = self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                blocks=blocks,
                thread_ts=thread_ts
            )
            return result["ts"]
        except SlackApiError as e:
            print(f"Error posting message: {e}")
            return None

    def update_message(self, channel_id: str, ts: str, text: str, blocks: list = None) -> bool:
        """Update an existing message."""
        try:
            self.client.chat_update(
                channel=channel_id,
                ts=ts,
                text=text,
                blocks=blocks
            )
            return True
        except SlackApiError as e:
            print(f"Error updating message: {e}")
            return False

    def add_reaction(self, channel_id: str, ts: str, emoji: str) -> bool:
        """Add a reaction to a message."""
        try:
            self.client.reactions_add(
                channel=channel_id,
                timestamp=ts,
                name=emoji
            )
            return True
        except SlackApiError:
            return False

    def parse_user_mention(self, text: str) -> Optional[str]:
        """Extract user ID from a mention like <@U12345>."""
        import re
        match = re.search(r"<@(U[A-Z0-9]+)>", text)
        return match.group(1) if match else None

    def parse_channel_mention(self, text: str) -> Optional[str]:
        """Extract channel ID from a mention like <#C12345|channel-name>."""
        import re
        match = re.search(r"<#(C[A-Z0-9]+)(?:\|[^>]+)?>", text)
        return match.group(1) if match else None

    def parse_time_period(self, text: str) -> Optional[int]:
        """Parse time period from text like '7d', '24h', '1 week'."""
        import re

        # Match patterns like "7d", "24h", "1 week", "2 days"
        patterns = [
            (r"(\d+)\s*d(?:ays?)?", lambda m: int(m.group(1)) * 24),
            (r"(\d+)\s*h(?:ours?)?", lambda m: int(m.group(1))),
            (r"(\d+)\s*w(?:eeks?)?", lambda m: int(m.group(1)) * 24 * 7),
            (r"today", lambda m: 24),
            (r"this week", lambda m: 24 * 7),
            (r"yesterday", lambda m: 48),
        ]

        text_lower = text.lower()
        for pattern, converter in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return converter(match)

        return None
