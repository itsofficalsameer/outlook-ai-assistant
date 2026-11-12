"""
Firestore REST API Connection & Operations Module for MindWise (Outlook AI Email Assistant).

Connects to Google Cloud Firestore using standard HTTPS REST calls authenticated
via Google Service Account credentials (AuthorizedSession). This avoids native
gRPC DLL dependencies, making it fully compatible with Windows Smart App Control
and strict system environments.

Provides full CRUD operations for:
1. 'emails' collection (saving, updating, deleting, retrieving processed emails)
2. 'meeting_alarms' collection (saving and retrieving meeting alarms for Flutter UI)
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import urllib.parse
import uuid
import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

# Relative path to the service account credentials JSON file
PROJECT_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = PROJECT_DIR / "secrets" / "firebase-service-account.json"

# Firestore REST API Base URL and Scopes
FIRESTORE_API_BASE_URL = "https://firestore.googleapis.com/v1"
SCOPES = ["https://www.googleapis.com/auth/datastore"]

# Cached module-level session and project ID
_session: Optional[AuthorizedSession] = None
_project_id: Optional[str] = None


# ==============================================================================
# FIRESTORE DATA TYPE CONVERTERS (PYTHON <-> FIRESTORE REST JSON)
# ==============================================================================

def _python_to_firestore_value(val: Any) -> Dict[str, Any]:
    """
    Converts a Python native value to Firestore REST API typed value format.
    Handles None, bool, int, float, str, datetime, list/tuple, and dict.
    """
    if val is None:
        return {"nullValue": None}
    # Note: Check bool before int, because in Python bool is a subclass of int
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, datetime):
        # Format datetime as RFC 3339 UTC string with trailing 'Z'
        if val.tzinfo is None:
            utc_dt = val.replace(tzinfo=timezone.utc)
        else:
            utc_dt = val.astimezone(timezone.utc)
        iso_str = utc_dt.isoformat().replace("+00:00", "Z")
        if not iso_str.endswith("Z"):
            iso_str += "Z"
        return {"timestampValue": iso_str}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, (list, tuple)):
        return {
            "arrayValue": {
                "values": [_python_to_firestore_value(item) for item in val]
            }
        }
    if isinstance(val, dict):
        return {
            "mapValue": {
                "fields": {k: _python_to_firestore_value(v) for k, v in val.items()}
            }
        }
    return {"stringValue": str(val)}


def _dict_to_firestore_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a Python dictionary of fields into the Firestore document 'fields' structure.
    """
    return {
        "fields": {
            k: _python_to_firestore_value(v) for k, v in data.items()
        }
    }


def _firestore_value_to_python(val_dict: Dict[str, Any]) -> Any:
    """
    Converts a Firestore REST API typed value dictionary back into a native Python value.
    """
    if not isinstance(val_dict, dict):
        return val_dict
    if "stringValue" in val_dict:
        return val_dict["stringValue"]
    if "booleanValue" in val_dict:
        return val_dict["booleanValue"]
    if "integerValue" in val_dict:
        return int(val_dict["integerValue"])
    if "doubleValue" in val_dict:
        return float(val_dict["doubleValue"])
    if "timestampValue" in val_dict:
        return val_dict["timestampValue"]
    if "nullValue" in val_dict:
        return None
    if "mapValue" in val_dict:
        fields = val_dict["mapValue"].get("fields", {})
        return {k: _firestore_value_to_python(v) for k, v in fields.items()}
    if "arrayValue" in val_dict:
        values = val_dict["arrayValue"].get("values", [])
        return [_firestore_value_to_python(item) for item in values]
    return None


def _firestore_doc_to_dict(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts a complete Firestore REST document response into a standard Python dictionary.
    Extracts the document ID from the 'name' field if not present in the fields.
    """
    fields = doc_data.get("fields", {})
    result = {k: _firestore_value_to_python(v) for k, v in fields.items()}

    doc_name = doc_data.get("name", "")
    if doc_name:
        doc_id = urllib.parse.unquote(doc_name.split("/")[-1])
        if "id" not in result and "email_id" not in result:
            result["id"] = doc_id

    return result


# ==============================================================================
# INITIALIZATION & METADATA
# ==============================================================================

def get_project_id() -> str:
    """
    Returns the Firebase project ID dynamically extracted from the service account JSON.

    Returns:
        str: The Google Cloud / Firebase project ID.

    Raises:
        FileNotFoundError: If the service account credential file is missing.
        RuntimeError: If the project_id field cannot be found or read.
    """
    global _project_id

    if _project_id:
        return _project_id

    if not CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(
            f"Service account file not found at: {CREDENTIALS_PATH}\n"
            "Please ensure 'secrets/firebase-service-account.json' exists in the project root."
        )

    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            cred_data = json.load(f)
            project_id = cred_data.get("project_id")
            if not project_id:
                raise ValueError("The 'project_id' field is missing in the service account JSON.")
            _project_id = project_id
            return _project_id
    except json.JSONDecodeError as json_err:
        raise RuntimeError(
            f"Failed to parse service account JSON file: {json_err}"
        ) from json_err
    except Exception as err:
        raise RuntimeError(
            f"Could not read project ID from credentials file: {err}"
        ) from err


def initialize_firestore() -> AuthorizedSession:
    """
    Authenticates using the service account credentials and creates an AuthorizedSession
    for making authenticated REST calls to the Firestore REST API.

    Initializes only once and caches the session to avoid duplicate overhead.

    Returns:
        google.auth.transport.requests.AuthorizedSession: The authenticated session object.

    Raises:
        FileNotFoundError: If the service account JSON is not found.
        RuntimeError: If authentication or credentials loading fails.
    """
    global _session, _project_id

    if _session is not None:
        return _session

    if not CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(
            f"Service account file not found at: {CREDENTIALS_PATH}\n"
            "Please verify that 'secrets/firebase-service-account.json' exists."
        )

    try:
        # Load Google service account credentials with Firestore datastore scope
        credentials = service_account.Credentials.from_service_account_file(
            str(CREDENTIALS_PATH),
            scopes=SCOPES,
        )

        # Store project ID dynamically
        _project_id = credentials.project_id or get_project_id()

        # Create an AuthorizedSession that automatically adds Bearer tokens to requests
        _session = AuthorizedSession(credentials)
        return _session

    except GoogleAuthError as auth_err:
        raise RuntimeError(
            f"Authentication failed with Google service account: {auth_err}"
        ) from auth_err
    except Exception as exc:
        raise RuntimeError(
            f"Unexpected error initializing Firestore REST session: {exc}"
        ) from exc


def get_database_info(database_id: str = "(default)") -> Dict[str, Any]:
    """
    Sends an authenticated GET request to the Firestore database metadata endpoint
    for the specified database (defaulting to '(default)').

    REST Endpoint:
        GET https://firestore.googleapis.com/v1/projects/{project_id}/databases/{database_id}

    Args:
        database_id (str): Database name identifier, defaults to '(default)'.

    Returns:
        Dict[str, Any]: Parsed JSON response containing database metadata.
    """
    session = initialize_firestore()
    project_id = get_project_id()

    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/{database_id}"

    try:
        response = session.get(url, timeout=15)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise RuntimeError(
                "401 Unauthorized: The service account token was rejected. "
                "Check service account status and validity."
            )
        elif response.status_code == 403:
            raise RuntimeError(
                f"403 Forbidden: Insufficient permissions for project '{project_id}'. "
                "Ensure Cloud Datastore / Firestore IAM role is assigned to the service account."
            )
        elif response.status_code == 404:
            raise RuntimeError(
                f"404 Not Found: Database '{database_id}' was not found in project '{project_id}'."
            )
        else:
            raise RuntimeError(
                f"HTTP {response.status_code} Error from Firestore REST API: {response.text}"
            )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Connection timed out while contacting Firestore REST API. Check your internet connection."
        )
    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(
            f"Network error while connecting to Firestore REST API: {req_err}"
        ) from req_err


# ==============================================================================
# EMAIL COLLECTION OPERATIONS
# ==============================================================================

def save_email(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Saves or updates a processed email in the 'emails' collection.

    Uses the email_id as the document ID where available. If a document with
    the same ID already exists, it is safely updated rather than duplicated (upsert via PATCH).
    Preserves all fields produced by email_processor.py:
        email_id, sender_email, subject, received_time, body, is_read, status

    Args:
        email_data (Dict[str, Any]): Processed email dictionary.

    Returns:
        Dict[str, Any]: The saved email data.

    Raises:
        ValueError: If email_data is invalid or missing.
        RuntimeError: If the HTTP request to Firestore REST API fails.
    """
    if not isinstance(email_data, dict) or not email_data:
        raise ValueError("email_data must be a non-empty dictionary.")

    session = initialize_firestore()
    project_id = get_project_id()

    # Determine document ID (use email_id or id if available, fallback to generated UUID)
    raw_id = email_data.get("email_id") or email_data.get("id")
    if not raw_id:
        raw_id = f"email_{uuid.uuid4().hex[:12]}"

    doc_id = str(raw_id).strip()

    # Ensure email_id field is explicitly preserved in the saved data
    record = dict(email_data)
    record["email_id"] = doc_id

    # URL-encode document ID to safely handle special characters (e.g. '=', '/', '+')
    encoded_id = urllib.parse.quote(doc_id, safe="")
    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/(default)/documents/emails/{encoded_id}"

    payload = _dict_to_firestore_fields(record)

    try:
        # PATCH upserts: creates if new, replaces/updates if already exists (no 409 conflict)
        response = session.patch(url, json=payload, timeout=15)

        if response.status_code == 200:
            return record
        elif response.status_code == 401:
            raise RuntimeError("401 Unauthorized: Service account token expired or rejected.")
        elif response.status_code == 403:
            raise RuntimeError(f"403 Forbidden: Insufficient write permissions for project '{project_id}'.")
        else:
            raise RuntimeError(f"HTTP {response.status_code} Error saving email: {response.text}")

    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Network error while saving email '{doc_id}': {req_err}") from req_err


def save_emails(email_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Saves multiple processed emails to the 'emails' collection.

    Args:
        email_list (List[Dict[str, Any]]): List of processed email dictionaries.

    Returns:
        List[Dict[str, Any]]: List of successfully saved email dictionaries.

    Raises:
        ValueError: If email_list is not a list.
    """
    if not isinstance(email_list, list):
        raise ValueError("email_list must be a list of email dictionaries.")

    saved_records = []
    for email in email_list:
        saved = save_email(email)
        saved_records.append(saved)

    return saved_records


def get_email(email_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single email document by its document ID from the 'emails' collection.

    Args:
        email_id (str): The document ID of the email.

    Returns:
        Optional[Dict[str, Any]]: The parsed email dictionary if found, or None if not found.

    Raises:
        ValueError: If email_id is missing or blank.
        RuntimeError: On HTTP or network errors.
    """
    if not email_id or not str(email_id).strip():
        raise ValueError("email_id must be a non-empty string.")

    session = initialize_firestore()
    project_id = get_project_id()

    encoded_id = urllib.parse.quote(str(email_id).strip(), safe="")
    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/(default)/documents/emails/{encoded_id}"

    try:
        response = session.get(url, timeout=15)

        if response.status_code == 200:
            return _firestore_doc_to_dict(response.json())
        elif response.status_code == 404:
            return None
        elif response.status_code == 401:
            raise RuntimeError("401 Unauthorized: Service account token expired or invalid.")
        elif response.status_code == 403:
            raise RuntimeError(f"403 Forbidden: Insufficient read permissions for project '{project_id}'.")
        else:
            raise RuntimeError(f"HTTP {response.status_code} Error retrieving email: {response.text}")

    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Network error while retrieving email '{email_id}': {req_err}") from req_err


def get_all_emails(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieves all saved email documents from the 'emails' collection.

    Args:
        limit (int): Maximum number of emails to retrieve per page (default: 100).

    Returns:
        List[Dict[str, Any]]: List of email dictionaries stored in Firestore.

    Raises:
        RuntimeError: On HTTP or network errors.
    """
    session = initialize_firestore()
    project_id = get_project_id()

    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/(default)/documents/emails"
    params = {"pageSize": limit}

    emails: List[Dict[str, Any]] = []

    try:
        while True:
            response = session.get(url, params=params, timeout=15)

            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code} Error reading emails: {response.text}")

            data = response.json()
            docs = data.get("documents", [])

            for doc in docs:
                emails.append(_firestore_doc_to_dict(doc))

            # Check if additional pages exist
            next_page_token = data.get("nextPageToken")
            if next_page_token:
                params["pageToken"] = next_page_token
            else:
                break

        return emails

    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Network error while retrieving all emails: {req_err}") from req_err


def update_email(email_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates selected fields of an existing email document in the 'emails' collection.
    Uses updateMask to modify only the specified fields without overwriting other data.

    Args:
        email_id (str): The document ID of the email to update.
        updates (Dict[str, Any]): Dictionary of fields and new values to update.

    Returns:
        Dict[str, Any]: The updated fields.

    Raises:
        ValueError: If email_id or updates are empty.
        KeyError: If the document does not exist.
        RuntimeError: On HTTP or network errors.
    """
    if not email_id or not str(email_id).strip():
        raise ValueError("email_id must be a non-empty string.")
    if not isinstance(updates, dict) or not updates:
        raise ValueError("updates must be a non-empty dictionary.")

    session = initialize_firestore()
    project_id = get_project_id()

    encoded_id = urllib.parse.quote(str(email_id).strip(), safe="")
    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/(default)/documents/emails/{encoded_id}"

    # updateMask ensures only specified field paths are altered in Firestore
    params = [("updateMask.fieldPaths", k) for k in updates.keys()]
    payload = _dict_to_firestore_fields(updates)

    try:
        response = session.patch(url, params=params, json=payload, timeout=15)

        if response.status_code == 200:
            return _firestore_doc_to_dict(response.json())
        elif response.status_code == 404:
            raise KeyError(f"Email with ID '{email_id}' was not found in Firestore.")
        else:
            raise RuntimeError(f"HTTP {response.status_code} Error updating email: {response.text}")

    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Network error while updating email '{email_id}': {req_err}") from req_err


def delete_email(email_id: str) -> bool:
    """
    Deletes an email document from the 'emails' collection.

    Args:
        email_id (str): The document ID of the email to delete.

    Returns:
        bool: True if the deletion succeeded.

    Raises:
        ValueError: If email_id is missing or blank.
        RuntimeError: On HTTP or network errors.
    """
    if not email_id or not str(email_id).strip():
        raise ValueError("email_id must be a non-empty string.")

    session = initialize_firestore()
    project_id = get_project_id()

    encoded_id = urllib.parse.quote(str(email_id).strip(), safe="")
    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/(default)/documents/emails/{encoded_id}"

    try:
        response = session.delete(url, timeout=15)

        if response.status_code in (200, 204):
            return True
        else:
            raise RuntimeError(f"HTTP {response.status_code} Error deleting email: {response.text}")

    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Network error while deleting email '{email_id}': {req_err}") from req_err


# ==============================================================================
# MEETING ALARMS COLLECTION OPERATIONS (FLUTTER COMPATIBLE)
# ==============================================================================

def save_meeting_alarm(alarm_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Saves a meeting alarm in the 'meeting_alarms' collection.

    Preserves Flutter-compatible fields:
        - title (str): Meeting or alarm title
        - meeting_time or timestamp (str): Meeting date/time
        - is_scam (bool): Scam detection flag (defaults to False)
        - sender_email (str, optional): Sender or organizer email
        - status (str, optional): e.g. 'scheduled', 'active'

    Note: Meeting alarms must be explicitly supplied with valid data.
    Ordinary emails are never converted into alarms automatically.

    Args:
        alarm_data (Dict[str, Any]): Dictionary containing meeting alarm details.
            Must contain at least a 'title' (or 'meeting_title') and 'timestamp' (or 'meeting_time').

    Returns:
        Dict[str, Any]: The saved meeting alarm dictionary.

    Raises:
        ValueError: If alarm_data is invalid, empty, or lacks title/time.
        RuntimeError: If the HTTP request to Firestore REST API fails.
    """
    if not isinstance(alarm_data, dict) or not alarm_data:
        raise ValueError("alarm_data must be a non-empty dictionary.")

    # Validate essential meeting alarm fields
    title = alarm_data.get("title") or alarm_data.get("meeting_title")
    raw_meeting_time = alarm_data.get("meeting_time")
    raw_timestamp = alarm_data.get("timestamp")

    # Determine time value from either meeting_time or timestamp
    time_candidate = raw_meeting_time if raw_meeting_time is not None else raw_timestamp

    if not title or not str(title).strip():
        raise ValueError("Meeting alarm must explicitly include a valid 'title'.")
    if time_candidate is None:
        raise ValueError("Meeting alarm must explicitly include a valid 'meeting_time' or 'timestamp'.")
    if isinstance(time_candidate, str) and not time_candidate.strip():
        raise ValueError("Meeting alarm must explicitly include a valid 'meeting_time' or 'timestamp'.")

    # Convert meeting_time to an ISO 8601 string for Flutter's fallback parser
    if isinstance(time_candidate, datetime):
        if time_candidate.tzinfo is None:
            utc_dt = time_candidate.replace(tzinfo=timezone.utc)
        else:
            utc_dt = time_candidate.astimezone(timezone.utc)
        meeting_time_str = utc_dt.isoformat().replace("+00:00", "Z")
        if not meeting_time_str.endswith("Z"):
            meeting_time_str += "Z"
    else:
        meeting_time_str = str(time_candidate).strip()

    # Determine timestamp field (supports datetime object or string)
    if raw_timestamp is not None:
        if isinstance(raw_timestamp, datetime):
            timestamp_val = raw_timestamp
        else:
            timestamp_val = str(raw_timestamp).strip()
    else:
        # If timestamp was not supplied, use time_candidate (datetime or string)
        timestamp_val = time_candidate

    # Validate is_scam field
    raw_is_scam = alarm_data.get("is_scam")
    if raw_is_scam is None:
        is_scam_val = False
    elif isinstance(raw_is_scam, bool):
        is_scam_val = raw_is_scam
    elif isinstance(raw_is_scam, str):
        clean_str = raw_is_scam.strip().lower()
        if clean_str == "true":
            is_scam_val = True
        elif clean_str == "false":
            is_scam_val = False
        else:
            raise ValueError(
                f"Invalid value for 'is_scam': '{raw_is_scam}'. Expected a boolean (True/False) or string ('true'/'false')."
            )
    else:
        raise ValueError(
            f"Invalid type for 'is_scam': {type(raw_is_scam).__name__}. Expected a boolean (True/False) or string ('true'/'false')."
        )

    session = initialize_firestore()
    project_id = get_project_id()

    # Determine unique document ID
    raw_id = alarm_data.get("id") or alarm_data.get("alarm_id")
    if not raw_id:
        raw_id = f"alarm_{uuid.uuid4().hex[:12]}"

    alarm_id = str(raw_id).strip()

    # Build standardized alarm record preserving Flutter frontend expected fields
    record = dict(alarm_data)
    record["id"] = alarm_id
    record["title"] = str(title).strip()
    record["meeting_time"] = meeting_time_str
    record["timestamp"] = timestamp_val
    record["is_scam"] = is_scam_val

    encoded_id = urllib.parse.quote(alarm_id, safe="")
    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/(default)/documents/meeting_alarms/{encoded_id}"

    payload = _dict_to_firestore_fields(record)

    try:
        response = session.patch(url, json=payload, timeout=15)

        if response.status_code == 200:
            return record
        elif response.status_code == 401:
            raise RuntimeError("401 Unauthorized: Service account token expired or rejected.")
        elif response.status_code == 403:
            raise RuntimeError(f"403 Forbidden: Insufficient permissions for project '{project_id}'.")
        else:
            raise RuntimeError(f"HTTP {response.status_code} Error saving meeting alarm: {response.text}")

    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Network error while saving meeting alarm '{alarm_id}': {req_err}") from req_err


def get_meeting_alarms(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieves all meeting alarms from the 'meeting_alarms' collection.

    Args:
        limit (int): Maximum number of alarms to retrieve per page (default: 100).

    Returns:
        List[Dict[str, Any]]: List of meeting alarm dictionaries.

    Raises:
        RuntimeError: On HTTP or network errors.
    """
    session = initialize_firestore()
    project_id = get_project_id()

    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/(default)/documents/meeting_alarms"
    params = {"pageSize": limit}

    alarms: List[Dict[str, Any]] = []

    try:
        while True:
            response = session.get(url, params=params, timeout=15)

            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code} Error reading meeting alarms: {response.text}")

            data = response.json()
            docs = data.get("documents", [])

            for doc in docs:
                alarms.append(_firestore_doc_to_dict(doc))

            next_page_token = data.get("nextPageToken")
            if next_page_token:
                params["pageToken"] = next_page_token
            else:
                break

        return alarms

    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Network error while retrieving meeting alarms: {req_err}") from req_err


def delete_meeting_alarm(alarm_id: str) -> bool:
    """
    Deletes a meeting alarm from the 'meeting_alarms' collection.

    Args:
        alarm_id (str): The document ID of the alarm to delete.

    Returns:
        bool: True if the deletion succeeded.
    """
    if not alarm_id or not str(alarm_id).strip():
        raise ValueError("alarm_id must be a non-empty string.")

    session = initialize_firestore()
    project_id = get_project_id()

    encoded_id = urllib.parse.quote(str(alarm_id).strip(), safe="")
    url = f"{FIRESTORE_API_BASE_URL}/projects/{project_id}/databases/(default)/documents/meeting_alarms/{encoded_id}"

    try:
        response = session.delete(url, timeout=15)
        if response.status_code in (200, 204):
            return True
        else:
            raise RuntimeError(f"HTTP {response.status_code} Error deleting meeting alarm: {response.text}")
    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Network error while deleting meeting alarm '{alarm_id}': {req_err}") from req_err


# ==============================================================================
# MAIN (PRESERVED STANDALONE CONNECTION TEST)
# ==============================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("      MINDWISE - FIRESTORE REST API CONNECTION TEST")
    print("=" * 65)

    try:
        # Initialize authorized session
        session = initialize_firestore()
        project_id = get_project_id()
        print(f"[OK] Service account authenticated successfully.")
        print(f"[OK] Detected Project ID: {project_id}")

        # Fetch database metadata
        print(f"[INFO] Requesting metadata for database '(default)' over HTTPS...")
        db_info = get_database_info()

        print("\n" + "-" * 65)
        print("SUCCESS: Connected to Firestore REST API!")
        print(f"  Database Resource: {db_info.get('name', 'N/A')}")
        print(f"  Database Type:     {db_info.get('type', 'N/A')}")
        print(f"  Location ID:       {db_info.get('locationId', 'N/A')}")
        print(f"  Concurrency Mode:  {db_info.get('concurrencyMode', 'N/A')}")
        print("-" * 65)
        print("CRUD Operations for 'emails' and 'meeting_alarms' loaded successfully.")

    except Exception as e:
        print(f"\n[ERROR] Connection test failed: {e}")
        raise SystemExit(1)
