
"""
MindWise - Groq AI Email Analyzer
Handles Groq API initialization and configuration.
"""
import time
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from groq import Groq
from zoneinfo import ZoneInfo

# Load project environment variables
load_dotenv(override=True)

# Configuration
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
TIMEZONE = ZoneInfo("Asia/Kolkata")


def initialize_groq():
    """Initialize and return the Groq client."""

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from .env")

    client = Groq(api_key=api_key)

    return client

def analyze_email(email, client=None):
    """
    Analyze one processed email using Groq AI.
    Returns structured email analysis as a Python dictionary.
    """

    if client is None:
        client = initialize_groq()

    email_id = email.get("email_id") or email.get("id")
    subject = email.get("subject", "")
    sender = email.get("sender_email", "")
    received_time = email.get("received_time", "")
    body = email.get("body", "")

    prompt = f"""
You are MindWise, an intelligent Outlook email assistant.

Analyze the following email and return ONLY valid JSON.

EMAIL DETAILS:
Email ID: {email_id}
Sender: {sender}
Subject: {subject}
Received Time: {received_time}
Body:
{body}

IMPORTANT RULES:

1. Categorize the email as one of:
   Academic, Personal, Professional, Promotional,
   Social, Technical, Security, Other.

2. Priority must be:
   High, Medium, or Low.

3. Extract assignment deadlines separately from meetings.
   An assignment deadline must NEVER be treated as a meeting alarm.

3A. OVERDUE DEADLINES:
   - Extract deadlines even if they are in the past.
   - Never ignore a deadline just because it has passed.
   - Library return dates, payment due dates, assignment
     submission dates and expired registration dates
     must be extracted when explicitly mentioned.
   - Set deadline_detected = true when a specific
     past or future deadline date is available.
   - If the date is known but the time is unknown,
     keep deadline_time_ist and deadline_datetime_ist null.
   - Do not confuse the email received date with
     the actual deadline date.

4. Detect meetings and events.
   Distinguish:
   - confirmed: explicitly scheduled or confirmed
   - proposed: suggested but not yet accepted
   - cancelled: explicitly cancelled
   - unknown: status cannot be determined

5. Do not treat an interview invitation asking the user
   to select a slot as a confirmed meeting.

6. Date and timezone rules:
   - Resolve today, tomorrow, and other relative dates
     using the email's Received Time.
   - Never use the computer's current date to resolve
     relative dates in an email.
   - Default timezone is Asia/Kolkata (IST).
   - If the email specifies another timezone, honor it
     and convert the resulting date and time to IST.
   - If a date or time cannot be determined, use null.
   - Never invent dates or times.

7. Set alarm_required to true ONLY when:
   - A real meeting or event is confirmed.
   - Its exact date and time are known.
   - It requires the user's attention or attendance.
   Proposed meetings must have alarm_required = false.

8. Scam detection:
   - Set is_scam to true only when there are credible
     indicators of phishing or fraud.
   - Do not classify an email as a scam merely because
     it contains a link or security code.
   - Never repeat passwords, OTPs, or security codes
     in the summary or scam_reason.

9. Write a short, useful summary.
10. Set action_required to true when the user needs
    to do something after reading the email.

RETURN JSON WITH EXACTLY THESE FIELDS:

{{
    "category": "Academic",
    "priority": "High",
    "summary": "Short email summary",
    "action_required": true,
    "is_scam": false,
    "scam_reason": null,

    "deadline_detected": true,
    "deadline_date_ist": "2026-11-13",
    "deadline_time_ist": "23:59",
    "deadline_datetime_ist": "2026-11-13T23:59:00+05:30",
    "deadline_description": "Project submission deadline",

    "event_detected": false,
    "event_type": null,
    "event_title": null,
    "event_date_ist": null,
    "event_time_ist": null,
    "event_datetime_ist": null,
    "event_status": null,
    "alarm_required": false
}}

Use null for unknown or unavailable values.
Use actual JSON booleans, not strings.
Return no Markdown or explanations.
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a precise email analysis assistant. Return valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1500
    )

    result_text = response.choices[0].message.content

    if not result_text:
        raise ValueError("Groq returned an empty analysis response.")

    result = json.loads(result_text)

    # Preserve the original email ID for database integration.
    result["email_id"] = email_id

    return result

def analyze_emails(emails, client=None):
    """
    Analyze multiple emails using Groq.
    Automatically retries failed requests.
    """

    if client is None:
        client = initialize_groq()

    results = []

    for index, email in enumerate(emails, start=1):

        email_id = email.get("email_id") or email.get("id")

        print(f"Analyzing email {index}/{len(emails)}...")

        for attempt in range(3):

            try:
                result = analyze_email(email, client)
                results.append(result)
                break

            except Exception as error:

                is_rate_limit = getattr(error, "status_code", None) == 429

                if is_rate_limit and attempt < 2:
                    wait_time = 2 * (attempt + 1)

                    print(
                        f"Rate limit reached. "
                        f"Retrying in {wait_time} seconds..."
                    )

                    time.sleep(wait_time)

                else:
                    print(f"Failed: {email_id}: {error}")

    return results

def extract_meeting_alarms(results):
    """
    Extract valid future meeting/event alarms.
    Excludes deadlines, proposed meetings and scam emails.
    """

    alarms = []

    for result in results:

        # Ignore scam emails
        if result.get("is_scam") is not False:
            continue

        # Only confirmed events are eligible
        if result.get("event_detected") is not True:
            continue

        if result.get("event_status") != "confirmed":
            continue

        # Alarm must be explicitly required
        if result.get("alarm_required") is not True:
            continue

        # Exact event date and time are mandatory
        event_datetime = result.get("event_datetime_ist")

        if not event_datetime:
            continue

        try:
            meeting_time = datetime.fromisoformat(event_datetime)

            # Ensure timezone is available
            if meeting_time.tzinfo is None:
                meeting_time = meeting_time.replace(tzinfo=TIMEZONE)

            # Convert to IST
            meeting_time = meeting_time.astimezone(TIMEZONE)

            # Ignore past events
            if meeting_time <= datetime.now(TIMEZONE):
                continue

        except (ValueError, TypeError):
            continue

        alarm = {
            "id": f"meeting_{result.get('email_id')}",
            "email_id": result.get("email_id"),
            "title": result.get("event_title") or "Upcoming Event",
            "timestamp": meeting_time,
            "meeting_time": meeting_time.isoformat(),
            "is_scam": False
}

        alarms.append(alarm)

    return alarms
