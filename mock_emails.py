"""
Mock Email Dataset for Outlook Email Bridge (Part 1).
Provides 10 realistic sample emails mimicking the data structure returned
by Microsoft Graph API for local development and testing without authentication.
"""

from typing import List, Dict, Any


def get_mock_emails() -> List[Dict[str, Any]]:
    """
    Returns 10 realistic sample Outlook emails for development and testing.

    Each dictionary matches the exact structure extracted by outlook_fetch.py:
    - id: Unique string identifier
    - sender_email: Email address of the sender
    - subject: Subject line
    - received_time: ISO 8601 timestamp string
    - body: Raw email body (HTML or plain text as Microsoft Graph returns)
    - is_read: Boolean status flag
    """
    return [
        {
            "id": "mock-outlook-msg-001",
            "sender_email": "prof.johnson@university.edu",
            "subject": "CS401: Midterm Project Guidelines & Submission Deadline",
            "received_time": "2026-11-09T16:45:00Z",
            "body": "<html><body><p>Dear Students,</p><p>Please note that the deadline for Milestone 1 of your final project is Friday, November 13th at 11:59 PM. Ensure your GitHub repository links are submitted to the portal on time.</p><p>Best regards,<br>Prof. Johnson</p></body></html>",
            "is_read": False,
        },
        {
            "id": "mock-outlook-msg-002",
            "sender_email": "registrar@university.edu",
            "subject": "Spring 2027 Course Registration Window Opens Monday",
            "received_time": "2026-11-09T15:30:12Z",
            "body": "<html><body><p>Hello Student,</p><p>Your priority registration window for the upcoming Spring 2027 semester will open on <strong>Monday, Nov 16 at 9:00 AM EST</strong>. Please review any academic holds on your account prior to this date.</p></body></html>",
            "is_read": True,
        },
        {
            "id": "mock-outlook-msg-003",
            "sender_email": "careers@techrecruiting-corp.com",
            "subject": "Interview Invitation: Software Engineering Intern (Summer 2027)",
            "received_time": "2026-11-09T14:15:45Z",
            "body": "<p>Hi there,</p><p>Thank you for applying to our Software Engineering Internship program. Our team was impressed by your profile and we would love to schedule a 45-minute technical screening with our engineering lead.</p><p>Please select a convenient slot via our calendar link.</p>",
            "is_read": False,
        },
        {
            "id": "mock-outlook-msg-004",
            "sender_email": "it-service-desk@university.edu",
            "subject": "Scheduled Maintenance: Campus VPN & Cloud Portal",
            "received_time": "2026-11-09T12:00:00Z",
            "body": "Please be advised that the Campus VPN and student portal services will undergo scheduled network maintenance on Saturday, Nov 14 from 2:00 AM to 6:00 AM. Connectivity may be intermittent during this window.",
            "is_read": True,
        },
        {
            "id": "mock-outlook-msg-005",
            "sender_email": "notifications@github.com",
            "subject": "[GitHub] Pull Request #14 merged: Fix token refresh timeout",
            "received_time": "2026-11-09T10:18:22Z",
            "body": "<html><body><p>Your pull request <strong>#14: Fix token refresh timeout</strong> has been reviewed and merged into <code>main</code> by @team-lead.</p><p>View changes on GitHub: https://github.com/example/outlook-email-bridge/pull/14</p></body></html>",
            "is_read": True,
        },
        {
            "id": "mock-outlook-msg-006",
            "sender_email": "sarah.miller@student.university.edu",
            "subject": "Group Project Meeting Today at 4 PM?",
            "received_time": "2026-11-09T09:05:10Z",
            "body": "Hey! Are we still meeting at the library study room 3B today at 4 PM to combine our slides for the database presentation? Let me know if that time still works for everyone.",
            "is_read": False,
        },
        {
            "id": "mock-outlook-msg-007",
            "sender_email": "library-notices@university.edu",
            "subject": "Library Overdue Notice: 'Designing Data-Intensive Applications'",
            "received_time": "2026-11-08T18:30:00Z",
            "body": "<p>Dear Patron,</p><p>The item <em>'Designing Data-Intensive Applications' by Martin Kleppmann</em> was due on November 07, 2026. Please return or renew this title online to avoid late fee charges.</p>",
            "is_read": True,
        },
        {
            "id": "mock-outlook-msg-008",
            "sender_email": "advising@engineering.university.edu",
            "subject": "Degree Audit & Graduation Check for Seniors",
            "received_time": "2026-11-08T14:10:05Z",
            "body": "Dear Senior Engineering Majors,\n\nIf you anticipate graduating this academic year, please schedule an advising check to verify your degree completion requirements before the end of the term.",
            "is_read": False,
        },
        {
            "id": "mock-outlook-msg-009",
            "sender_email": "security-alert@accountprotection.microsoft.com",
            "subject": "Microsoft account security code",
            "received_time": "2026-11-08T11:22:34Z",
            "body": "<html><body><p>Security code: <strong>482910</strong></p><p>Use this code to verify your sign-in to Microsoft services. If you did not request this code, you can safely ignore this email.</p></body></html>",
            "is_read": True,
        },
        {
            "id": "mock-outlook-msg-010",
            "sender_email": "events@campus-life.university.edu",
            "subject": "Annual Fall Hackathon & Tech Career Fair This Weekend!",
            "received_time": "2026-11-07T16:00:00Z",
            "body": "<html><body><h1>Fall Hackathon 2026</h1><p>Join over 300 students this Saturday for 24 hours of hacking, prizes, free food, and networking with top technology sponsors!</p><p>Register your team now at hackathon.university.edu.</p></body></html>",
            "is_read": True,
        },
    ]

