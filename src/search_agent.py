import os
import logging
import time
import random
from typing import List, Dict, Any, Optional
from serpapi import GoogleSearch
from functools import lru_cache

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SearchAgent:
    """
    Advanced Search Agent using SerpAPI for job searches and general Google queries.
    Includes filtering, retry logic with exponential backoff, and caching.
    """

    def __init__(self, api_key: str, config: Optional[Dict[str, Any]] = None):
        self.api_key = api_key
        self.config = config or {}
        self.filters = self.config.get("filters", {})
        self.retry_attempts = self.config.get("retry_attempts", 3)
        self.delay_seconds = self.config.get("delay_seconds", 2)
        self.use_cache = self.config.get("use_cache", True)
        self.language = self.config.get("language", "en")

        if not self.api_key:
            logger.warning("⚠️ SerpAPI key not provided — functionality will be limited.")

    # ------------------------------ Core Search Logic ------------------------------

    def search_jobs(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """
        Searches Google Jobs via SerpAPI and filters results based on configuration.
        Includes retry logic, error handling, and caching.
        """
        if not self.api_key:
            logger.error("❌ Missing SerpAPI key — aborting job search.")
            return []

        start_time = time.time()
        logger.info(f"🔍 Searching jobs for: '{query}' (max {num_results})")

        params = {
            "engine": "google_jobs",
            "q": query,
            "api_key": self.api_key,
            "num": num_results,
            "hl": self.language,
        }

        for attempt in range(1, self.retry_attempts + 1):
            try:
                search = GoogleSearch(params)
                results = search.get_dict()

                if "error" in results:
                    raise ValueError(results["error"])

                jobs_results = results.get("jobs_results", [])
                logger.info(f"📊 Retrieved {len(jobs_results)} raw results for query '{query}'")

                parsed_jobs = [self._parse_job(job) for job in jobs_results]
                filtered_jobs = self._filter_jobs(parsed_jobs)
                deduped_jobs = self._deduplicate_jobs(filtered_jobs)

                duration = time.time() - start_time
                logger.info(
                    f"✅ Completed job search: {len(deduped_jobs)} results after filtering "
                    f"(took {duration:.2f}s)"
                )
                return deduped_jobs

            except Exception as e:
                logger.warning(f"⚠️ Attempt {attempt}/{self.retry_attempts} failed: {e}")
                if attempt < self.retry_attempts:
                    delay = self._get_backoff_delay(attempt)
                    logger.debug(f"⏳ Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    logger.error("🚨 All retry attempts failed for job search.")
                    return []

        return []

    # ------------------------------ General Google Search ------------------------------

    @lru_cache(maxsize=128)
    def search_google_general(self, query: str, num_results: int = 3) -> List[str]:
        """
        General Google Search to find company websites, contact pages, or career portals.
        Cached to avoid redundant lookups.
        """
        if not self.api_key:
            logger.error("❌ Missing SerpAPI key — cannot perform general search.")
            return []

        logger.info(f"🌐 Performing general Google search for: '{query}'")

        params = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": num_results,
            "hl": self.language,
        }

        try:
            search = GoogleSearch(params)
            results = search.get_dict()
            organic_results = results.get("organic_results", [])
            links = [res.get("link") for res in organic_results if res.get("link")]
            logger.info(f"🔗 Found {len(links)} general links for '{query}'")
            return links
        except Exception as e:
            logger.error(f"💥 Error during general search: {e}")
            return []

    # ------------------------------ Helper Methods ------------------------------

    def _parse_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts and normalizes job fields from SerpAPI response."""
        return {
            "company": job.get("company_name", "").strip(),
            "title": job.get("title", "").strip(),
            "location": job.get("location", "").strip(),
            "description": job.get("description", "").strip(),
            "link": self._extract_link(job),
            "apply_link": self._extract_apply_link(job),
            "via": job.get("via"),
            "detected_extensions": job.get("detected_extensions", {}),
        }

    def _extract_link(self, job: Dict[str, Any]) -> Optional[str]:
        links = job.get("related_links", [])
        return links[0].get("link") if links else None

    def _extract_apply_link(self, job: Dict[str, Any]) -> Optional[str]:
        options = job.get("apply_options", [])
        return options[0].get("link") if options else None

    # ------------------------------ Job Filtering Logic ------------------------------

    def _filter_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Applies multiple configurable filters to job listings."""
        filtered = []
        for job in jobs:
            if self._is_valid_job(job):
                filtered.append(job)
        logger.info(f"🧹 Filtered {len(jobs)} → {len(filtered)} valid jobs.")
        return filtered

    def _is_valid_job(self, job: Dict[str, Any]) -> bool:
        """Applies all filtering criteria defined in the config."""
        company = job.get("company", "").lower()
        title = job.get("title", "").lower()
        location = job.get("location", "").lower()
        description = job.get("description", "").lower()

        f = self.filters

        # --- Company Exclusions ---
        for keyword in f.get("company_exclude_keywords", []):
            if keyword.lower() in company:
                logger.debug(f"🚫 Excluding company '{company}' (matched '{keyword}')")
                return False

        # --- Keyword Inclusions ---
        include_keywords = f.get("include_keywords", [])
        if include_keywords and not any(kw.lower() in title + description for kw in include_keywords):
            return False

        # --- Remote Filter ---
        if f.get("remote_only"):
            if "remote" not in location and "remote" not in title and "remote" not in description:
                return False

        # --- Location Whitelist ---
        allowed_locations = f.get("locations", [])
        if allowed_locations and not any(loc.lower() in location for loc in allowed_locations):
            return False

        # --- Seniority Exclusion ---
        seniority_exclude = f.get("exclude_seniority_levels", [])
        if any(level.lower() in title for level in seniority_exclude):
            return False

        return True

    def _deduplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Removes duplicate job postings by title + company combination."""
        seen = set()
        deduped = []
        for job in jobs:
            key = (job.get("title", "").lower(), job.get("company", "").lower())
            if key not in seen:
                deduped.append(job)
                seen.add(key)
        return deduped

    def _get_backoff_delay(self, attempt: int) -> float:
        """Exponential backoff delay with jitter."""
        base = self.delay_seconds * (2 ** (attempt - 1))
        return base + random.uniform(0, 1.0)

# ------------------------------ Example Usage ------------------------------
if __name__ == "__main__":
    config = {
        "retry_attempts": 3,
        "delay_seconds": 2,
        "filters": {
            "remote_only": True,
            "company_exclude_keywords": ["recruiter", "agency"],
            "include_keywords": ["python", "data", "ml"],
            "locations": ["usa", "canada"],
            "exclude_seniority_levels": ["intern", "junior"],
        },
    }

    agent = SearchAgent(api_key=os.getenv("SERPAPI_KEY"), config=config)
    results = agent.search_jobs("Machine Learning Engineer", num_results=20)
    print(f"Found {len(results)} refined results.")
