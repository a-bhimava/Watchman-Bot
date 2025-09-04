"""
Job Data Enrichment and Normalization Pipeline

Advanced job data processing to extract maximum value from scraped data,
including text analysis, company information enrichment, and data standardization.
"""

import re
import json
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import requests
from difflib import SequenceMatcher
import hashlib

from integrations.rss_processor import JobData
from utils.logger import get_logger, performance_tracker, log_context
from utils.error_handler import retry_on_failure, DataProcessingError


@dataclass
class EnrichmentConfig:
    """Configuration for job enrichment pipeline."""
    enable_salary_extraction: bool = True
    enable_skills_extraction: bool = True
    enable_company_enrichment: bool = True
    enable_location_normalization: bool = True
    enable_seniority_detection: bool = True
    enable_remote_detection: bool = True
    max_description_length: int = 5000
    company_info_cache_hours: int = 24


@dataclass
class ExtractedSalary:
    """Extracted salary information."""
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    currency: str = "USD"
    frequency: str = "annual"  # annual, monthly, hourly
    equity_mentioned: bool = False
    benefits_mentioned: bool = False


@dataclass
class ExtractedSkills:
    """Extracted skills and technologies."""
    pm_skills: List[str] = field(default_factory=list)
    technical_skills: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    methodologies: List[str] = field(default_factory=list)
    industries: List[str] = field(default_factory=list)


@dataclass
class CompanyInfo:
    """Enriched company information."""
    name: str
    size: Optional[str] = None
    industry: Optional[str] = None
    stage: Optional[str] = None  # startup, growth, public
    valuation: Optional[str] = None
    founded_year: Optional[int] = None
    location: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None


@dataclass
class EnrichedJobData:
    """Job data with enrichment results."""
    original_job: JobData
    extracted_salary: Optional[ExtractedSalary] = None
    extracted_skills: Optional[ExtractedSkills] = None
    company_info: Optional[CompanyInfo] = None
    normalized_location: Optional[str] = None
    seniority_level: Optional[str] = None
    remote_work_type: Optional[str] = None  # remote, hybrid, onsite
    job_type: Optional[str] = None  # full-time, part-time, contract
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    quality_score: float = 0.0  # 0-100 score based on data completeness
    enriched_at: datetime = field(default_factory=datetime.now)


class SalaryExtractor:
    """Extract salary information from job descriptions."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Salary pattern regex
        self.salary_patterns = [
            # $100,000 - $150,000
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:-|to)\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            # $100K - $150K
            r'\$(\d{1,3})K\s*(?:-|to)\s*\$?(\d{1,3})K',
            # 100000 - 150000
            r'(?:salary|pay|compensation).*?(\d{1,3}(?:,\d{3})*)\s*(?:-|to)\s*(\d{1,3}(?:,\d{3})*)',
            # $100,000+
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\+',
            # Up to $150,000
            r'up to.*?\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        self.equity_patterns = [
            r'equity', r'stock options', r'rsu', r'restricted stock',
            r'employee stock', r'ownership', r'shares'
        ]
        
        self.benefits_patterns = [
            r'health insurance', r'dental', r'vision', r'401k', r'retirement',
            r'pto', r'vacation', r'benefits package', r'medical coverage'
        ]
    
    def extract_salary(self, text: str) -> ExtractedSalary:
        """Extract salary information from text."""
        salary = ExtractedSalary()
        text_lower = text.lower()
        
        # Try each salary pattern
        for pattern in self.salary_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                try:
                    if isinstance(match, tuple) and len(match) == 2:
                        # Range pattern
                        min_val = self._parse_salary_value(match[0])
                        max_val = self._parse_salary_value(match[1])
                        if min_val and max_val:
                            salary.min_salary = min_val
                            salary.max_salary = max_val
                            break
                    else:
                        # Single value
                        val = self._parse_salary_value(match)
                        if val:
                            salary.min_salary = val
                            break
                except ValueError:
                    continue
        
        # Check for equity mentions
        for pattern in self.equity_patterns:
            if re.search(pattern, text_lower):
                salary.equity_mentioned = True
                break
        
        # Check for benefits mentions
        for pattern in self.benefits_patterns:
            if re.search(pattern, text_lower):
                salary.benefits_mentioned = True
                break
        
        # Detect frequency
        if re.search(r'per hour|hourly|/hr', text_lower):
            salary.frequency = 'hourly'
        elif re.search(r'per month|monthly|/month', text_lower):
            salary.frequency = 'monthly'
        
        return salary
    
    def _parse_salary_value(self, value_str: str) -> Optional[int]:
        """Parse salary value from string."""
        try:
            # Remove commas and convert
            clean_value = re.sub(r'[,$]', '', str(value_str))
            
            # Handle K suffix
            if clean_value.endswith('k') or clean_value.endswith('K'):
                return int(float(clean_value[:-1]) * 1000)
            
            return int(float(clean_value))
        except (ValueError, TypeError):
            return None


class SkillsExtractor:
    """Extract skills and technologies from job descriptions."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # PM skills dictionary
        self.pm_skills = {
            'core': [
                'product strategy', 'product roadmap', 'roadmapping', 'user research',
                'market research', 'competitive analysis', 'product metrics',
                'data analysis', 'a/b testing', 'user testing', 'product launch',
                'go-to-market', 'gtm', 'stakeholder management', 'cross-functional',
                'agile', 'scrum', 'kanban', 'product vision', 'product planning',
                'user experience', 'ux', 'customer development', 'mvp',
                'minimum viable product', 'product-market fit', 'kpis',
                'product analytics', 'customer interviews', 'personas',
                'user stories', 'backlog management', 'prioritization',
                'requirements gathering', 'wireframing', 'prototyping'
            ],
            'technical': [
                'sql', 'python', 'r', 'tableau', 'looker', 'mixpanel', 'amplitude',
                'google analytics', 'segment', 'hubspot', 'salesforce', 'jira',
                'confluence', 'slack', 'notion', 'figma', 'sketch', 'miro',
                'productboard', 'aha', 'monday', 'asana', 'trello'
            ],
            'methodologies': [
                'design thinking', 'lean startup', 'jobs-to-be-done', 'jtbd',
                'okrs', 'objectives and key results', 'sprint planning',
                'retrospectives', 'daily standups', 'continuous improvement',
                'six sigma', 'hypothesis-driven development'
            ],
            'industries': [
                'saas', 'b2b', 'b2c', 'fintech', 'healthtech', 'edtech',
                'e-commerce', 'marketplace', 'platform', 'api', 'mobile',
                'web', 'enterprise', 'consumer', 'social', 'gaming',
                'blockchain', 'ai', 'machine learning', 'iot', 'cloud'
            ]
        }
    
    def extract_skills(self, text: str) -> ExtractedSkills:
        """Extract skills from job description text."""
        skills = ExtractedSkills()
        text_lower = text.lower()
        
        # Extract each category
        skills.pm_skills = self._extract_category(text_lower, self.pm_skills['core'])
        skills.technical_skills = self._extract_category(text_lower, self.pm_skills['technical'])
        skills.methodologies = self._extract_category(text_lower, self.pm_skills['methodologies'])
        skills.industries = self._extract_category(text_lower, self.pm_skills['industries'])
        
        # Extract tools (broader search)
        tools_patterns = [
            r'experience with (\w+)', r'proficient in (\w+)', r'knowledge of (\w+)',
            r'familiar with (\w+)', r'using (\w+)', r'expertise in (\w+)'
        ]
        
        for pattern in tools_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if len(match) > 2 and match not in skills.tools:
                    skills.tools.append(match)
        
        return skills
    
    def _extract_category(self, text: str, skill_list: List[str]) -> List[str]:
        """Extract skills from a specific category."""
        found_skills = []
        
        for skill in skill_list:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(skill.lower()) + r'\b'
            if re.search(pattern, text):
                found_skills.append(skill)
        
        return found_skills


class CompanyEnricher:
    """Enrich company information using various data sources."""
    
    def __init__(self, config: EnrichmentConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.cache = {}  # Simple in-memory cache
        
        # Company size indicators
        self.size_indicators = {
            'startup': ['startup', 'early stage', 'seed', 'series a'],
            'small': ['small company', '1-10', '11-50', 'boutique'],
            'medium': ['51-200', '201-500', 'mid-size', 'growing company'],
            'large': ['501-1000', '1001-5000', 'large company', 'established'],
            'enterprise': ['5000+', '10000+', 'enterprise', 'fortune 500', 'public company']
        }
        
        # Industry keywords
        self.industry_keywords = {
            'fintech': ['fintech', 'financial', 'banking', 'payments', 'lending', 'investment'],
            'healthtech': ['healthcare', 'health', 'medical', 'biotech', 'pharmaceutical'],
            'edtech': ['education', 'learning', 'educational', 'university', 'school'],
            'saas': ['saas', 'software as a service', 'cloud software', 'b2b software'],
            'e-commerce': ['e-commerce', 'ecommerce', 'retail', 'marketplace', 'shopping'],
            'technology': ['technology', 'tech', 'software', 'digital', 'internet']
        }
    
    @retry_on_failure(max_attempts=2, base_delay=1)
    def enrich_company(self, company_name: str, job_description: str = "") -> CompanyInfo:
        """Enrich company information."""
        cache_key = company_name.lower().strip()
        
        # Check cache first
        if cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if datetime.now() - cache_entry['timestamp'] < timedelta(hours=self.config.company_info_cache_hours):
                return cache_entry['data']
        
        company_info = CompanyInfo(name=company_name)
        
        # Extract information from job description
        if job_description:
            company_info = self._extract_from_description(company_info, job_description)
        
        # Try to enrich from external sources (placeholder for future implementation)
        # This could include APIs like Clearbit, LinkedIn Company API, etc.
        
        # Cache the result
        self.cache[cache_key] = {
            'data': company_info,
            'timestamp': datetime.now()
        }
        
        return company_info
    
    def _extract_from_description(self, company_info: CompanyInfo, description: str) -> CompanyInfo:
        """Extract company information from job description."""
        text_lower = description.lower()
        
        # Detect company size
        for size, indicators in self.size_indicators.items():
            for indicator in indicators:
                if indicator in text_lower:
                    company_info.size = size
                    break
            if company_info.size:
                break
        
        # Detect industry
        for industry, keywords in self.industry_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    company_info.industry = industry
                    break
            if company_info.industry:
                break
        
        # Extract company stage indicators
        if any(word in text_lower for word in ['startup', 'early stage', 'seed funding']):
            company_info.stage = 'startup'
        elif any(word in text_lower for word in ['series b', 'series c', 'growth stage']):
            company_info.stage = 'growth'
        elif any(word in text_lower for word in ['public company', 'publicly traded', 'nasdaq', 'nyse']):
            company_info.stage = 'public'
        
        # Extract founded year
        year_match = re.search(r'founded in (\d{4})|established (\d{4})|since (\d{4})', text_lower)
        if year_match:
            year = year_match.group(1) or year_match.group(2) or year_match.group(3)
            try:
                company_info.founded_year = int(year)
            except ValueError:
                pass
        
        return company_info


class LocationNormalizer:
    """Normalize job locations to standardized formats."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Location mappings
        self.city_mappings = {
            'sf': 'San Francisco, CA',
            'san francisco': 'San Francisco, CA',
            'new york': 'New York, NY',
            'nyc': 'New York, NY',
            'los angeles': 'Los Angeles, CA',
            'la': 'Los Angeles, CA',
            'boston': 'Boston, MA',
            'seattle': 'Seattle, WA',
            'austin': 'Austin, TX',
            'chicago': 'Chicago, IL',
            'denver': 'Denver, CO',
            'atlanta': 'Atlanta, GA',
            'miami': 'Miami, FL'
        }
        
        self.remote_indicators = [
            'remote', 'work from home', 'distributed', 'anywhere',
            'fully remote', 'remote-first', 'remote work'
        ]
    
    def normalize_location(self, location: str) -> Tuple[str, str]:
        """
        Normalize location and detect remote work type.
        
        Returns:
            Tuple of (normalized_location, remote_work_type)
        """
        if not location:
            return "", "unknown"
        
        location_lower = location.lower().strip()
        
        # Check for remote indicators
        for indicator in self.remote_indicators:
            if indicator in location_lower:
                return "Remote", "remote"
        
        # Check for hybrid indicators
        if any(word in location_lower for word in ['hybrid', 'flexible', 'mix of']):
            return location, "hybrid"
        
        # Normalize city names
        for key, normalized in self.city_mappings.items():
            if key in location_lower:
                return normalized, "onsite"
        
        # Return as-is if no normalization available
        return location, "onsite"


class JobEnricher:
    """Main job enrichment pipeline orchestrator."""
    
    def __init__(self, config: EnrichmentConfig = None):
        """Initialize job enricher."""
        self.config = config or EnrichmentConfig()
        self.logger = get_logger(__name__)
        
        # Initialize extractors
        self.salary_extractor = SalaryExtractor()
        self.skills_extractor = SkillsExtractor()
        self.company_enricher = CompanyEnricher(self.config)
        self.location_normalizer = LocationNormalizer()
    
    @performance_tracker("job_enricher", "enrich_job")
    def enrich_job(self, job: JobData) -> EnrichedJobData:
        """
        Enrich a single job with extracted information.
        
        Args:
            job: Original job data
            
        Returns:
            EnrichedJobData with extracted information
        """
        enriched = EnrichedJobData(original_job=job)
        
        # Get job text for analysis
        job_text = self._get_job_text(job)
        
        try:
            with log_context(operation="job_enrichment", job_id=job.id):
                # Extract salary information
                if self.config.enable_salary_extraction and job_text:
                    enriched.extracted_salary = self.salary_extractor.extract_salary(job_text)
                
                # Extract skills
                if self.config.enable_skills_extraction and job_text:
                    enriched.extracted_skills = self.skills_extractor.extract_skills(job_text)
                
                # Enrich company information
                if self.config.enable_company_enrichment and job.company:
                    enriched.company_info = self.company_enricher.enrich_company(
                        job.company, job_text
                    )
                
                # Normalize location
                if self.config.enable_location_normalization and job.location:
                    normalized_loc, remote_type = self.location_normalizer.normalize_location(job.location)
                    enriched.normalized_location = normalized_loc
                    enriched.remote_work_type = remote_type
                
                # Detect seniority level
                if self.config.enable_seniority_detection:
                    enriched.seniority_level = self._detect_seniority(job.title, job_text)
                
                # Detect job type and requirements
                enriched.job_type = self._detect_job_type(job_text)
                enriched.experience_required = self._extract_experience_requirement(job_text)
                enriched.education_required = self._extract_education_requirement(job_text)
                
                # Calculate quality score
                enriched.quality_score = self._calculate_quality_score(enriched)
                
                self.logger.debug(f"Enriched job {job.id} with quality score {enriched.quality_score}")
        
        except Exception as e:
            self.logger.error(f"Job enrichment failed for {job.id}: {e}")
            # Return partial enrichment
        
        return enriched
    
    def _get_job_text(self, job: JobData) -> str:
        """Get combined text from job for analysis."""
        text_parts = [job.title]
        
        if job.company:
            text_parts.append(job.company)
        
        if hasattr(job, 'description') and job.description:
            # Truncate description if too long
            description = job.description
            if len(description) > self.config.max_description_length:
                description = description[:self.config.max_description_length]
            text_parts.append(description)
        
        return " ".join(text_parts)
    
    def _detect_seniority(self, title: str, job_text: str) -> Optional[str]:
        """Detect job seniority level."""
        title_lower = title.lower()
        text_lower = job_text.lower()
        
        # Senior level indicators
        if any(word in title_lower for word in ['senior', 'sr', 'principal', 'staff', 'lead']):
            return 'senior'
        
        # Junior/entry level indicators  
        if any(word in title_lower for word in ['junior', 'jr', 'associate', 'entry', 'new grad']):
            return 'junior'
        
        # Director+ level
        if any(word in title_lower for word in ['director', 'vp', 'vice president', 'head of']):
            return 'executive'
        
        # Check experience requirements
        exp_matches = re.findall(r'(\d+)\+?\s*years?\s*(?:of\s*)?experience', text_lower)
        if exp_matches:
            years = int(exp_matches[0])
            if years >= 7:
                return 'senior'
            elif years >= 3:
                return 'mid'
            else:
                return 'junior'
        
        return 'mid'  # Default
    
    def _detect_job_type(self, job_text: str) -> Optional[str]:
        """Detect job type (full-time, part-time, contract)."""
        text_lower = job_text.lower()
        
        if any(word in text_lower for word in ['contract', 'contractor', 'freelance', 'consultant']):
            return 'contract'
        elif any(word in text_lower for word in ['part-time', 'part time', 'temporary']):
            return 'part-time'
        elif any(word in text_lower for word in ['full-time', 'full time', 'permanent']):
            return 'full-time'
        
        return 'full-time'  # Default assumption
    
    def _extract_experience_requirement(self, job_text: str) -> Optional[str]:
        """Extract experience requirements."""
        # Look for experience patterns
        exp_patterns = [
            r'(\d+)\+?\s*(?:-\s*\d+)?\s*years?\s*(?:of\s*)?experience',
            r'minimum\s*(?:of\s*)?(\d+)\s*years?',
            r'at least\s*(\d+)\s*years?',
            r'(\d+)\s*to\s*(\d+)\s*years?'
        ]
        
        for pattern in exp_patterns:
            match = re.search(pattern, job_text.lower())
            if match:
                return match.group(0)
        
        return None
    
    def _extract_education_requirement(self, job_text: str) -> Optional[str]:
        """Extract education requirements."""
        text_lower = job_text.lower()
        
        if any(word in text_lower for word in ['phd', 'doctorate', 'doctoral']):
            return 'PhD'
        elif any(word in text_lower for word in ['master', 'mba', 'ms', 'ma']):
            return 'Masters'
        elif any(word in text_lower for word in ['bachelor', 'ba', 'bs', 'degree']):
            return 'Bachelors'
        
        return None
    
    def _calculate_quality_score(self, enriched: EnrichedJobData) -> float:
        """Calculate data quality score (0-100)."""
        score = 0.0
        max_score = 100.0
        
        # Base job data quality (40 points)
        if enriched.original_job.title:
            score += 10
        if enriched.original_job.company:
            score += 10
        if enriched.original_job.location:
            score += 10
        if hasattr(enriched.original_job, 'description') and enriched.original_job.description:
            score += 10
        
        # Enrichment completeness (60 points)
        if enriched.extracted_salary and (enriched.extracted_salary.min_salary or enriched.extracted_salary.max_salary):
            score += 15
        
        if enriched.extracted_skills:
            if enriched.extracted_skills.pm_skills:
                score += 10
            if enriched.extracted_skills.technical_skills:
                score += 10
        
        if enriched.company_info:
            if enriched.company_info.industry:
                score += 10
            if enriched.company_info.size:
                score += 5
        
        if enriched.seniority_level:
            score += 5
        
        if enriched.remote_work_type and enriched.remote_work_type != "unknown":
            score += 5
        
        return min(score, max_score)
    
    @performance_tracker("job_enricher", "enrich_jobs_batch")
    def enrich_jobs(self, jobs: List[JobData]) -> List[EnrichedJobData]:
        """
        Enrich multiple jobs in batch.
        
        Args:
            jobs: List of jobs to enrich
            
        Returns:
            List of enriched job data
        """
        enriched_jobs = []
        
        with log_context("job_enricher", operation="batch_job_enrichment", job_count=len(jobs)):
            for i, job in enumerate(jobs):
                try:
                    enriched = self.enrich_job(job)
                    enriched_jobs.append(enriched)
                    
                    if i % 10 == 0:
                        self.logger.debug(f"Enriched {i+1}/{len(jobs)} jobs")
                
                except Exception as e:
                    self.logger.error(f"Failed to enrich job {job.id}: {e}")
                    # Add minimal enriched data
                    enriched_jobs.append(EnrichedJobData(original_job=job))
            
            avg_quality = sum(e.quality_score for e in enriched_jobs) / len(enriched_jobs) if enriched_jobs else 0
            
            self.logger.info(f"Batch enrichment completed", extra={
                'enriched_count': len(enriched_jobs),
                'avg_quality_score': avg_quality
            })
        
        return enriched_jobs