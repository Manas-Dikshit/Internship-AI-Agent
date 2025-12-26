import os
import yaml
import logging
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, date

from src.utils import setup_logging, filter_emails, extract_text_from_pdf
from src.search_agent import SearchAgent
from src.parser import WebParser
from src.email_agent import EmailGenerator
from src.mailer import Mailer

# Load environment variables
load_dotenv()

# Load configuration
with open("config/config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Setup logging
setup_logging(log_dir="logs", log_file="app.log")
logger = logging.getLogger(__name__)

def check_rate_limit(log_file: str, limit: int) -> bool:
    """Checks if the daily email limit has been reached."""
    if not os.path.exists(log_file):
        return True
    
    try:
        df = pd.read_csv(log_file)
        # Ensure timestamp column exists
        if "timestamp" not in df.columns:
            return True
            
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        today_emails = df[df["timestamp"].dt.date == date.today()]
        
        count = len(today_emails)
        logger.info(f"Emails sent today: {count}/{limit}")
        
        return count < limit
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        return True # Fail open or closed? Open for now, but log error.

def main():
    logger.info("Starting Internship Application Agent...")

    # Initialize Agents
    serpapi_key = os.getenv("SERPAPI_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    # Pass full search config to SearchAgent
    search_agent = SearchAgent(api_key=serpapi_key, config=config["search"])
    parser = WebParser()
    # Pass full email generation config to EmailGenerator
    email_generator = EmailGenerator(api_key=openai_api_key, config=config["email_generation"])
    mailer = Mailer(
        smtp_server=config["email_sending"]["smtp_server"],
        smtp_port=config["email_sending"]["smtp_port"],
        user_email=gmail_user,
        user_password=gmail_password
    )

    # Check Rate Limit
    sent_log_path = "data/sent_log.csv"
    daily_limit = config["email_sending"]["rate_limit_per_day"]
    if not check_rate_limit(sent_log_path, daily_limit):
        logger.warning("Daily email limit reached. Exiting.")
        return

    # 1. Search for Jobs
    all_jobs = []
    for keyword in config["search"]["keywords"]:
        jobs = search_agent.search_jobs(keyword, num_results=config["search"]["max_results"])
        all_jobs.extend(jobs)
    
    logger.info(f"Total jobs found: {len(all_jobs)}")

    # 2. Process Jobs
    sent_log = []
    resume_path = "data/resume.pdf"
    
    # Extract text from resume PDF
    if os.path.exists(resume_path):
        resume_text = extract_text_from_pdf(resume_path)
        if not resume_text:
            logger.warning("Could not extract text from resume. Using placeholder.")
            resume_text = "Experienced Software Engineer..."
    else:
        logger.warning("Resume file not found at data/resume.pdf")
        resume_text = "Experienced Software Engineer..."

    emails_sent_session = 0

    for job in all_jobs:
        # Re-check rate limit dynamically
        if not check_rate_limit(sent_log_path, daily_limit - emails_sent_session):
             logger.warning("Daily limit reached during execution. Stopping.")
             break

        company = job.get("company")
        title = job.get("title")
        link = job.get("link") or job.get("apply_link")

        if not link:
            logger.warning(f"No link found for {title} at {company}, skipping.")
            continue

        logger.info(f"Processing {title} at {company}...")

        # 3. Find Contact Email
        emails = parser.extract_emails_from_url(link)
        valid_emails = filter_emails(emails, config["safety"]["allowed_domains"])

        if not valid_emails:
            logger.info(f"No valid contact email found for {company}. Skipping email generation.")
            continue

        target_email = valid_emails[0] # Pick the first one
        logger.info(f"Found target email: {target_email}")

        # 4. Generate Email
        email_body = email_generator.generate_email(
            job_details=job,
            resume_text=resume_text,
            template=config["email_generation"]["template"]
        )

        if not email_body:
            logger.error("Failed to generate email body.")
            continue

        # 5. Send Email
        # Personalize subject if needed, or use template subject if it was part of the body generation (usually separate)
        # The config template has "Subject: ..." inside it. 
        # We need to parse the subject from the generated body or generate it separately.
        # For now, we'll assume the generated body contains the subject line or we strip it.
        # A common pattern is to have the LLM generate the whole email including subject.
        
        subject = f"Application for {title} - [Your Name]" 
        # If the generated content starts with "Subject:", extract it.
        if email_body.startswith("Subject:"):
            lines = email_body.split("\n")
            subject = lines[0].replace("Subject:", "").strip()
            email_body = "\n".join(lines[1:]).strip()

        success = mailer.send_email(
            to_email=target_email,
            subject=subject,
            body=email_body,
            attachment_path=resume_path
        )

        status = "Sent" if success else "Failed"
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "company": company,
            "role": title,
            "email_sent_to": target_email,
            "status": status
        }
        sent_log.append(log_entry)
        
        # Append to CSV immediately to avoid data loss and for rate limiting
        df = pd.DataFrame([log_entry])
        if os.path.exists(sent_log_path):
            df.to_csv(sent_log_path, mode='a', header=False, index=False)
        else:
            df.to_csv(sent_log_path, index=False)

        if success:
            emails_sent_session += 1

    logger.info("Workflow completed.")

if __name__ == "__main__":
    main()
