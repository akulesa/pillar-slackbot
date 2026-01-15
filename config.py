import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Slack
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
    SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # Tavily (web search)
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # Google
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

    # Airtable
    AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
    AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

    # App settings
    PORTFOLIO_CHANNEL_PREFIX = os.getenv("PORTFOLIO_CHANNEL_PREFIX", "portfolio-")
    DEFAULT_SUMMARY_HOURS = 24
    MAX_MESSAGES_TO_FETCH = 500

    @classmethod
    def validate(cls):
        """Validate that required config values are set."""
        # Debug: print what we see
        print(f"DEBUG: SLACK_BOT_TOKEN set: {bool(cls.SLACK_BOT_TOKEN)}")
        print(f"DEBUG: SLACK_APP_TOKEN set: {bool(cls.SLACK_APP_TOKEN)}")
        print(f"DEBUG: ANTHROPIC_API_KEY set: {bool(cls.ANTHROPIC_API_KEY)}")
        print(f"DEBUG: All env vars: {[k for k in os.environ.keys() if 'SLACK' in k or 'ANTHROPIC' in k]}")

        required = [
            ("SLACK_BOT_TOKEN", cls.SLACK_BOT_TOKEN),
            ("SLACK_APP_TOKEN", cls.SLACK_APP_TOKEN),
            ("ANTHROPIC_API_KEY", cls.ANTHROPIC_API_KEY),
        ]
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
