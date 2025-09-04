"""
Job Discovery Orchestrator

Coordinates RSS feed processing, LinkedIn scraping, job enrichment,
and storage to create a comprehensive job discovery pipeline.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import time

from integrations.rss_processor import RSSFeedProcessor, JobData
from integrations.linkedin_scraper import LinkedInScraper, LinkedInSearchConfig, create_pm_search_config
from processing.job_enricher import JobEnricher, EnrichmentConfig, EnrichedJobData
from storage.job_storage import JobStorage, JobStorageConfig, create_default_storage_config
from core.default_pm_scorer import DefaultPMScorer
from core.config_loader import PMProfile, SystemSettings, ConfigLoader

from utils.logger import get_logger, performance_tracker, log_context
from utils.error_handler import retry_on_failure, NetworkError, DataProcessingError


@dataclass
class DiscoveryConfig:
    """Configuration for job discovery orchestrator."""
    # Source configuration
    enable_rss_feeds: bool = True
    enable_linkedin_scraping: bool = True
    rss_feeds: Dict[str, str] = field(default_factory=dict)
    linkedin_config: Optional[LinkedInSearchConfig] = None
    
    # Processing configuration
    enable_job_enrichment: bool = True
    enrichment_config: Optional[EnrichmentConfig] = None
    
    # Storage configuration
    storage_config: Optional[JobStorageConfig] = None
    
    # Execution configuration
    max_jobs_per_source: int = 100
    concurrent_processing: bool = True
    max_workers: int = 4
    discovery_timeout_minutes: int = 30
    
    # Scheduling
    discovery_interval_hours: int = 6
    cleanup_interval_days: int = 1


@dataclass
class DiscoveryResults:
    """Results from job discovery run."""
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Source results
    rss_jobs_found: int = 0
    linkedin_jobs_found: int = 0
    total_raw_jobs: int = 0
    
    # Processing results
    jobs_enriched: int = 0
    jobs_stored: int = 0
    duplicates_detected: int = 0
    
    # Quality metrics
    avg_quality_score: float = 0.0
    high_quality_jobs: int = 0  # Quality score >= 80
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Performance metrics
    total_duration_seconds: float = 0.0
    rss_duration_seconds: float = 0.0
    linkedin_duration_seconds: float = 0.0
    enrichment_duration_seconds: float = 0.0
    storage_duration_seconds: float = 0.0
    
    success: bool = False


class SourceWorker:
    """Worker class for handling individual job sources."""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.logger = get_logger(__name__)
    
    def process_rss_feeds(self, rss_feeds: Dict[str, str], max_jobs: int) -> Tuple[List[JobData], float]:
        """Process RSS feeds and return jobs with timing."""
        start_time = time.time()
        all_jobs = []
        
        try:
            processor = RSSFeedProcessor()
            
            # Convert rss_feeds format to what RSS processor expects
            feed_configs = {}
            for feed_name, feed_url in rss_feeds.items():
                feed_configs[feed_name] = {"url": feed_url, "enabled": True}
            
            # Process all feeds in one call
            jobs = processor.process_feeds(feed_configs)[:max_jobs]
            all_jobs.extend(jobs)
            self.logger.info(f"RSS processing provided {len(jobs)} jobs")
            
            duration = time.time() - start_time
            self.logger.info(f"RSS processing completed: {len(all_jobs)} jobs in {duration:.2f}s")
            
            return all_jobs, duration
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"RSS processing failed: {e}")
            return [], duration
    
    def process_linkedin(self, config: LinkedInSearchConfig, max_jobs: int) -> Tuple[List[JobData], float]:
        """Process LinkedIn scraping and return jobs with timing."""
        start_time = time.time()
        
        try:
            scraper = LinkedInScraper(config)
            
            jobs = scraper.discover_jobs(enrich_data=True)
            
            # Limit results
            if len(jobs) > max_jobs:
                jobs = jobs[:max_jobs]
            
            duration = time.time() - start_time
            self.logger.info(f"LinkedIn scraping completed: {len(jobs)} jobs in {duration:.2f}s")
            
            # Cleanup
            scraper.cleanup()
            
            return jobs, duration
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"LinkedIn scraping failed: {e}")
            return [], duration


class JobOrchestrator:
    """
    Main orchestrator for comprehensive job discovery and processing.
    
    Coordinates multiple data sources, enrichment, scoring, and storage
    to provide a complete job discovery pipeline.
    """
    
    def __init__(self, 
                 config: DiscoveryConfig,
                 pm_profile: PMProfile,
                 system_settings: SystemSettings):
        """Initialize job orchestrator."""
        self.config = config
        self.pm_profile = pm_profile
        self.system_settings = system_settings
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.job_enricher = JobEnricher(config.enrichment_config or EnrichmentConfig())
        self.job_storage = JobStorage(config.storage_config or create_default_storage_config())
        self.pm_scorer = DefaultPMScorer()
        
        # Execution state
        self.is_running = False
        self.current_run = None
        self.last_run_results = None
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)
        self._shutdown_event = threading.Event()
    
    @performance_tracker("job_orchestrator", "discover_jobs")
    def discover_jobs(self, 
                     run_id: Optional[str] = None,
                     progress_callback: Optional[Callable[[str, float], None]] = None) -> DiscoveryResults:
        """
        Run complete job discovery pipeline.
        
        Args:
            run_id: Optional run identifier
            progress_callback: Optional callback for progress updates
            
        Returns:
            DiscoveryResults with comprehensive metrics
        """
        if self.is_running:
            raise RuntimeError("Discovery is already running")
        
        run_id = run_id or f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        results = DiscoveryResults(run_id=run_id, started_at=datetime.now())
        self.current_run = results
        self.is_running = True
        
        try:
            self.logger.info(f"Starting job discovery run: {run_id}")
            
            # Phase 1: Data collection from sources
            if progress_callback:
                progress_callback("Collecting jobs from sources", 10)
            
            raw_jobs = self._collect_jobs_from_sources(results)
            results.total_raw_jobs = len(raw_jobs)
            
            if not raw_jobs:
                results.warnings.append("No jobs collected from any source")
                return self._finalize_results(results, False)
            
            # Phase 2: Job enrichment
            if self.config.enable_job_enrichment:
                if progress_callback:
                    progress_callback("Enriching job data", 40)
                
                enriched_jobs = self._enrich_jobs(raw_jobs, results)
                results.jobs_enriched = len(enriched_jobs)
            else:
                # Convert to enriched format without enrichment
                from processing.job_enricher import EnrichedJobData
                enriched_jobs = [EnrichedJobData(original_job=job) for job in raw_jobs]
            
            # Phase 3: Job scoring and filtering
            if progress_callback:
                progress_callback("Scoring and filtering jobs", 60)
            
            scored_jobs = self._score_and_filter_jobs(enriched_jobs, results)
            
            # Phase 4: Storage
            if progress_callback:
                progress_callback("Storing jobs", 80)
            
            storage_results = self._store_jobs(scored_jobs, results)
            
            # Phase 5: Cleanup and finalization
            if progress_callback:
                progress_callback("Finalizing", 95)
            
            self._cleanup_old_data(results)
            
            if progress_callback:
                progress_callback("Complete", 100)
            
            success = results.jobs_stored > 0
            return self._finalize_results(results, success)
        
        except Exception as e:
            self.logger.error(f"Discovery run failed: {e}", exc_info=True)
            results.errors.append(f"Discovery failed: {str(e)}")
            return self._finalize_results(results, False)
        
        finally:
            self.is_running = False
            self.current_run = None
    
    def _collect_jobs_from_sources(self, results: DiscoveryResults) -> List[JobData]:
        """Collect jobs from all configured sources."""
        all_jobs = []
        futures = []
        
        # Submit source processing tasks
        if self.config.enable_rss_feeds and self.config.rss_feeds:
            future = self.executor.submit(
                SourceWorker("rss").process_rss_feeds,
                self.config.rss_feeds,
                self.config.max_jobs_per_source
            )
            futures.append(("rss", future))
        
        if self.config.enable_linkedin_scraping and self.config.linkedin_config:
            future = self.executor.submit(
                SourceWorker("linkedin").process_linkedin,
                self.config.linkedin_config,
                self.config.max_jobs_per_source
            )
            futures.append(("linkedin", future))
        
        # Collect results
        for source_name, future in futures:
            try:
                jobs, duration = future.result(timeout=self.config.discovery_timeout_minutes * 60)
                all_jobs.extend(jobs)
                
                if source_name == "rss":
                    results.rss_jobs_found = len(jobs)
                    results.rss_duration_seconds = duration
                elif source_name == "linkedin":
                    results.linkedin_jobs_found = len(jobs)
                    results.linkedin_duration_seconds = duration
                
                self.logger.info(f"Source {source_name} contributed {len(jobs)} jobs")
                
            except Exception as e:
                error_msg = f"Source {source_name} failed: {str(e)}"
                results.errors.append(error_msg)
                self.logger.error(error_msg)
        
        self.logger.info(f"Collected {len(all_jobs)} total jobs from all sources")
        return all_jobs
    
    def _enrich_jobs(self, jobs: List[JobData], results: DiscoveryResults) -> List[EnrichedJobData]:
        """Enrich job data with additional information."""
        start_time = time.time()
        
        try:
            enriched_jobs = self.job_enricher.enrich_jobs(jobs)
            
            # Calculate quality metrics
            quality_scores = [job.quality_score for job in enriched_jobs]
            results.avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            results.high_quality_jobs = sum(1 for score in quality_scores if score >= 80)
            
            results.enrichment_duration_seconds = time.time() - start_time
            
            self.logger.info(f"Enriched {len(enriched_jobs)} jobs (avg quality: {results.avg_quality_score:.1f})")
            return enriched_jobs
            
        except Exception as e:
            results.errors.append(f"Job enrichment failed: {str(e)}")
            self.logger.error(f"Job enrichment failed: {e}")
            
            # Return minimal enrichment
            from processing.job_enricher import EnrichedJobData
            return [EnrichedJobData(original_job=job) for job in jobs]
    
    def _score_and_filter_jobs(self, enriched_jobs: List[EnrichedJobData], results: DiscoveryResults) -> List[EnrichedJobData]:
        """Score jobs and filter based on minimum threshold."""
        scored_jobs = []
        
        for enriched_job in enriched_jobs:
            try:
                # Score the original job data
                job_score = self.pm_scorer.score_job(
                    enriched_job.original_job,
                    self.pm_profile,
                    self.system_settings
                )
                
                # Attach score to enriched data
                enriched_job.pm_score = job_score
                
                # Filter by minimum threshold
                if job_score.total_score >= self.system_settings.minimum_score_threshold:
                    scored_jobs.append(enriched_job)
                
            except Exception as e:
                self.logger.warning(f"Failed to score job {enriched_job.original_job.id}: {e}")
                continue
        
        self.logger.info(f"Scored and filtered to {len(scored_jobs)} jobs above threshold")
        return scored_jobs
    
    def _store_jobs(self, jobs: List[EnrichedJobData], results: DiscoveryResults) -> Dict[str, Any]:
        """Store jobs in persistent storage."""
        start_time = time.time()
        
        try:
            # Extract original job data for storage
            job_data_list = [job.original_job for job in jobs]
            
            storage_results = self.job_storage.store_jobs(job_data_list)
            
            results.jobs_stored = storage_results['stored_count']
            results.duplicates_detected = storage_results['duplicate_count']
            results.storage_duration_seconds = time.time() - start_time
            
            if storage_results['errors']:
                results.errors.extend(storage_results['errors'])
            
            self.logger.info(f"Stored {results.jobs_stored} jobs ({results.duplicates_detected} duplicates)")
            
            return storage_results
            
        except Exception as e:
            results.errors.append(f"Job storage failed: {str(e)}")
            self.logger.error(f"Job storage failed: {e}")
            return {}
    
    def _cleanup_old_data(self, results: DiscoveryResults):
        """Clean up old data based on retention policies."""
        try:
            cleanup_results = self.job_storage.cleanup_old_jobs()
            
            if cleanup_results:
                results.warnings.append(
                    f"Cleaned up {cleanup_results.get('index_jobs_removed', 0)} old jobs"
                )
            
        except Exception as e:
            results.warnings.append(f"Cleanup failed: {str(e)}")
            self.logger.warning(f"Data cleanup failed: {e}")
    
    def _finalize_results(self, results: DiscoveryResults, success: bool) -> DiscoveryResults:
        """Finalize discovery results."""
        results.completed_at = datetime.now()
        results.total_duration_seconds = (results.completed_at - results.started_at).total_seconds()
        results.success = success
        
        self.last_run_results = results
        
        # Log summary
        if success:
            self.logger.info(f"Discovery completed successfully", extra={
                'run_id': results.run_id,
                'jobs_stored': results.jobs_stored,
                'duration': results.total_duration_seconds
            })
        else:
            self.logger.error(f"Discovery failed", extra={
                'run_id': results.run_id,
                'errors': len(results.errors),
                'duration': results.total_duration_seconds
            })
        
        return results
    
    def get_discovery_status(self) -> Dict[str, Any]:
        """Get current discovery status."""
        return {
            'is_running': self.is_running,
            'current_run_id': self.current_run.run_id if self.current_run else None,
            'last_run': {
                'run_id': self.last_run_results.run_id,
                'success': self.last_run_results.success,
                'jobs_stored': self.last_run_results.jobs_stored,
                'completed_at': self.last_run_results.completed_at.isoformat() if self.last_run_results.completed_at else None
            } if self.last_run_results else None,
            'storage_stats': self.job_storage.get_storage_stats().__dict__ if self.job_storage else None
        }
    
    def create_backup(self) -> str:
        """Create backup of all stored data."""
        try:
            backup_path = self.job_storage.create_backup()
            self.logger.info(f"Backup created: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"Backup creation failed: {e}")
            raise
    
    def shutdown(self, wait_for_completion: bool = True):
        """Shutdown orchestrator gracefully."""
        self.logger.info("Shutting down job orchestrator")
        
        self._shutdown_event.set()
        
        if wait_for_completion and self.is_running:
            self.logger.info("Waiting for current discovery to complete...")
            while self.is_running:
                time.sleep(1)
        
        self.executor.shutdown(wait=wait_for_completion)
        self.logger.info("Job orchestrator shutdown complete")


def create_default_discovery_config(
    pm_profile: PMProfile,
    enable_linkedin: bool = True,
    rss_feeds: Dict[str, str] = None
) -> DiscoveryConfig:
    """Create default discovery configuration optimized for PM jobs."""
    
    # Use RSS feeds from configuration - no hardcoded defaults
    default_rss_feeds = {}
    
    linkedin_config = None
    if enable_linkedin:
        linkedin_config = create_pm_search_config(
            location=pm_profile.preferred_locations[0] if pm_profile.preferred_locations else "Remote",
            experience_levels=["mid", "senior"] if pm_profile.seniority_level in ["mid", "senior"] else ["associate", "mid"],
            date_posted="week"
        )
    
    return DiscoveryConfig(
        enable_rss_feeds=bool(rss_feeds or default_rss_feeds),
        enable_linkedin_scraping=enable_linkedin,
        rss_feeds=rss_feeds or default_rss_feeds,
        linkedin_config=linkedin_config,
        
        enable_job_enrichment=True,
        enrichment_config=EnrichmentConfig(),
        
        storage_config=create_default_storage_config(),
        
        max_jobs_per_source=100,
        concurrent_processing=True,
        max_workers=4,
        discovery_timeout_minutes=30,
        
        discovery_interval_hours=6,
        cleanup_interval_days=1
    )


async def run_scheduled_discovery(
    orchestrator: JobOrchestrator,
    interval_hours: int = 6,
    progress_callback: Optional[Callable[[str, float], None]] = None
):
    """Run discovery on a schedule."""
    logger = get_logger(__name__)
    
    while not orchestrator._shutdown_event.is_set():
        try:
            logger.info("Starting scheduled job discovery")
            
            results = orchestrator.discover_jobs(progress_callback=progress_callback)
            
            if results.success:
                logger.info(f"Scheduled discovery completed: {results.jobs_stored} jobs stored")
            else:
                logger.error(f"Scheduled discovery failed: {len(results.errors)} errors")
            
        except Exception as e:
            logger.error(f"Scheduled discovery error: {e}", exc_info=True)
        
        # Wait for next interval
        await asyncio.sleep(interval_hours * 3600)
    
    logger.info("Scheduled discovery stopped")