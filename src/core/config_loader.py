"""
Configuration Loading and Validation System

Robust configuration management with comprehensive validation,
error handling, and fallback mechanisms for PM Watchman.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging


@dataclass
class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    field_name: str
    message: str
    
    def __str__(self):
        return f"Config validation error in '{self.field_name}': {self.message}"


@dataclass
class PMProfile:
    """Product Manager profile configuration."""
    years_of_pm_experience: int
    current_title: str
    seniority_level: str
    primary_titles: List[str]
    secondary_titles: List[str]
    avoid_titles: List[str]
    core_pm_skills: List[str]
    technical_skills: List[str]
    domain_expertise: List[str]
    primary_industries: List[str]
    interested_industries: List[str]
    avoid_industries: List[str]
    remote_preference: str
    preferred_locations: List[str]
    company_stages: List[str]
    company_sizes: List[str]
    preferred_companies: List[str]
    avoid_companies: List[str]
    minimum_base_salary: int
    target_total_comp: int
    equity_importance: str
    
    def __post_init__(self):
        """Validate PM profile data after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate all PM profile fields."""
        # Experience validation
        if not (0 <= self.years_of_pm_experience <= 50):
            raise ConfigValidationError(
                "years_of_pm_experience", 
                "Must be between 0 and 50 years"
            )
        
        valid_seniority = ["junior", "mid", "senior", "principal", "director", "vp"]
        if self.seniority_level.lower() not in valid_seniority:
            raise ConfigValidationError(
                "seniority_level",
                f"Must be one of: {', '.join(valid_seniority)}"
            )
        
        # Remote preference validation
        valid_remote = ["remote_only", "remote_first", "hybrid", "onsite"]
        if self.remote_preference.lower() not in valid_remote:
            raise ConfigValidationError(
                "remote_preference",
                f"Must be one of: {', '.join(valid_remote)}"
            )
        
        # Salary validation
        if self.minimum_base_salary < 0 or self.target_total_comp < 0:
            raise ConfigValidationError(
                "compensation",
                "Salary values must be positive"
            )
        
        if self.minimum_base_salary > self.target_total_comp:
            raise ConfigValidationError(
                "compensation",
                "Minimum salary cannot exceed target total compensation"
            )
        
        # Equity importance validation
        valid_equity = ["low", "medium", "high"]
        if self.equity_importance.lower() not in valid_equity:
            raise ConfigValidationError(
                "equity_importance",
                f"Must be one of: {', '.join(valid_equity)}"
            )
        
        # Required lists validation
        required_lists = [
            ("primary_titles", self.primary_titles),
            ("core_pm_skills", self.core_pm_skills),
            ("primary_industries", self.primary_industries),
            ("preferred_locations", self.preferred_locations)
        ]
        
        for field_name, field_value in required_lists:
            if not field_value or len(field_value) == 0:
                raise ConfigValidationError(
                    field_name,
                    "Must contain at least one item"
                )


@dataclass 
class SystemSettings:
    """System behavior and scheduling configuration."""
    jobs_per_batch: int = 10
    batches_per_day: int = 4
    hours_between_batches: int = 6
    preferred_start_hour: int = 9
    timezone: str = "America/Los_Angeles"
    minimum_score_threshold: int = 60
    title_match_importance: str = "high"
    skills_match_importance: str = "high"
    experience_match_importance: str = "medium"
    industry_match_importance: str = "medium"
    company_match_importance: str = "low"
    jobs_per_message: int = 1
    include_description_preview: bool = True
    max_description_length: int = 200
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    data_retention_days: int = 30
    cleanup_frequency_days: int = 7
    feed_timeout_seconds: int = 30
    max_jobs_per_source: int = 100
    
    def __post_init__(self):
        """Validate system settings after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate system settings."""
        if not (5 <= self.jobs_per_batch <= 20):
            raise ConfigValidationError(
                "jobs_per_batch",
                "Must be between 5 and 20"
            )
        
        if not (2 <= self.batches_per_day <= 8):
            raise ConfigValidationError(
                "batches_per_day", 
                "Must be between 2 and 8"
            )
        
        if not (1 <= self.hours_between_batches <= 12):
            raise ConfigValidationError(
                "hours_between_batches",
                "Must be between 1 and 12 hours"
            )
        
        if not (40 <= self.minimum_score_threshold <= 90):
            raise ConfigValidationError(
                "minimum_score_threshold",
                "Must be between 40 and 90"
            )
        
        valid_importance = ["low", "medium", "high"]
        importance_fields = [
            ("title_match_importance", self.title_match_importance),
            ("skills_match_importance", self.skills_match_importance),
            ("experience_match_importance", self.experience_match_importance),
            ("industry_match_importance", self.industry_match_importance),
            ("company_match_importance", self.company_match_importance)
        ]
        
        for field_name, value in importance_fields:
            if value.lower() not in valid_importance:
                raise ConfigValidationError(
                    field_name,
                    f"Must be one of: {', '.join(valid_importance)}"
                )


@dataclass
class JobSources:
    """Job discovery sources configuration."""
    linkedin_enabled: bool = True
    linkedin_priority: int = 1
    job_titles: List[str] = field(default_factory=lambda: ["Product Manager"])
    locations: List[str] = field(default_factory=lambda: ["Remote"])
    date_posted: str = "past_24_hours"
    experience_levels: List[str] = field(default_factory=lambda: ["mid_senior"])
    rss_feeds: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate job sources after initialization.""" 
        self._validate()
    
    def _validate(self):
        """Validate job sources configuration."""
        if not self.job_titles:
            raise ConfigValidationError(
                "job_titles",
                "Must specify at least one job title"
            )
        
        if not self.locations:
            raise ConfigValidationError(
                "locations", 
                "Must specify at least one location"
            )
        
        valid_date_posted = ["past_24_hours", "past_week", "past_month"]
        if self.date_posted not in valid_date_posted:
            raise ConfigValidationError(
                "date_posted",
                f"Must be one of: {', '.join(valid_date_posted)}"
            )


class ConfigLoader:
    """
    Robust configuration loader with validation, error handling, and fallbacks.
    
    Features:
    - JSON validation with detailed error messages
    - Configuration field validation
    - Default fallback values
    - Environment variable override support
    - Hot reload capability
    """
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize configuration loader.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir)
        self.logger = logging.getLogger(__name__)
        self._ensure_config_dir()
        
        # Configuration cache
        self._pm_profile: Optional[PMProfile] = None
        self._system_settings: Optional[SystemSettings] = None
        self._job_sources: Optional[JobSources] = None
        self._last_loaded: Dict[str, float] = {}
    
    def _ensure_config_dir(self):
        """Ensure configuration directory exists."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Configuration directory: {self.config_dir}")
        except Exception as e:
            raise ConfigValidationError(
                "config_directory",
                f"Cannot create config directory: {e}"
            )
    
    def _load_json_file(self, filename: str) -> Dict[str, Any]:
        """
        Load and validate JSON file with comprehensive error handling.
        
        Args:
            filename: JSON file to load
            
        Returns:
            Parsed JSON data
            
        Raises:
            ConfigValidationError: If file cannot be loaded or parsed
        """
        file_path = self.config_dir / filename
        
        try:
            if not file_path.exists():
                raise ConfigValidationError(
                    filename,
                    f"Configuration file not found: {file_path}"
                )
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.logger.info(f"Loaded configuration: {filename}")
            return data
            
        except json.JSONDecodeError as e:
            raise ConfigValidationError(
                filename,
                f"Invalid JSON format: {e.msg} at line {e.lineno}, column {e.colno}"
            )
        except Exception as e:
            raise ConfigValidationError(
                filename,
                f"Error loading file: {str(e)}"
            )
    
    def _extract_pm_profile_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and flatten PM profile data from nested JSON structure."""
        try:
            experience = data.get("experience", {})
            target_roles = data.get("target_roles", {})
            skills = data.get("skills", {})
            industries = data.get("industries", {})
            geo_prefs = data.get("geographic_preferences", {})
            company_prefs = data.get("company_preferences", {})
            compensation = data.get("compensation", {})
            
            return {
                # Experience
                "years_of_pm_experience": experience.get("years_of_pm_experience", 0),
                "current_title": experience.get("current_title", "Product Manager"),
                "seniority_level": experience.get("seniority_level", "mid"),
                
                # Target roles
                "primary_titles": target_roles.get("primary_titles", ["Product Manager"]),
                "secondary_titles": target_roles.get("secondary_titles", []),
                "avoid_titles": target_roles.get("avoid_titles", []),
                
                # Skills
                "core_pm_skills": skills.get("core_pm_skills", ["product strategy"]),
                "technical_skills": skills.get("technical_skills", []),
                "domain_expertise": skills.get("domain_expertise", []),
                
                # Industries
                "primary_industries": industries.get("primary_experience", ["technology"]),
                "interested_industries": industries.get("interested_in", []),
                "avoid_industries": industries.get("avoid_industries", []),
                
                # Geographic
                "remote_preference": geo_prefs.get("remote_preference", "remote_first"),
                "preferred_locations": geo_prefs.get("preferred_locations", ["Remote"]),
                
                # Company
                "company_stages": company_prefs.get("company_stages", ["startup"]),
                "company_sizes": company_prefs.get("company_sizes", ["51-200"]),
                "preferred_companies": company_prefs.get("preferred_companies", []),
                "avoid_companies": company_prefs.get("avoid_companies", []),
                
                # Compensation
                "minimum_base_salary": compensation.get("minimum_base_salary", 100000),
                "target_total_comp": compensation.get("target_total_comp", 150000),
                "equity_importance": compensation.get("equity_importance", "medium")
            }
        except KeyError as e:
            raise ConfigValidationError(
                "pm_profile_structure",
                f"Missing required section in PM profile: {e}"
            )
    
    def load_pm_profile(self, force_reload: bool = False) -> PMProfile:
        """
        Load and validate PM profile configuration.
        
        Args:
            force_reload: Force reload even if cached
            
        Returns:
            Validated PMProfile instance
        """
        filename = "pm_profile.json"
        
        if not force_reload and self._pm_profile is not None:
            return self._pm_profile
        
        try:
            data = self._load_json_file(filename)
            profile_data = self._extract_pm_profile_data(data)
            self._pm_profile = PMProfile(**profile_data)
            
            self.logger.info("PM profile loaded and validated successfully")
            return self._pm_profile
            
        except Exception as e:
            self.logger.error(f"Failed to load PM profile: {e}")
            raise
    
    def load_system_settings(self, force_reload: bool = False) -> SystemSettings:
        """
        Load and validate system settings configuration.
        
        Args:
            force_reload: Force reload even if cached
            
        Returns:
            Validated SystemSettings instance
        """
        filename = "system_settings.json"
        
        if not force_reload and self._system_settings is not None:
            return self._system_settings
        
        try:
            data = self._load_json_file(filename)
            
            # Flatten nested structure
            settings_data = {}
            
            # Scheduling
            scheduling = data.get("scheduling", {})
            settings_data.update({
                "jobs_per_batch": scheduling.get("jobs_per_batch", 10),
                "batches_per_day": scheduling.get("batches_per_day", 4),
                "hours_between_batches": scheduling.get("hours_between_batches", 6),
                "preferred_start_hour": scheduling.get("preferred_start_hour", 9),
                "timezone": scheduling.get("timezone", "America/Los_Angeles")
            })
            
            # Scoring
            scoring = data.get("scoring", {})
            settings_data.update({
                "minimum_score_threshold": scoring.get("minimum_score_threshold", 60),
                "title_match_importance": scoring.get("title_match_importance", "high"),
                "skills_match_importance": scoring.get("skills_match_importance", "high"),
                "experience_match_importance": scoring.get("experience_match_importance", "medium"),
                "industry_match_importance": scoring.get("industry_match_importance", "medium"),
                "company_match_importance": scoring.get("company_match_importance", "low")
            })
            
            # Telegram
            telegram = data.get("telegram", {})
            msg_format = telegram.get("message_formatting", {})
            delivery = telegram.get("delivery_settings", {})
            
            settings_data.update({
                "jobs_per_message": msg_format.get("jobs_per_message", 1),
                "include_description_preview": msg_format.get("include_description_preview", True),
                "max_description_length": msg_format.get("max_description_length", 200),
                "retry_attempts": delivery.get("retry_attempts", 3),
                "retry_delay_seconds": delivery.get("retry_delay_seconds", 5)
            })
            
            # Storage & Reliability
            storage = data.get("storage", {})
            reliability = data.get("reliability", {})
            
            settings_data.update({
                "data_retention_days": storage.get("data_retention_days", 30),
                "cleanup_frequency_days": storage.get("cleanup_frequency_days", 7),
                "feed_timeout_seconds": reliability.get("feed_timeout_seconds", 30),
                "max_jobs_per_source": reliability.get("max_jobs_per_source", 100)
            })
            
            self._system_settings = SystemSettings(**settings_data)
            
            self.logger.info("System settings loaded and validated successfully")
            return self._system_settings
            
        except Exception as e:
            self.logger.error(f"Failed to load system settings: {e}")
            raise
    
    def load_job_sources(self, force_reload: bool = False) -> JobSources:
        """
        Load and validate job sources configuration.
        
        Args:
            force_reload: Force reload even if cached
            
        Returns:
            Validated JobSources instance
        """
        filename = "job_sources.json"
        
        if not force_reload and self._job_sources is not None:
            return self._job_sources
        
        try:
            data = self._load_json_file(filename)
            
            # LinkedIn settings
            linkedin = data.get("linkedin", {})
            search_params = linkedin.get("search_parameters", {})
            
            sources_data = {
                "linkedin_enabled": linkedin.get("enabled", True),
                "linkedin_priority": linkedin.get("priority", 1),
                "job_titles": search_params.get("job_titles", ["Product Manager"]),
                "locations": search_params.get("locations", ["Remote"]),
                "date_posted": search_params.get("date_posted", "past_24_hours"),
                "experience_levels": search_params.get("experience_level", ["mid_senior"]),
                "rss_feeds": data.get("rss_feeds", {})
            }
            
            self._job_sources = JobSources(**sources_data)
            
            self.logger.info("Job sources loaded and validated successfully")
            return self._job_sources
            
        except Exception as e:
            self.logger.error(f"Failed to load job sources: {e}")
            raise
    
    def load_all_configs(self) -> tuple[PMProfile, SystemSettings, JobSources]:
        """
        Load all configuration files.
        
        Returns:
            Tuple of (PMProfile, SystemSettings, JobSources)
        """
        pm_profile = self.load_pm_profile()
        system_settings = self.load_system_settings()
        job_sources = self.load_job_sources()
        
        self.logger.info("All configurations loaded successfully")
        return pm_profile, system_settings, job_sources
    
    def validate_environment_variables(self) -> Dict[str, str]:
        """
        Validate required environment variables.
        
        Returns:
            Dictionary of validated environment variables
            
        Raises:
            ConfigValidationError: If required variables are missing
        """
        required_vars = {
            "TELEGRAM_BOT_TOKEN": "Telegram bot token",
            "TELEGRAM_CHAT_ID": "Telegram chat ID"
        }
        
        env_vars = {}
        missing_vars = []
        
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)
            if not value:
                missing_vars.append(f"{var_name} ({description})")
            else:
                env_vars[var_name] = value
        
        if missing_vars:
            raise ConfigValidationError(
                "environment_variables",
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
        
        # Basic validation
        bot_token = env_vars.get("TELEGRAM_BOT_TOKEN", "")
        if ":" not in bot_token or len(bot_token) < 10:
            raise ConfigValidationError(
                "TELEGRAM_BOT_TOKEN",
                "Invalid bot token format (should contain ':' and be longer)"
            )
        
        chat_id = env_vars.get("TELEGRAM_CHAT_ID", "")
        if not chat_id.isdigit() or len(chat_id) < 5:
            raise ConfigValidationError(
                "TELEGRAM_CHAT_ID", 
                "Invalid chat ID format (should be numeric and longer than 5 digits)"
            )
        
        self.logger.info("Environment variables validated successfully")
        return env_vars