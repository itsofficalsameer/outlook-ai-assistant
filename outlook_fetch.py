"""
Email fetching module for Microsoft Outlook using Microsoft Graph REST API.
Retrieves messages from the user's Inbox and parses basic email attributes.
"""

from typing import List, Dict, Any, Optional
import requests
import config


def fetch_inbox_emails(access_token: str, top: int = 10) -> List[Dict[str, Any]]:
    """
    Fetches the latest emails from the user's Outlook Inbox using Microsoft Graph API.

    Microsoft Graph Endpoint:
        GET https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages

    Pagination in Microsoft Graph:
        Microsoft Graph uses cursor-based pagination. If the number of matching items
        exceeds the requested '$top' limit (or default page size), the JSON response
        includes an '@odata.nextLink' property. That link is an opaque URL containing
        the skip token for fetching the next page.
        For this Part 1 initial test, we only retrieve the first page ($top=10).

    Args:
        access_token (str): Valid OAuth Bearer access token for Microsoft Graph.
        top (int): Number of emails to retrieve (default is 10).

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing:
            - id (str): Unique Outlook message ID
            - sender_email (str): Sender email address
            - subject (str): Subject line of the email
            - received_time (str): ISO 8601 received timestamp
            - body (str): Raw message body (HTML or plain text)
            - is_read (bool): Read status of the email

    Raises:
        requests.exceptions.HTTPError: On HTTP error responses (e.g. 401 Unauthorized, 403 Forbidden).
        requests.exceptions.RequestException: On general network failure.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    # Query parameters:
    # - $select: request only the specific fields needed
    # - $top: restrict page size to latest 10 messages
    # - $orderby: order by most recently received first
    params = {
        "$select": "id,subject,from,receivedDateTime,body,isRead",
        "$top": top,
        "$orderby": "receivedDateTime desc",
    }

    print(f"\n[FETCH] Connecting to Microsoft Graph API ({config.GRAPH_INBOX_MESSAGES_ENDPOINT})...")

    try:
        response = requests.get(
            config.GRAPH_INBOX_MESSAGES_ENDPOINT,
            headers=headers,
            params=params,
            timeout=20,
        )

        # Handle specific HTTP status codes with informative messages
        if response.status_code == 401:
            raise PermissionError(
                "401 Unauthorized: The access token is expired or invalid. Please re-authenticate."
            )
        elif response.status_code == 403:
            raise PermissionError(
                "403 Forbidden: Insufficient permissions. Ensure 'Mail.Read' delegated permission "
                "is added to the Azure App Registration and consented to by the user."
            )

        response.raise_for_status()

    except requests.exceptions.RequestException as err:
        print(f"[FETCH ERROR] Network or HTTP error occurred: {err}")
        raise

    data = response.json()
    raw_messages = data.get("value", [])

    # Check for pagination info
    next_link = data.get("@odata.nextLink")
    if next_link:
        print("[FETCH INFO] More emails exist in Inbox (@odata.nextLink available for subsequent pages).")

    parsed_emails: List[Dict[str, Any]] = []

    for msg in raw_messages:
        # Preserve original Outlook email ID
        email_id = msg.get("id", "")

        # Safely extract sender information
        from_field = msg.get("from") or {}
        email_address_field = from_field.get("emailAddress") or {}
        sender_email = email_address_field.get("address", "").strip()
        if not sender_email:
            sender_email = "Unknown Sender"

        # Safely extract subject (fallback for blank subjects)
        subject = msg.get("subject")
        if subject is None or subject.strip() == "":
            subject = "(No Subject)"

        # Received timestamp
        received_time = msg.get("receivedDateTime", "")

        # Raw body content (HTML or text) preserved as returned
        body_field = msg.get("body") or {}
        body = body_field.get("content", "")
        if body is None:
            body = ""

        # Read status
        is_read = bool(msg.get("isRead", False))

        parsed_email = {
            "id": email_id,
            "sender_email": sender_email,
            "subject": subject,
            "received_time": received_time,
            "body": body,
            "is_read": is_read,
        }
        parsed_emails.append(parsed_email)

    return parsed_emails

