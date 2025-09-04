"""
RSS Feed Processing Engine

Robust RSS feed discovery, parsing, and job extraction system
with health monitoring and comprehensive error handling.
"""

import feedparser
import requests
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from urllib.parse import urlparse, urljoin
import time
from bs4 import BeautifulSoup

from utils.logger import get_logger, performance_tracker, log_context, LogContext
from utils.error_handler import (
    retry_on_failure, graceful_degradation, NetworkError, 
    DataProcessingError, get_error_handler
)


@dataclass
class JobData:
    """Standardized job data structure."""
    id: str
    title: str
    company: str
    location: str
    salary_range: Optional[str] = None
    experience_required: Optional[str] = None
    skills_mentioned: List[str] = field(default_factory=list)
    industry: Optional[str] = None
    description: str = ""
    apply_url: str = ""
    source: str = ""
    posted_date: Optional[datetime] = None
    expires_date: Optional[datetime] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Generate unique ID if not provided."""
        if not self.id:
            content = f"{self.title}{self.company}{self.location}"
            self.id = hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class FeedHealth:
    """RSS feed health monitoring data."""
    url: str
    name: str
    enabled: bool = True
    priority: int = 2
    reliability_score: int = 10
    expected_jobs_per_day: int = 5
    
    # Health metrics
    last_successful_fetch: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    average_response_time: float = 0.0
    jobs_found_today: int = 0
    last_reset_date: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def health_status(self) -> str:
        """Get health status string."""
        if not self.enabled:
            return "disabled"
        elif self.consecutive_failures >= 3:
            return "critical"
        elif self.consecutive_failures >= 1:
            return "warning"
        elif self.success_rate < 80:
            return "degraded"
        else:
            return "healthy"
    
    def reset_daily_metrics(self):
        """Reset daily metrics."""
        self.jobs_found_today = 0
        self.last_reset_date = datetime.now()


class RSSFeedProcessor:
    """
    Robust RSS feed processing system.
    
    Features:
    - Multi-feed processing with prioritization
    - Health monitoring and automatic retry
    - Job data normalization and deduplication
    - Error handling and graceful degradation
    - Performance optimization with caching
    """
    
    def __init__(self, timeout: int = 30, max_jobs_per_feed: int = 100):
        """
        Initialize RSS feed processor.
        
        Args:
            timeout: Request timeout in seconds
            max_jobs_per_feed: Maximum jobs to extract per feed
        """
        self.timeout = timeout
        self.max_jobs_per_feed = max_jobs_per_feed
        self.logger = get_logger(__name__)
        self.error_handler = get_error_handler()
        
        # Feed health tracking
        self.feed_health: Dict[str, FeedHealth] = {}
        
        # Caching
        self._feed_cache: Dict[str, Tuple[datetime, Any]] = {}
        self.cache_duration = 300  # 5 minutes
        
        # Request session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PM-Watchman/1.0 (Job Search Bot; +https://github.com/a-bhimava/pm-watchman)'
        })
    
    def register_feed(self, 
                     url: str, 
                     name: str,
                     enabled: bool = True,
                     priority: int = 2,
                     expected_jobs_per_day: int = 5) -> FeedHealth:
        """
        Register RSS feed for monitoring.
        
        Args:
            url: Feed URL
            name: Feed name identifier
            enabled: Whether feed is enabled
            priority: Feed priority (1=highest)
            expected_jobs_per_day: Expected daily job count
            
        Returns:
            FeedHealth instance
        """
        feed_health = FeedHealth(
            url=url,
            name=name,
            enabled=enabled,
            priority=priority,
            expected_jobs_per_day=expected_jobs_per_day
        )
        
        self.feed_health[name] = feed_health
        self.logger.info(f"Registered RSS feed: {name} ({url})")
        
        return feed_health
    
    @performance_tracker("rss_processor", "fetch_feed")
    @retry_on_failure(max_attempts=3, base_delay=2.0, circuit_breaker_service="rss_feeds")
    def _fetch_feed_data(self, url: str, feed_name: str, feed_config: Dict[str, Any] = None) -> Any:
        """
        Fetch RSS feed data with error handling.
        
        Args:
            url: Feed URL
            feed_name: Feed identifier for logging
            
        Returns:
            Parsed feed data
            
        Raises:
            NetworkError: If feed cannot be fetched
        """
        start_time = time.time()
        
        try:
            # Check if this is a high-frequency feed that should bypass cache
            is_high_frequency = feed_config and feed_config.get('high_frequency', False)
            
            # Check cache first (unless high frequency)
            cache_key = url
            if not is_high_frequency and cache_key in self._feed_cache:
                cached_time, cached_data = self._feed_cache[cache_key]
                if (datetime.now() - cached_time).seconds < self.cache_duration:
                    self.logger.debug(f"Using cached data for feed {feed_name}")
                    return cached_data
            elif is_high_frequency:
                self.logger.debug(f"Bypassing cache for high-frequency feed {feed_name}")
            
            # Fetch feed
            self.logger.debug(f"Fetching RSS feed: {feed_name} ({url})")
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse feed
            feed_data = feedparser.parse(response.content)
            
            # Cache the result
            self._feed_cache[cache_key] = (datetime.now(), feed_data)
            
            # Update health metrics
            response_time = time.time() - start_time
            self._update_feed_health_success(feed_name, response_time)
            
            return feed_data
            
        except requests.exceptions.RequestException as e:
            self._update_feed_health_error(feed_name, f"Request failed: {str(e)}")
            raise NetworkError(
                f"Failed to fetch RSS feed {feed_name}: {str(e)}",
                component="rss_processor",
                operation="fetch_feed"
            )
        except Exception as e:
            self._update_feed_health_error(feed_name, f"Parse error: {str(e)}")
            raise DataProcessingError(
                f"Failed to parse RSS feed {feed_name}: {str(e)}",
                component="rss_processor", 
                operation="parse_feed"
            )
    
    def _update_feed_health_success(self, feed_name: str, response_time: float):
        """Update feed health metrics after successful fetch."""
        if feed_name in self.feed_health:
            health = self.feed_health[feed_name]
            health.last_successful_fetch = datetime.now()
            health.consecutive_failures = 0
            health.total_requests += 1
            health.successful_requests += 1
            
            # Update average response time
            if health.average_response_time == 0:
                health.average_response_time = response_time
            else:
                health.average_response_time = (health.average_response_time + response_time) / 2
    
    def _update_feed_health_error(self, feed_name: str, error_message: str):
        """Update feed health metrics after error."""
        if feed_name in self.feed_health:
            health = self.feed_health[feed_name]
            health.last_error = error_message
            health.consecutive_failures += 1
            health.total_requests += 1
    
    @performance_tracker("rss_processor", "extract_jobs")
    def _extract_jobs_from_feed(self, feed_data: Any, feed_name: str) -> List[JobData]:
        """
        Extract job data from RSS feed.
        
        Args:
            feed_data: Parsed feed data
            feed_name: Feed identifier
            
        Returns:
            List of extracted job data
        """
        jobs = []
        
        if not hasattr(feed_data, 'entries') or not feed_data.entries:
            self.logger.warning(f"No entries found in feed {feed_name}")
            return jobs
        
        for entry in feed_data.entries[:self.max_jobs_per_feed]:
            try:
                job = self._parse_feed_entry(entry, feed_name)
                if job and self._is_pm_related_job(job):
                    jobs.append(job)
                    
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse entry in feed {feed_name}: {str(e)}",
                    extra={"feed_name": feed_name, "entry_title": getattr(entry, 'title', 'unknown')}
                )
                continue
        
        # Update jobs found count
        if feed_name in self.feed_health:
            self.feed_health[feed_name].jobs_found_today += len(jobs)
        
        self.logger.info(f"Extracted {len(jobs)} PM jobs from feed {feed_name}")
        return jobs
    
    def _parse_feed_entry(self, entry: Any, source: str) -> Optional[JobData]:
        """
        Parse individual RSS feed entry into JobData.
        
        Args:
            entry: Feed entry object
            source: Source feed name
            
        Returns:
            JobData instance or None if parsing fails
        """
        try:
            # Extract basic information
            title = self._clean_text(getattr(entry, 'title', ''))
            if not title:
                return None
            
            # Extract description/summary
            description = ''
            if hasattr(entry, 'description'):
                description = self._clean_html(entry.description)
            elif hasattr(entry, 'summary'):
                description = self._clean_html(entry.summary)
            elif hasattr(entry, 'content'):
                if isinstance(entry.content, list) and entry.content:
                    description = self._clean_html(entry.content[0].get('value', ''))
                else:
                    description = self._clean_html(str(entry.content))
            
            # Extract application URL
            apply_url = getattr(entry, 'link', '')
            if hasattr(entry, 'links') and entry.links:
                for link in entry.links:
                    if link.get('type') == 'text/html':
                        apply_url = link.get('href', apply_url)
                        break
            
            # Extract posting date
            posted_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                posted_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                posted_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            
            # Extract company and location from title/description
            company, location = self._extract_company_location(title, description, entry)
            
            # Extract salary information
            salary_range = self._extract_salary(description)
            
            # Extract experience requirements
            experience_required = self._extract_experience(description)
            
            # Extract skills
            skills_mentioned = self._extract_skills(description)
            
            # Detect industry
            industry = self._detect_industry(title, description, company)
            
            return JobData(
                id="",  # Will be auto-generated
                title=title,
                company=company,
                location=location,
                salary_range=salary_range,
                experience_required=experience_required,
                skills_mentioned=skills_mentioned,
                industry=industry,
                description=description,
                apply_url=apply_url,
                source=source,
                posted_date=posted_date,
                raw_data={
                    'entry_id': getattr(entry, 'id', ''),
                    'tags': getattr(entry, 'tags', []),
                    'author': getattr(entry, 'author', ''),
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing feed entry: {str(e)}", exc_info=True)
            return None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        
        # Remove HTML tags
        text = self._clean_html(text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove common prefixes/suffixes
        prefixes = ['job:', 'position:', 'role:', 'opening:']
        for prefix in prefixes:
            if text.lower().startswith(prefix):
                text = text[len(prefix):].strip()
        
        return text
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and entities."""
        if not html:
            return ""
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()
            # Decode HTML entities
            text = BeautifulSoup(text, 'html.parser').get_text()
            return text.strip()
        except Exception:
            # Fallback: simple regex removal
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text)
            return text.strip()
    
    def _extract_company_location(self, title: str, description: str, entry: Any) -> Tuple[str, str]:
        """Extract company and location information."""
        company = "Unknown Company"
        location = "Location not specified"
        
        # Try to extract from entry metadata
        if hasattr(entry, 'author') and entry.author:
            company = entry.author.strip()
        
        # Common patterns for company extraction from title
        company_patterns = [
            r'at\s+([A-Z][A-Za-z\s&,.]+?)(?:\s*[-|]|\s*$)',
            r'@\s*([A-Z][A-Za-z\s&,.]+?)(?:\s*[-|]|\s*$)',
            r'[\(]([A-Z][A-Za-z\s&,.]+?)[\)]',
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, title)
            if match:
                company = match.group(1).strip()
                break
        
        # Location patterns
        location_patterns = [
            r'\b(Remote|Work from home|WFH)\b',
            r'\b([A-Z][a-z]+,\s*[A-Z]{2})\b',  # City, State
            r'\b([A-Z][a-z]+\s*[A-Z][a-z]*,\s*[A-Z][a-z]+)\b',  # City, Country
            r'\b(San Francisco|New York|Los Angeles|Chicago|Boston|Seattle|Austin|Denver)\b',
        ]
        
        text_to_search = f"{title} {description}"
        for pattern in location_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                location = match.group(1)
                break
        
        return company, location
    
    def _extract_salary(self, description: str) -> Optional[str]:
        """Extract salary information from job description."""
        salary_patterns = [
            r'\$(\d{1,3},\d{3})\s*-\s*\$(\d{1,3},\d{3})',  # $120,000 - $150,000
            r'\$(\d{1,3})k\s*-\s*\$(\d{1,3})k',            # $120k - $150k
            r'(\d{1,3},\d{3})\s*-\s*(\d{1,3},\d{3})',      # 120,000 - 150,000
            r'(\d{1,3})k\s*-\s*(\d{1,3})k',                # 120k - 150k
            r'\$(\d{1,3},\d{3})\+',                        # $120,000+
            r'\$(\d{1,3})k\+',                             # $120k+
        ]
        
        for pattern in salary_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_experience(self, description: str) -> Optional[str]:
        """Extract experience requirements from job description."""
        experience_patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'(\d+)\+?\s*years?\s+(?:of\s+)?PM\s+experience',
            r'(\d+)\+?\s*years?\s+product\s+management',
            r'(entry.level|junior|senior|principal|staff)',
        ]
        
        for pattern in experience_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_skills(self, description: str) -> List[str]:
        """Extract mentioned skills from job description."""
        # Common PM skills to look for
        pm_skills = [
            'product strategy', 'roadmapping', 'user research', 'data analysis',
            'A/B testing', 'SQL', 'analytics', 'figma', 'jira', 'confluence',
            'agile', 'scrum', 'kanban', 'stakeholder management', 'wireframing',
            'user stories', 'market research', 'competitive analysis',
            'product metrics', 'KPIs', 'OKRs', 'go-to-market', 'pricing',
            'product launch', 'feature prioritization', 'customer interviews'
        ]
        
        found_skills = []
        description_lower = description.lower()
        
        for skill in pm_skills:
            if skill.lower() in description_lower:
                found_skills.append(skill)
        
        return found_skills
    
    def _detect_industry(self, title: str, description: str, company: str) -> Optional[str]:
        """Detect industry from job information."""
        industry_keywords = {
            'fintech': ['fintech', 'financial', 'banking', 'payments', 'crypto', 'blockchain'],
            'healthtech': ['health', 'healthcare', 'medical', 'biotech', 'pharma'],
            'edtech': ['education', 'learning', 'e-learning', 'university', 'school'],
            'saas': ['saas', 'software as a service', 'b2b', 'enterprise software'],
            'e-commerce': ['e-commerce', 'ecommerce', 'retail', 'marketplace', 'shopping'],
            'mobility': ['transportation', 'mobility', 'automotive', 'rideshare'],
            'social': ['social', 'social media', 'community', 'networking'],
            'gaming': ['gaming', 'games', 'esports', 'entertainment'],
            'climate': ['climate', 'sustainability', 'clean energy', 'green tech']
        }
        
        text_to_search = f"{title} {description} {company}".lower()
        
        for industry, keywords in industry_keywords.items():
            if any(keyword in text_to_search for keyword in keywords):
                return industry
        
        return None
    
    def _is_pm_related_job(self, job: JobData) -> bool:
        """Check if job is Product Manager related."""
        pm_indicators = [
            'product manager', 'product management', 'pm ', 'product owner',
            'product lead', 'product director', 'product strategy', 'principal product',
            'senior product', 'associate product', 'product marketing',
            'growth product', 'technical product'
        ]
        
        title_lower = job.title.lower()
        description_lower = job.description.lower()
        
        # Check for PM indicators in title (higher weight)
        title_matches = any(indicator in title_lower for indicator in pm_indicators)
        if title_matches:
            return True
        
        # Check for PM indicators in description
        description_matches = any(indicator in description_lower for indicator in pm_indicators)
        if description_matches:
            return True
        
        return False
    
    def process_feeds(self, feed_configs: Dict[str, Dict[str, Any]]) -> List[JobData]:
        """
        Process multiple RSS feeds and extract jobs.
        
        Args:
            feed_configs: Dictionary of feed configurations
            
        Returns:
            List of all extracted jobs
        """
        all_jobs = []
        
        # Register feeds if not already registered
        for feed_name, config in feed_configs.items():
            if feed_name not in self.feed_health:
                self.register_feed(
                    url=config['url'],
                    name=feed_name,
                    enabled=config.get('enabled', True),
                    priority=config.get('priority', 2),
                    expected_jobs_per_day=config.get('expected_jobs_per_day', 5)
                )
        
        # Sort feeds by priority
        enabled_feeds = [
            (name, health) for name, health in self.feed_health.items()
            if health.enabled and health.health_status != 'critical'
        ]
        enabled_feeds.sort(key=lambda x: x[1].priority)
        
        # Process each feed
        for feed_name, health in enabled_feeds:
            try:
                context = log_context("rss_processor", "process_feed", source=feed_name)
                self.logger.info(f"Processing RSS feed: {feed_name}", extra={"context": context})
                
                # Fetch and parse feed
                feed_data = self._fetch_feed_data(health.url, feed_name, feed_configs.get(feed_name, {}))
                
                # Extract jobs
                jobs = self._extract_jobs_from_feed(feed_data, feed_name)
                all_jobs.extend(jobs)
                
                self.logger.info(
                    f"Successfully processed feed {feed_name}: {len(jobs)} jobs found",
                    extra={"context": context}
                )
                
            except Exception as e:
                self.logger.error(
                    f"Failed to process feed {feed_name}: {str(e)}",
                    extra={"context": log_context("rss_processor", "process_feed", source=feed_name)},
                    exc_info=True
                )
                continue
        
        self.logger.info(f"Total jobs extracted from {len(enabled_feeds)} feeds: {len(all_jobs)}")
        return all_jobs
    
    def get_feed_health_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive feed health summary.
        
        Returns:
            Feed health summary information
        """
        total_feeds = len(self.feed_health)
        enabled_feeds = len([h for h in self.feed_health.values() if h.enabled])
        healthy_feeds = len([h for h in self.feed_health.values() if h.health_status == 'healthy'])
        
        feed_details = {}
        for name, health in self.feed_health.items():
            feed_details[name] = {
                'status': health.health_status,
                'enabled': health.enabled,
                'success_rate': round(health.success_rate, 2),
                'consecutive_failures': health.consecutive_failures,
                'jobs_found_today': health.jobs_found_today,
                'expected_daily': health.expected_jobs_per_day,
                'last_successful_fetch': health.last_successful_fetch.isoformat() if health.last_successful_fetch else None,
                'last_error': health.last_error,
                'average_response_time': round(health.average_response_time, 2)
            }
        
        return {
            'total_feeds': total_feeds,
            'enabled_feeds': enabled_feeds,
            'healthy_feeds': healthy_feeds,
            'overall_health': 'healthy' if healthy_feeds / max(enabled_feeds, 1) > 0.8 else 'degraded',
            'feeds': feed_details
        }