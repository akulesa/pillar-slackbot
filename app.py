#!/usr/bin/env python3
"""
Pillar VC Slackbot - Main Application Entry Point

A Slack bot for Pillar VC that helps with:
- Channel summarization and catch-up
- Action item extraction
- Monday meeting agenda building
- Portfolio company updates
- LP letter generation
- Google Docs integration
- Airtable integration
"""

import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config import Config
from handlers import register_commands, register_mentions, register_events
from handlers.events import register_view_handlers
from database import init_db
from services import GoogleService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle Google OAuth callbacks."""

    def do_GET(self):
        """Handle GET requests for OAuth callback."""
        parsed = urlparse(self.path)

        if parsed.path == "/oauth/callback":
            query_params = parse_qs(parsed.query)
            code = query_params.get("code", [None])[0]
            state = query_params.get("state", [None])[0]  # user_id

            if code and state:
                google_service = GoogleService()
                success = google_service.handle_oauth_callback(
                    user_id=state,
                    code=code,
                    redirect_uri="http://localhost:8080/oauth/callback"
                )

                if success:
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html>
                        <head><title>Success</title></head>
                        <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                            <h1>Google Account Connected!</h1>
                            <p>You can close this window and return to Slack.</p>
                            <p>Try running <code>/pillar agenda finalize</code> again.</p>
                        </body>
                        </html>
                    """)
                else:
                    self.send_response(500)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html>
                        <head><title>Error</title></head>
                        <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                            <h1>Connection Failed</h1>
                            <p>There was an error connecting your Google account.</p>
                            <p>Please try again from Slack.</p>
                        </body>
                        </html>
                    """)
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Missing code or state parameter")
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not found")

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        logger.debug(f"OAuth server: {args[0]}")


def start_oauth_server():
    """Start the OAuth callback HTTP server."""
    server = HTTPServer(("localhost", 8080), OAuthCallbackHandler)
    logger.info("OAuth callback server running on http://localhost:8080")
    server.serve_forever()


def create_app() -> App:
    """Create and configure the Slack Bolt app."""
    # Validate configuration
    Config.validate()

    # Initialize the app
    app = App(
        token=Config.SLACK_BOT_TOKEN,
        signing_secret=Config.SLACK_SIGNING_SECRET,
    )

    # Initialize database
    init_db()

    # Register all handlers
    register_commands(app)
    register_mentions(app)
    register_events(app)
    register_view_handlers(app)

    logger.info("Pillar VC Bot initialized successfully")

    return app


def main():
    """Run the bot using Socket Mode."""
    app = create_app()

    # Start OAuth callback server in background thread
    if Config.GOOGLE_CLIENT_ID and Config.GOOGLE_CLIENT_SECRET:
        oauth_thread = threading.Thread(target=start_oauth_server, daemon=True)
        oauth_thread.start()
    else:
        logger.info("Google OAuth not configured - skipping OAuth server")

    # Use Socket Mode for easier development and deployment
    # No need to expose a public URL
    handler = SocketModeHandler(app, Config.SLACK_APP_TOKEN)

    logger.info("Starting Pillar VC Bot in Socket Mode...")
    logger.info("Bot is ready! Use /pillar help in Slack to get started.")

    handler.start()


if __name__ == "__main__":
    main()
