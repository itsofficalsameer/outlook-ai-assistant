"""
Configuration module for Microsoft Graph API & MSAL Authentication.
Loads environment variables and defines API endpoints, scopes, and mock mode.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Mode configuration:
# When MOCK_MODE is True, the application uses realistic sample emails without needing Microsoft OAuth.
# When MOCK_MODE is False, the application connects to real Microsoft Graph API via OAuth.
MOCK_MODE = os.getenv("MOCK_MODE", "True").strip().lower() in ("true", "1", "yes")

# Microsoft Application (Client) ID
CLIENT_ID = os.getenv("CLIENT_ID", "").strip()

# Authority URL:
# - 'common': Allows both personal accounts (Outlook.com, Hotmail) and Work/School accounts.
# - 'consumers': Personal accounts only.
# - 'organizations': Work or school accounts only.
AUTHORITY = os.getenv("AUTHORITY", "https://login.microsoftonline.com/common").strip()

# Delegated permissions required to read emails from the user's Inbox
SCOPES = ["Mail.Read"]

# Microsoft Graph REST API endpoints
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_INBOX_MESSAGES_ENDPOINT = f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messages"


def validate_config() -> bool:
    """
    Validates that necessary configuration values are set.
    When MOCK_MODE is active, Microsoft credentials are not required.
    Returns True if configuration is valid; otherwise raises ValueError.
    """
    if MOCK_MODE:
        return True

    if not CLIENT_ID or CLIENT_ID == "YOUR_MICROSOFT_CLIENT_ID":
        raise ValueError(
            "CLIENT_ID is not configured. Please add your registered Application (Client) ID "
            "to the .env file.\nOr set MOCK_MODE=True in .env to test with mock emails without credentials."
        )
    return True
