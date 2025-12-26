import os
import logging
import time
from typing import List, Dict, Any
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)

class SearchAgent:
    def __init__(self, api_key: str, config: Dict[str, Any]):
        self.api_key = api_key
        self.config = config
        self.filters = config.get("filters", {})
        self.retry_attempts = config.get("retry_attempts", 3)
        self.delay_seconds = config.get("delay_seconds", 2)

        if not self.api_key:
            logger.warning("SerpAPI key not provided. Search functionality will be limited.")

    def search_jobs(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """Searches for jobs using SerpAPI (Google Jobs) with retries and filtering."""
        if not self.api_key:
            logger.error("Cannot search without SerpAPI key.")
            return []

        logger.info(f"Searching for: {query}")
        
        params = {
            "engine": "google_jobs",
            "q": query,
            "api_key": self.api_key,
            "num": num_results,
            "hl": "en", # Language
        }

        for attempt in range(self.retry_attempts):
            try:
                search = GoogleSearch(params)
                results = search.get_dict()
                
                if "error" in results:
                    logger.error(f"SerpAPI Error: {results['error']}")
                    break

                jobs_results = results.get("jobs_results", [])
                logger.info(f"Found {len(jobs_results)} raw jobs for query '{query}'")
                
                parsed_jobs = []
                for job in jobs_results:
                    parsed_job = {
                        "company": job.get("company_name"),
                        "title": job.get("title"),
                        "location": job.get("location"),
                        "description": job.get("description"),
                        "link": job.get("related_links", [{}])[0].get("link") if job.get("related_links") else None,
                        "apply_link": job.get("apply_options", [{}])[0].get("link") if job.get("apply_options") else None,
                        "via": job.get("via")
                    }
                    
                    if self._is_valid_job(parsed_job):
                        parsed_jobs.append(parsed_job)
                
                logger.info(f"Filtered down to {len(parsed_jobs)} valid jobs.")
                return parsed_jobs

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.delay_seconds)
                else:
                    logger.error("All retry attempts failed.")
                    return []
        return []

    def search_google_general(self, query: str, num_results: int = 3) -> List[str]:
        """Performs a general Google Search to find company career pages or contacts."""
        if not self.api_key:
            return []

        logger.info(f"Performing general search for: {query}")
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": num_results
        }

        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            organic_results = results.get("organic_results", [])
            
            links = [res.get("link") for res in organic_results if res.get("link")]
            logger.info(f"Found {len(links)} general links for '{query}'")
            return links
        except Exception as e:
            logger.error(f"Error during general search: {e}")
            return []

    def _is_valid_job(self, job: Dict[str, Any]) -> bool:
        """Filters jobs based on configuration."""
        company = job.get("company", "").lower()
        title = job.get("title", "").lower()
        location = job.get("location", "").lower()
        description = job.get("description", "").lower()

        # 1. Exclude Keywords (Company)
        exclude_keywords = self.filters.get("company_exclude_keywords", [])
        for keyword in exclude_keywords:
            if keyword.lower() in company:
                logger.debug(f"Skipping job at {company} due to exclude keyword '{keyword}'")
                return False

        # 2. Remote Only
        if self.filters.get("remote_only"):
            if "remote" not in location and "remote" not in title and "remote" not in description:
                # Some jobs might be marked remote in metadata not captured here, but this is a heuristic
                logger.debug(f"Skipping non-remote job: {title} at {company} ({location})")
                return False

        # 3. Location Filter (if not remote only, or in addition)
        # If remote_only is True, we already checked for 'remote'. 
        # If we have specific locations allowed:
        allowed_locations = self.filters.get("locations", [])
        if allowed_locations and not self.filters.get("remote_only"):
            # Check if any allowed location matches the job location
            # This is a simple string match.
            match = False
            for loc in allowed_locations:
                if loc.lower() in location:
                    match = True
                    break
            if not match:
                 logger.debug(f"Skipping job in {location} (not in allowed locations)")
                 return False

        return True
