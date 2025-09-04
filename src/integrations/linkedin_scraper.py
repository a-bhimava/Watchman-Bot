"""
LinkedIn Job Search URL Scraper

Robust LinkedIn job discovery system using search URLs instead of 
company career pages for broader PM job coverage with anti-detection measures.
"""

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup

import time
import random
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlencode, parse_qs
import re
import hashlib

from utils.logger import get_logger, performance_tracker, log_context
from utils.error_handler import retry_on_failure, NetworkError, DataProcessingError
from integrations.rss_processor import JobData


@dataclass
class LinkedInSearchConfig:
    """Configuration for LinkedIn job searches."""
    keywords: List[str]
    location: str
    experience_levels: List[str]  # ["entry", "associate", "mid", "senior", "director", "executive"]
    date_posted: str  # ["24hr", "week", "month"]
    remote_options: List[str]  # ["remote", "hybrid", "onsite"]
    company_sizes: List[str]  # ["startup", "small", "medium", "large", "enterprise"]
    max_results_per_search: int = 100
    search_delay_range: Tuple[int, int] = (8, 15)  # seconds - more conservative


@dataclass
class LinkedInJobResult:
    """Individual LinkedIn job result."""
    job_id: str
    title: str
    company: str
    location: str
    posted_date: str
    job_url: str
    description_preview: str
    seniority_level: Optional[str] = None
    employment_type: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    scraped_at: datetime = None
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now()


class LinkedInScraper:
    """
    Robust LinkedIn job scraper using search URLs.
    
    Features:
    - Anti-detection measures (rotating user agents, delays, etc.)
    - Multiple search strategies for comprehensive coverage
    - Robust error handling and retry mechanisms
    - Data enrichment from job detail pages
    """
    
    def __init__(self, config: LinkedInSearchConfig):
        """Initialize LinkedIn scraper."""
        self.config = config
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        self.driver = None
        
        # Anti-detection measures
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        ]
        
        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0
        self.session_start_time = datetime.now()
        
        self._setup_session()
    
    def _setup_session(self):
        """Configure requests session with anti-detection measures."""
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        })
    
    def _get_random_user_agent(self) -> str:
        """Get random user agent for anti-detection."""
        return random.choice(self.user_agents)
    
    def _apply_rate_limiting(self):
        """Apply intelligent rate limiting."""
        current_time = time.time()
        
        # Base delay
        min_delay, max_delay = self.config.search_delay_range
        delay = random.uniform(min_delay, max_delay)
        
        # Increase delay if making many requests
        if self.request_count > 10:
            delay *= 1.5
        if self.request_count > 20:
            delay *= 2.0
        
        # Ensure minimum time between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < delay:
            sleep_time = delay - time_since_last
            self.logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def _setup_selenium_driver(self) -> webdriver.Chrome:
        """Setup Selenium WebDriver with anti-detection options."""
        if self.driver is not None:
            return self.driver
        
        chrome_options = Options()
        
        # Anti-detection options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(f"--user-agent={self._get_random_user_agent()}")
        
        # Performance options
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-javascript")  # Most LinkedIn content loads without JS
        chrome_options.add_argument("--disable-plugins")
        
        # Headless mode for production
        chrome_options.add_argument("--headless")
        
        try:
            # Try to use webdriver-manager if available, otherwise use system Chrome
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
            except ImportError:
                # Fallback to system Chrome
                service = Service()
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info("Selenium WebDriver initialized successfully")
            return self.driver
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Selenium WebDriver: {e}")
            raise NetworkError(f"WebDriver initialization failed: {e}")
    
    def _build_search_url(self, 
                         keywords: str, 
                         location: str = "", 
                         experience: str = "",
                         date_posted: str = "",
                         remote: bool = False) -> str:
        """Build LinkedIn job search URL."""
        
        base_url = "https://www.linkedin.com/jobs/search/"
        
        params = {
            'keywords': keywords,
            'location': location or self.config.location,
            'trk': 'public_jobs_jobs-search-bar_search-submit',
            'position': '1',
            'pageNum': '0'
        }
        
        # Add experience level filter
        if experience:
            experience_map = {
                'entry': '1',      # Internship
                'associate': '2',   # Entry level  
                'mid': '3',        # Associate
                'senior': '4',     # Mid-Senior level
                'director': '5',   # Director
                'executive': '6'   # Executive
            }
            if experience in experience_map:
                params['f_E'] = experience_map[experience]
        
        # Add date posted filter
        if date_posted:
            date_map = {
                '24hr': 'r86400',
                'week': 'r604800', 
                'month': 'r2592000'
            }
            if date_posted in date_map:
                params['f_TPR'] = date_map[date_posted]
        
        # Add remote work filter
        if remote:
            params['f_WT'] = '2'  # Remote
        
        url = base_url + '?' + urlencode(params)
        self.logger.debug(f"Built search URL: {url}")
        return url
    
    def _generate_search_combinations(self) -> List[Dict[str, str]]:
        """Generate comprehensive search combinations for broad coverage."""
        combinations = []
        
        # Core PM keywords with variations
        pm_keywords = [
            "Product Manager",
            "Senior Product Manager", 
            "Principal Product Manager",
            "Product Lead",
            "PM",
            "Product Owner",
            "Product Management",
            "Staff Product Manager"
        ]
        
        # Industry-specific keywords
        industry_keywords = [
            "Product Manager fintech",
            "Product Manager SaaS", 
            "Product Manager healthcare",
            "Product Manager B2B",
            "Technical Product Manager",
            "Growth Product Manager",
            "Data Product Manager"
        ]
        
        all_keywords = pm_keywords + industry_keywords
        
        for keyword in all_keywords:
            # Base search
            combinations.append({
                'keywords': keyword,
                'location': self.config.location,
                'experience': '',
                'date_posted': self.config.date_posted,
                'remote': False
            })
            
            # Remote variation if relevant
            if any(remote in self.config.remote_options for remote in ['remote', 'hybrid']):
                combinations.append({
                    'keywords': keyword,
                    'location': 'Remote',
                    'experience': '',
                    'date_posted': self.config.date_posted,
                    'remote': True
                })
            
            # Experience level variations for key keywords
            if keyword in pm_keywords[:4]:  # Main PM titles
                for exp_level in self.config.experience_levels:
                    combinations.append({
                        'keywords': keyword,
                        'location': self.config.location,
                        'experience': exp_level,
                        'date_posted': self.config.date_posted,
                        'remote': False
                    })
        
        self.logger.info(f"Generated {len(combinations)} search combinations")
        return combinations[:20]  # Limit to prevent excessive requests
    
    @retry_on_failure(max_attempts=3, base_delay=5)
    def _scrape_search_results(self, search_url: str) -> List[LinkedInJobResult]:
        """Scrape job results from LinkedIn search page."""
        self._apply_rate_limiting()
        
        try:
            # Use requests first for faster scraping
            self.session.headers['User-Agent'] = self._get_random_user_agent()
            
            response = self.session.get(search_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = self._parse_job_listings(soup, search_url)
            
            self.logger.info(f"Scraped {len(jobs)} jobs from search", 
                           extra={"search_url": search_url, "job_count": len(jobs)})
            
            return jobs
                
        except requests.RequestException as e:
            self.logger.warning(f"Requests method failed, trying Selenium: {e}")
            
            # Fallback to Selenium for JavaScript-heavy pages
            return self._scrape_with_selenium(search_url)
    
    def _scrape_with_selenium(self, search_url: str) -> List[LinkedInJobResult]:
        """Fallback scraping method using Selenium."""
        driver = self._setup_selenium_driver()
        
        try:
            driver.get(search_url)
            
            # Wait for job listings to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-job-id]"))
            )
            
            # Scroll to load more results
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            
            while scroll_attempts < 3:  # Limit scrolling
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                new_height = driver.execute_script("return document.body.scrollHeight") 
                if new_height == last_height:
                    break
                    
                last_height = new_height
                scroll_attempts += 1
            
            # Parse results
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            jobs = self._parse_job_listings(soup, search_url)
            
            self.logger.info(f"Selenium scraped {len(jobs)} jobs from search")
            return jobs
            
        except (TimeoutException, WebDriverException) as e:
            self.logger.error(f"Selenium scraping failed: {e}")
            raise NetworkError(f"Failed to scrape with Selenium: {e}")
    
    def _parse_job_listings(self, soup: BeautifulSoup, search_url: str) -> List[LinkedInJobResult]:
        """Parse job listings from LinkedIn search results."""
        jobs = []
        
        # LinkedIn job listing selectors (these may need updating)
        job_selectors = [
            '[data-job-id]',  # Main job listing selector
            '.job-search-card',
            '.jobs-search__results .result-card',
            '.jobs-search-results__list .result-card'
        ]
        
        job_elements = []
        for selector in job_selectors:
            job_elements = soup.select(selector)
            if job_elements:
                break
        
        if not job_elements:
            self.logger.warning("No job elements found with any selector", 
                              extra={"search_url": search_url})
            return jobs
        
        for element in job_elements[:self.config.max_results_per_search]:
            try:
                job = self._extract_job_data(element)
                if job:
                    jobs.append(job)
            except Exception as e:
                self.logger.warning(f"Failed to parse job element: {e}")
                continue
        
        return jobs
    
    def _extract_job_data(self, element) -> Optional[LinkedInJobResult]:
        """Extract job data from individual listing element."""
        try:
            # Extract basic job information
            job_id = element.get('data-job-id', '') or self._generate_job_id(element)
            
            # Title and company
            title_elem = element.select_one('h3 a, .job-title a, [data-job-title]')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            company_elem = element.select_one('.company-name, [data-company-name], h4 a')
            company = company_elem.get_text(strip=True) if company_elem else ""
            
            # Location
            location_elem = element.select_one('.job-location, [data-job-location]')
            location = location_elem.get_text(strip=True) if location_elem else ""
            
            # Posted date
            date_elem = element.select_one('.job-posted-date, [data-posted-date]')
            posted_date = date_elem.get_text(strip=True) if date_elem else ""
            
            # Job URL
            url_elem = element.select_one('h3 a, .job-title a')
            job_url = url_elem.get('href', '') if url_elem else ""
            if job_url and not job_url.startswith('http'):
                job_url = f"https://www.linkedin.com{job_url}"
            
            # Description preview
            desc_elem = element.select_one('.job-summary, .job-description-text')
            description_preview = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Skip if missing critical data
            if not title or not company:
                return None
            
            return LinkedInJobResult(
                job_id=job_id,
                title=title,
                company=company, 
                location=location,
                posted_date=posted_date,
                job_url=job_url,
                description_preview=description_preview
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to extract job data: {e}")
            return None
    
    def _generate_job_id(self, element) -> str:
        """Generate unique job ID from element content."""
        content = str(element)[:500]  # First 500 chars
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    @performance_tracker("linkedin_scraper", "enrich_job_data")
    def _enrich_job_data(self, job: LinkedInJobResult) -> LinkedInJobResult:
        """Enrich job data by scraping individual job page."""
        if not job.job_url:
            return job
        
        try:
            self._apply_rate_limiting()
            
            self.session.headers['User-Agent'] = self._get_random_user_agent()
            response = self.session.get(job.job_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract additional details
            # Seniority level
            seniority_elem = soup.select_one('[data-job-criterion="seniority"]')
            if seniority_elem:
                job.seniority_level = seniority_elem.get_text(strip=True)
            
            # Employment type
            employment_elem = soup.select_one('[data-job-criterion="employment-type"]')
            if employment_elem:
                job.employment_type = employment_elem.get_text(strip=True)
            
            # Industry  
            industry_elem = soup.select_one('[data-job-criterion="industries"]')
            if industry_elem:
                job.industry = industry_elem.get_text(strip=True)
            
            # Company size
            company_elem = soup.select_one('[data-job-criterion="company-size"]')
            if company_elem:
                job.company_size = company_elem.get_text(strip=True)
            
            self.logger.debug(f"Enriched job data for {job.job_id}")
            
        except Exception as e:
            self.logger.warning(f"Failed to enrich job data for {job.job_id}: {e}")
        
        return job
    
    def convert_to_job_data(self, linkedin_job: LinkedInJobResult) -> JobData:
        """Convert LinkedIn job result to standardized JobData format."""
        return JobData(
            id=f"linkedin_{linkedin_job.job_id}",
            title=linkedin_job.title,
            company=linkedin_job.company,
            location=linkedin_job.location,
            posted_date=linkedin_job.posted_date,
            url=linkedin_job.job_url,
            description=linkedin_job.description_preview,
            source="linkedin",
            scraped_at=linkedin_job.scraped_at,
            
            # Additional LinkedIn-specific fields
            seniority_level=linkedin_job.seniority_level,
            employment_type=linkedin_job.employment_type,
            industry=linkedin_job.industry,
            company_size=linkedin_job.company_size
        )
    
    @performance_tracker("linkedin_scraper", "discover_jobs")
    def discover_jobs(self, enrich_data: bool = True) -> List[JobData]:
        """
        Main method to discover PM jobs from LinkedIn.
        
        Args:
            enrich_data: Whether to enrich jobs with additional details
            
        Returns:
            List of standardized JobData objects
        """
        try:
            self.logger.info("Starting LinkedIn job discovery")
            
            all_jobs = []
            search_combinations = self._generate_search_combinations()
            
            for i, search_config in enumerate(search_combinations):
                try:
                    search_url = self._build_search_url(**search_config)
                    
                    self.logger.info(f"Scraping search {i+1}/{len(search_combinations)}: {search_config['keywords']}")
                    
                    jobs = self._scrape_search_results(search_url)
                    
                    # Enrich job data if requested
                    if enrich_data and jobs:
                        enriched_jobs = []
                        for job in jobs[:10]:  # Limit enrichment to prevent overload
                            enriched_job = self._enrich_job_data(job)
                            enriched_jobs.append(enriched_job)
                        jobs = enriched_jobs
                    
                    # Convert to standard format
                    for linkedin_job in jobs:
                        job_data = self.convert_to_job_data(linkedin_job)
                        all_jobs.append(job_data)
                    
                    # Longer delay between searches
                    if i < len(search_combinations) - 1:
                        delay = random.uniform(10, 20)  # 10-20 seconds between searches
                        self.logger.debug(f"Waiting {delay:.1f}s before next search")
                        time.sleep(delay)
                        
                except Exception as e:
                    self.logger.error(f"Search failed for {search_config}: {e}")
                    continue
            
            self.logger.info(f"LinkedIn discovery completed: {len(all_jobs)} jobs found")
            return all_jobs
            
        except Exception as e:
            self.logger.error(f"LinkedIn discovery failed: {e}")
            return []
    
    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.warning(f"Error closing WebDriver: {e}")
        
        if self.session:
            self.session.close()


def create_pm_search_config(
    location: str = "Remote", 
    experience_levels: List[str] = None,
    date_posted: str = "24hr"
) -> LinkedInSearchConfig:
    """Create a LinkedIn search configuration optimized for PM jobs."""
    
    if experience_levels is None:
        experience_levels = ["associate", "mid", "senior"]
    
    return LinkedInSearchConfig(
        keywords=[
            "Product Manager",
            "Senior Product Manager", 
            "Principal Product Manager",
            "Staff Product Manager",
            "Product Lead"
        ],
        location=location,
        experience_levels=experience_levels,
        date_posted=date_posted,
        remote_options=["remote", "hybrid"],
        company_sizes=["medium", "large"],
        max_results_per_search=50,
        search_delay_range=(5, 12)  # Conservative delays
    )