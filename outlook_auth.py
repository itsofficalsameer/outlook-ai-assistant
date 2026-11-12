"""
Authentication module for Microsoft Outlook using MSAL Device Code Flow.
Handles user authentication and acquires an OAuth access token for Microsoft Graph API.
"""

from typing import Optional
import msal
import config


def get_access_token() -> Optional[str]:
    """
    Authenticates the user using MSAL's Device Code Flow and returns an access token.

    Device Code Flow is ideal for CLI and desktop development tools:
    1. The script requests a temporary code and verification URL from Microsoft.
    2. The user visits the URL in any web browser and inputs the code.
    3. The user logs in and consents with their Microsoft credentials.
    4. The script polls Microsoft in the background until authentication completes.

    Returns:
        str: A valid Microsoft Graph access token.
    Raises:
        RuntimeError: If authentication fails or is cancelled.
    """
    # Ensure CLIENT_ID is configured before attempting auth
    config.validate_config()

    # Create MSAL PublicClientApplication
    app = msal.PublicClientApplication(
        client_id=config.CLIENT_ID,
        authority=config.AUTHORITY,
    )

    # Check for existing cached accounts (silent token acquisition)
    accounts = app.get_accounts()
    if accounts:
        # Attempt to acquire token silently from cache if available
        silent_result = app.acquire_token_silent(scopes=config.SCOPES, account=accounts[0])
        if silent_result and "access_token" in silent_result:
            print(f"[AUTH] Found cached session for account: {accounts[0].get('username', 'Unknown')}")
            return silent_result["access_token"]

    # Initiate Device Code Flow
    print("\n" + "=" * 60)
    print("       MICROSOFT OUTLOOK AUTHENTICATION (DEVICE CODE FLOW)")
    print("=" * 60)

    flow = app.initiate_device_flow(scopes=config.SCOPES)
    if "user_code" not in flow:
        error_msg = flow.get("error_description", "Failed to initiate device code flow.")
        raise RuntimeError(f"Device code flow initiation failed: {error_msg}")

    # Display clear instructions to the user
    user_code = flow.get("user_code")
    verification_uri = flow.get("verification_uri", "https://microsoft.com/devicelogin")

    print("\nFollow these steps to authenticate your Outlook account:")
    print(f"  1. Open your web browser and go to: {verification_uri}")
    print(f"  2. Enter the device code:          {user_code}")
    print("  3. Sign in with your Microsoft/Outlook account and grant permissions.\n")
    print("Waiting for authentication to complete in your browser...")

    # Wait for the user to complete the login in their browser
    result = app.acquire_token_by_device_flow(flow)

    # Inspect the result
    if "access_token" in result:
        print("[AUTH] Successfully authenticated! Access token acquired.")
        # Notice: The token is returned to the caller, never printed to console
        return result["access_token"]
    else:
        error = result.get("error", "Unknown error")
        error_description = result.get("error_description", "No detailed description provided.")
        raise RuntimeError(f"Authentication failed: [{error}] {error_description}")

