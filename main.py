import os
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Load environment variables from .env file
load_dotenv()

# Define Google API permissions
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Read project settings from .env
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "Sheet1")
MAX_EMAILS = int(os.getenv("MAX_EMAILS", "10"))


def get_google_credentials():
    """Create or refresh Google OAuth credentials."""

    creds = None

    # Load existing token if available
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # Create new token if credentials are missing or invalid
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError(
                    "credentials.json not found. Please download it from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES
            )

            creds = flow.run_local_server(port=0)

        # Save token for future runs
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def get_header(headers, name):
    """Extract a specific header from Gmail message headers."""

    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")

    return ""


def read_recent_emails(gmail_service):
    """Read recent emails from Gmail inbox."""

    results = gmail_service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=MAX_EMAILS
    ).execute()

    messages = results.get("messages", [])
    email_rows = []

    for message in messages:
        msg = gmail_service.users().messages().get(
            userId="me",
            id=message["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()

        headers = msg.get("payload", {}).get("headers", [])

        sender = get_header(headers, "From")
        subject = get_header(headers, "Subject")
        date_raw = get_header(headers, "Date")
        snippet = msg.get("snippet", "")

        try:
            date_value = parsedate_to_datetime(date_raw).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            date_value = date_raw

        email_rows.append([
            date_value,
            sender,
            subject,
            snippet
        ])

    return email_rows


def save_to_google_sheet(sheets_service, rows):
    """Append email data rows to Google Sheet."""

    if not SPREADSHEET_ID:
        raise ValueError("SPREADSHEET_ID is missing in .env file.")

    if not rows:
        print("No emails found.")
        return

    range_name = f"{SHEET_NAME}!A:D"

    body = {
        "values": rows
    }

    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()

    print(f"{len(rows)} emails saved to Google Sheet.")


def main():
    """Main workflow: read Gmail emails and save them to Google Sheets."""

    try:
        creds = get_google_credentials()

        gmail_service = build("gmail", "v1", credentials=creds)
        sheets_service = build("sheets", "v4", credentials=creds)

        rows = read_recent_emails(gmail_service)
        save_to_google_sheet(sheets_service, rows)

    except Exception as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
