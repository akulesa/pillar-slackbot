import os
from datetime import datetime
from typing import Optional, Dict
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from config import Config
from database import save_google_token, get_google_token

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleService:
    """Service for interacting with Google Docs and Drive."""

    def __init__(self):
        self.client_config = {
            "web": {
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080/oauth/callback"],
            }
        }

    def get_auth_url(self, user_id: str, redirect_uri: str) -> str:
        """Generate OAuth URL for user authorization."""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=user_id,
            prompt="consent"
        )
        return auth_url

    def handle_oauth_callback(self, user_id: str, code: str, redirect_uri: str) -> bool:
        """Handle OAuth callback and store tokens."""
        try:
            flow = Flow.from_client_config(
                self.client_config,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            flow.fetch_token(code=code)
            credentials = flow.credentials

            save_google_token(
                user_id=user_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expiry=credentials.expiry
            )
            return True
        except Exception as e:
            print(f"OAuth callback error: {e}")
            return False

    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """Get valid credentials for a user, refreshing if needed."""
        token_data = get_google_token(user_id)
        if not token_data:
            return None

        credentials = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=Config.GOOGLE_CLIENT_ID,
            client_secret=Config.GOOGLE_CLIENT_SECRET,
        )

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            save_google_token(
                user_id=user_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expiry=credentials.expiry
            )

        return credentials

    def create_document(self, user_id: str, title: str, content: str) -> Optional[Dict]:
        """Create a new Google Doc with the given content."""
        credentials = self.get_credentials(user_id)
        if not credentials:
            return None

        try:
            docs_service = build("docs", "v1", credentials=credentials)
            drive_service = build("drive", "v3", credentials=credentials)

            # Create empty document
            doc = docs_service.documents().create(body={"title": title}).execute()
            doc_id = doc["documentId"]

            # Insert content
            requests = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": content
                    }
                }
            ]
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()

            # Get the document URL
            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

            return {
                "document_id": doc_id,
                "title": title,
                "url": doc_url
            }
        except Exception as e:
            print(f"Error creating document: {e}")
            return None

    def create_meeting_agenda_doc(self, user_id: str, agenda_content: str, meeting_date: str = None) -> Optional[Dict]:
        """Create a meeting agenda document."""
        if meeting_date is None:
            meeting_date = datetime.now().strftime("%Y-%m-%d")

        title = f"Pillar VC - Monday Meeting Agenda - {meeting_date}"
        return self.create_document(user_id, title, agenda_content)

    def create_lp_letter_doc(self, user_id: str, letter_content: str, quarter: str) -> Optional[Dict]:
        """Create an LP letter document."""
        title = f"Pillar VC - LP Letter - {quarter}"
        return self.create_document(user_id, title, letter_content)

    def create_portfolio_update_doc(self, user_id: str, company_name: str, update_content: str) -> Optional[Dict]:
        """Create a portfolio company update document."""
        date = datetime.now().strftime("%Y-%m-%d")
        title = f"{company_name} - Portfolio Update - {date}"
        return self.create_document(user_id, title, update_content)

    def append_to_document(self, user_id: str, document_id: str, content: str) -> bool:
        """Append content to an existing document."""
        credentials = self.get_credentials(user_id)
        if not credentials:
            return False

        try:
            docs_service = build("docs", "v1", credentials=credentials)

            # Get current document length
            doc = docs_service.documents().get(documentId=document_id).execute()
            end_index = doc["body"]["content"][-1]["endIndex"] - 1

            # Append content
            requests = [
                {
                    "insertText": {
                        "location": {"index": end_index},
                        "text": f"\n\n{content}"
                    }
                }
            ]
            docs_service.documents().batchUpdate(
                documentId=document_id,
                body={"requests": requests}
            ).execute()

            return True
        except Exception as e:
            print(f"Error appending to document: {e}")
            return False

    def is_user_authenticated(self, user_id: str) -> bool:
        """Check if a user has valid Google credentials."""
        credentials = self.get_credentials(user_id)
        return credentials is not None and credentials.valid
