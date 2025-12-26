import logging
import os
import re
from datetime import datetime
from typing import List
from email_validator import validate_email, EmailNotValidError
from pypdf import PdfReader

def setup_logging(log_dir: str = "logs", log_file: str = "app.log"):
    """Configures logging for the application."""
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    logging.info("Logging initialized.")

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from a PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logging.error(f"Error reading PDF {pdf_path}: {e}")
        return ""

def validate_email_address(email: str) -> bool:
    """Validates an email address using email-validator."""
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False

def filter_emails(emails: List[str], allowed_prefixes: List[str]) -> List[str]:
    """Filters emails based on allowed prefixes (e.g., hr@, careers@)."""
    valid_emails = []
    for email in emails:
        if not validate_email_address(email):
            logging.debug(f"Invalid email format: {email}")
            continue
        
        # Check if email starts with any of the allowed prefixes
        # We check if the local part (before @) matches or if it's a generic contact email
        # For simplicity, we check if the email string contains the prefix logic or just use the list provided in config
        # The requirement says: "Only use public emails ending with careers@, hr@, jobs@, or contact@."
        # This likely means the local part. e.g. careers@company.com
        
        is_allowed = False
        for prefix in allowed_prefixes:
            # prefix is like "careers@"
            if email.lower().startswith(prefix.lower()):
                is_allowed = True
                break
        
        if is_allowed:
            valid_emails.append(email)
        else:
            logging.debug(f"Email {email} rejected by prefix filter.")
            
    return list(set(valid_emails))

def clean_text(text: str) -> str:
    """Cleans text by removing extra whitespace."""
    return " ".join(text.split())
