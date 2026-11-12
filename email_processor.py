"""
Email Processor & Data Preparation Module (Part 2)
Outlook Email Bridge

Provides functions to:
1. Clean and convert HTML email bodies into human-readable plain text using Python's standard library.
2. Normalize and validate email metadata (handling missing sender, subject, body, or read status).
3. Prepare standardized email records tagged with 'pending_analysis' status.
"""

import html
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional


class _HTMLToTextParser(HTMLParser):
    """
    Internal HTML parser using Python's standard library html.parser.
    Strips tags, removes scripts and styles, converts block elements and breaks
    to readable newlines, and preserves link destinations and text.
    """

    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self.fed: List[str] = []
        # Elements whose inner text should be completely discarded
        self.ignore_tags = {"script", "style", "noscript", "head"}
        self._ignore_depth = 0
        self._current_href: Optional[str] = None
        self._link_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        tag = tag.lower()
        if tag in self.ignore_tags:
            self._ignore_depth += 1
        elif tag in ("p", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.fed.append("\n")
        elif tag in ("br", "hr"):
            self.fed.append("\n")
        elif tag == "li":
            self.fed.append("\n- ")
        elif tag == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href")
            self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.ignore_tags:
            self._ignore_depth = max(0, self._ignore_depth - 1)
        elif tag in ("p", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.fed.append("\n")
        elif tag == "a":
            if self._current_href:
                link_text_str = "".join(self._link_text).strip()
                href_clean = self._current_href.strip()
                # If the anchor text differs from the URL, include the URL in parentheses
                if link_text_str and href_clean and link_text_str != href_clean:
                    self.fed.append(f" ({href_clean})")
                elif not link_text_str and href_clean:
                    self.fed.append(href_clean)
                self._current_href = None
                self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0:
            self.fed.append(data)
            if self._current_href is not None:
                self._link_text.append(data)

    def get_text(self) -> str:
        return "".join(self.fed)


def clean_email_body(body: Optional[str]) -> str:
    """
    Cleans raw email body content:
    - Handles None and empty strings gracefully.
    - If content contains HTML markup, strips tags, removes script/style blocks,
      converts <br>/<p> tags to newlines, decodes HTML entities, and retains links.
    - Preserves critical text content such as dates, assignment deadlines, and submission instructions.
    - Normalizes excessive whitespace and blank lines.

    Args:
        body (Optional[str]): Raw body string (HTML or plain text), or None.

    Returns:
        str: Cleaned, human-readable plain text.
    """
    if body is None:
        return ""

    if not isinstance(body, str):
        body = str(body)

    if not body.strip():
        return ""

    # Parse HTML using standard library parser
    parser = _HTMLToTextParser()
    try:
        parser.feed(body)
        parser.close()
        text = parser.get_text()
    except Exception:
        # Fallback in case of severely malformed HTML: strip tags via regex
        text = re.sub(r"<[^>]+>", " ", body)

    # Decode HTML entities (e.g. &amp;, &lt;, &gt;, &quot;, &#39;, &nbsp;)
    text = html.unescape(text)

    # Normalize whitespace: replace non-breaking spaces with standard space
    text = text.replace("\u00a0", " ")

    # Normalize line breaks and spaces while preserving paragraph structure
    lines = [line.strip() for line in text.splitlines()]

    # Collapse multiple consecutive empty lines to a clean double newline
    cleaned_lines: List[str] = []
    consecutive_empty = 0
    for line in lines:
        if line == "":
            consecutive_empty += 1
            if consecutive_empty <= 1 and cleaned_lines:
                cleaned_lines.append("")
        else:
            consecutive_empty = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def process_email(raw_email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates, normalizes, and cleans a single email dictionary.

    Args:
        raw_email (Dict[str, Any]): Dictionary containing raw email data.
            Must contain either 'id' or 'email_id'.

    Returns:
        Dict[str, Any]: Processed email with fields:
            - email_id (str): Original email ID preserved.
            - sender_email (str): Sender address or 'Unknown sender'.
            - subject (str): Subject line or 'No subject'.
            - received_time (str): Timestamp or empty string.
            - body (str): Cleaned, human-readable plain text body.
            - is_read (bool): Boolean read status (defaults to False if missing).
            - status (str): Set to 'pending_analysis'.

    Raises:
        ValueError: If neither 'id' nor 'email_id' is present or if the ID is blank.
    """
    if not isinstance(raw_email, dict):
        raise ValueError("raw_email must be a dictionary.")

    # 1. Accept email ID from "id" or "email_id"
    raw_id = raw_email.get("id")
    if raw_id is None:
        raw_id = raw_email.get("email_id")

    if raw_id is None or str(raw_id).strip() == "":
        raise ValueError("Email ID is missing or empty.")

    email_id = str(raw_id).strip()

    # 2. Sender email with fallback
    sender_raw = raw_email.get("sender_email")
    if sender_raw is None:
        sender_raw = raw_email.get("sender")

    if sender_raw is None or not str(sender_raw).strip():
        sender_email = "Unknown sender"
    else:
        sender_email = str(sender_raw).strip()

    # 3. Subject with fallback
    subject_raw = raw_email.get("subject")
    if subject_raw is None or not str(subject_raw).strip():
        subject = "No subject"
    else:
        subject = str(subject_raw).strip()

    # 4. Received time (empty string if missing)
    received_time_raw = raw_email.get("received_time")
    if received_time_raw is None:
        received_time = ""
    else:
        received_time = str(received_time_raw).strip()

    # 5. Clean email body
    cleaned_body = clean_email_body(raw_email.get("body"))

    # 6. Read status (False if missing)
    is_read_raw = raw_email.get("is_read")
    if is_read_raw is None:
        is_read = False
    else:
        is_read = bool(is_read_raw)

    # 7. Standardized return structure with status='pending_analysis'
    return {
        "email_id": email_id,
        "sender_email": sender_email,
        "subject": subject,
        "received_time": received_time,
        "body": cleaned_body,
        "is_read": is_read,
        "status": "pending_analysis",
    }


def process_emails(raw_emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Processes a list of raw email dictionaries.

    Args:
        raw_emails (List[Dict[str, Any]]): List of raw email dictionaries.

    Returns:
        List[Dict[str, Any]]: List of processed and standardized email dictionaries.
    """
    if not isinstance(raw_emails, list):
        raise ValueError("raw_emails must be a list.")

    return [process_email(email) for email in raw_emails]

