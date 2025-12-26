import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Set
from urllib.parse import urljoin
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class WebParser:
    def __init__(self):
        self.ua = UserAgent()
        self.email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    def extract_emails_from_url(self, url: str) -> List[str]:
        """Scrapes a webpage and extracts potential email addresses."""
        if not url:
            return []

        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/'
        }
        try:
            logger.info(f"Scraping URL: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            # Find all emails in text
            emails = set(re.findall(self.email_regex, text))
            
            # Also check mailto links
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('mailto:'):
                    email = href.replace('mailto:', '').split('?')[0]
                    emails.add(email)
            
            # Advanced: If no emails found, try to find a "Contact" or "Careers" link and follow it (depth=1)
            if not emails:
                logger.info("No emails found on main page. Looking for Contact/Careers links...")
                contact_links = []
                for a in soup.find_all('a', href=True):
                    text_content = a.get_text().lower()
                    if 'contact' in text_content or 'career' in text_content or 'about' in text_content:
                        full_link = urljoin(url, a['href'])
                        if full_link not in contact_links and full_link.startswith('http'):
                            contact_links.append(full_link)
                
                # Try the first 2 promising links
                for link in contact_links[:2]:
                    logger.info(f"Following link: {link}")
                    try:
                        resp_sub = requests.get(link, headers=headers, timeout=10)
                        if resp_sub.status_code == 200:
                            soup_sub = BeautifulSoup(resp_sub.text, 'html.parser')
                            text_sub = soup_sub.get_text()
                            found_sub = set(re.findall(self.email_regex, text_sub))
                            if found_sub:
                                logger.info(f"Found {len(found_sub)} emails on sub-page {link}")
                                emails.update(found_sub)
                    except Exception as e:
                        logger.warning(f"Failed to scrape sub-page {link}: {e}")

            logger.info(f"Found {len(emails)} total emails for {url}")
            return list(emails)

        except requests.RequestException as e:
            logger.error(f"Error scraping {url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing {url}: {e}")
            return []
