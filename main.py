
"""
MindWise - Complete Email Processing Pipeline

1. Retrieve Outlook emails (Mock or Live mode).
2. Normalize emails.
3. Analyze emails using Groq AI.
4. Save analyzed emails to Firestore.
5. Extract valid meeting alarms.
6. Save alarms to Firestore.
"""

import sys
import config

from outlook_auth import get_access_token
from outlook_fetch import fetch_inbox_emails
from mock_emails import get_mock_emails

from email_processor import process_emails
from groq_analyzer import (
    initialize_groq,
    analyze_emails,
    extract_meeting_alarms
)

from firestore_rest import save_emails, save_meeting_alarm


def main():

    print("=" * 70)
    print("                 MINDWISE - EMAIL ASSISTANT")
    print("=" * 70)

    # STEP 1: Configuration
    try:
        config.validate_config()
    except Exception as error:
        print("[CONFIGURATION ERROR]", error)
        return

    # STEP 2: Retrieve Outlook emails
    if config.MOCK_MODE:

        print("\n[MOCK MODE] Loading sample Outlook emails...")
        emails = get_mock_emails()

    else:

        print("\n[LIVE MODE] Connecting to Outlook...")

        try:
            access_token = get_access_token()

            if not access_token:
                print("[ERROR] Authentication failed.")
                return

            emails = fetch_inbox_emails(
                access_token=access_token,
                top=10
            )

        except KeyboardInterrupt:
            print("\n[INFO] Operation cancelled.")
            return

        except Exception as error:
            print("[OUTLOOK ERROR]", error)
            return

    print("\nEmails retrieved:", len(emails))

    if not emails:
        print("No emails found.")
        return

    # STEP 3: Normalize emails
    print("\n[STEP 1/6] Processing emails...")

    try:
        processed_emails = process_emails(emails)
        print("Successfully processed:", len(processed_emails))

    except Exception as error:
        print("[PROCESSING ERROR]", error)
        return

    if not processed_emails:
        print("No valid emails to analyze.")
        return

    # STEP 4: Initialize Groq and analyze emails
    print("\n[STEP 2/6] Initializing Groq AI...")

    try:
        client = initialize_groq()

        print("[SUCCESS] Groq connected.")

        print("\n[STEP 3/6] Analyzing emails...")

        analysis_results = analyze_emails(
            processed_emails,
            client
        )

        print("\nSuccessfully analyzed:", len(analysis_results))

    except Exception as error:
        print("[GROQ ERROR]", error)
        return

    # STEP 5: Combine processed emails and AI results
    print("\n[STEP 4/6] Preparing email records...")

    analysis_map = {
        result.get("email_id"): result
        for result in analysis_results
        if result.get("email_id")
    }

    final_emails = []

    for email in processed_emails:

        email_id = email.get("email_id")
        combined_email = dict(email)

        analysis = analysis_map.get(email_id)

        if analysis:
            combined_email.update(analysis)
            combined_email["status"] = "analyzed"
        else:
            combined_email["status"] = "analysis_failed"

        final_emails.append(combined_email)

    # STEP 6: Save analyzed emails to Firestore
    print("\n[STEP 5/6] Saving emails to Firestore...")

    try:
        saved_emails = save_emails(final_emails)

        print("[SUCCESS] Emails saved:", len(saved_emails))

    except Exception as error:
        print("[FIRESTORE EMAIL ERROR]", error)

    # STEP 7: Extract and save meeting alarms
    print("\n[STEP 6/6] Extracting meeting alarms...")

    try:
        alarms = extract_meeting_alarms(analysis_results)

        print("Valid alarms detected:", len(alarms))

        saved_alarm_count = 0

        for alarm in alarms:

            try:
                save_meeting_alarm(alarm)

                saved_alarm_count += 1

                print(
                    "[SUCCESS] Alarm saved:",
                    alarm["title"]
                )

            except Exception as error:
                print(
                    "[ALARM SAVE ERROR]",
                    alarm.get("title"),
                    error
                )

        print("\nSuccessfully saved alarms:", saved_alarm_count)

    except Exception as error:
        print("[ALARM ERROR]", error)
        saved_alarm_count = 0

    # FINAL REPORT
    print("\n" + "=" * 70)
    print("               MINDWISE PROCESSING REPORT")
    print("=" * 70)

    print("Emails retrieved:       ", len(emails))
    print("Emails processed:       ", len(processed_emails))
    print("Emails analyzed:        ", len(analysis_results))
    print("Emails saved:           ", len(final_emails))
    print("Alarms detected:        ", len(alarms))
    print("Alarms saved:            ", saved_alarm_count)

    print("\nMode:", "Mock" if config.MOCK_MODE else "Live Outlook")

    print("\nMindWise pipeline execution completed.")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] MindWise execution interrupted.")
        sys.exit(0)
