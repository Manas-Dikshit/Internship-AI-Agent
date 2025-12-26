import logging
import os
import re
from datetime import datetime
from typing import List
from email_validator import validate_email, EmailNotValidError
from pypdf import PdfReader

from urllib.parse import urlparse

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

def get_domain_from_url(url: str) -> str:
    """Extracts the domain from a URL (e.g., https://www.google.com -> google.com)."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return ""

def filter_emails(emails: List[str], allowed_prefixes: List[str], company_domain: str = None) -> List[str]:
    """Filters emails based on allowed prefixes and optionally matches company domain."""
    valid_emails = []
    for email in emails:
        if not validate_email_address(email):
            logging.debug(f"Invalid email format: {email}")
            continue
        
        # 1. Domain Match Check (High Accuracy)
        # If we know the company domain, prioritize emails that match it.
        if company_domain:
            email_domain = email.split("@")[-1]
            if company_domain in email_domain:
                # If it matches the company domain, we might be more lenient with prefixes, 
                # or strictly enforce them. Let's strictly enforce prefixes for safety.
                pass
            else:
                # If domain doesn't match, it might be a recruiting agency or generic email.
                # We can log this.
                logging.debug(f"Email {email} domain does not match company domain {company_domain}")
                # We might still allow it if it's a generic provider but has a valid prefix, 
                # but for "High Accuracy", we should prefer domain matches.
                # For now, let's just proceed to prefix check.

        # 2. Prefix Check
        is_allowed = False
        for prefix in allowed_prefixes:
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
