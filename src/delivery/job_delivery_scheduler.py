"""
Job Delivery Scheduler

Advanced scheduling system for delivering PM jobs via Telegram with
user preferences, timezone handling, and delivery optimization.
"""

import asyncio
import schedule
import threading
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time as datetime_time
import pytz
from enum import Enum
import json
import time

from delivery.telegram_bot import PMJobTelegramBot, TelegramUserPreferences
from core.job_orchestrator import JobOrchestrator, DiscoveryResults
from processing.job_enricher import EnrichedJobData
from storage.job_storage import JobStorage
from utils.logger import get_logger, performance_tracker, log_context
from utils.error_handler import retry_on_failure, DataProcessingError


class DeliveryFrequency(Enum):
    """Delivery frequency options."""
    IMMEDIATE = "immediate"
    DAILY = "daily"
    TWICE_DAILY = "twice_daily"
    WEEKLY = "weekly"
    DISABLED = "disabled"


@dataclass
class DeliveryWindow:
    """Time window for job delivery."""
    hour: int  # 0-23
    minute: int = 0  # 0-59
    timezone: str = "UTC"
    
    def to_time(self) -> datetime_time:
        """Convert to datetime.time object."""
        return datetime_time(hour=self.hour, minute=self.minute)
    
    def get_timezone(self) -> pytz.BaseTzInfo:
        """Get timezone object."""
        return pytz.timezone(self.timezone)


@dataclass
class DeliveryAttempt:
    """Record of delivery attempt."""
    user_id: int
    jobs_delivered: int
    delivery_time: datetime
    success: bool
    error_message: Optional[str] = None
    jobs_filtered: int = 0
    jobs_scored: int = 0


@dataclass
class DeliveryStats:
    """Delivery statistics for monitoring."""
    total_attempts: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    total_jobs_delivered: int = 0
    total_users_served: int = 0
    avg_jobs_per_user: float = 0.0
    avg_delivery_time_seconds: float = 0.0
    last_delivery_batch: Optional[datetime] = None
    error_rate: float = 0.0


class JobDeliveryScheduler:
    """
    Sophisticated job delivery scheduler with user preferences,
    timezone handling, and delivery optimization.
    """
    
    def __init__(self, 
                 telegram_bot: PMJobTelegramBot,
                 job_orchestrator: JobOrchestrator,
                 job_storage: JobStorage):
        """Initialize delivery scheduler."""
        self.telegram_bot = telegram_bot
        self.job_orchestrator = job_orchestrator
        self.job_storage = job_storage
        self.logger = get_logger(__name__)
        
        # Scheduling state
        self.is_running = False
        self.scheduler_thread = None
        self._stop_event = threading.Event()
        
        # Delivery tracking
        self.delivery_attempts: List[DeliveryAttempt] = []
        self.stats = DeliveryStats()
        
        # User delivery schedules
        self._user_schedules: Dict[int, schedule.Job] = {}
        
        # Configure scheduler
        self.scheduler = schedule
        self._setup_default_schedules()
    
    def _setup_default_schedules(self):
        """Setup default delivery schedules."""
        # Daily morning delivery (9:00 AM UTC)
        self.scheduler.every().day.at("09:00").do(
            self._run_daily_delivery_batch, 
            delivery_window=DeliveryWindow(hour=9, minute=0)
        )
        
        # Evening delivery for twice-daily users (18:00 UTC)
        self.scheduler.every().day.at("18:00").do(
            self._run_evening_delivery_batch,
            delivery_window=DeliveryWindow(hour=18, minute=0)
        )
        
        # Cleanup old delivery records weekly
        self.scheduler.every().sunday.at("02:00").do(self._cleanup_old_records)
    
    def start_scheduler(self):
        """Start the delivery scheduler."""
        if self.is_running:
            self.logger.warning("Delivery scheduler is already running")
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="DeliveryScheduler",
            daemon=True
        )
        self.scheduler_thread.start()
        
        self.logger.info("Job delivery scheduler started")
    
    def stop_scheduler(self):
        """Stop the delivery scheduler."""
        if not self.is_running:
            return
        
        self._stop_event.set()
        self.is_running = False
        
        # Clear all scheduled jobs
        self.scheduler.clear()
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        self.logger.info("Job delivery scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        self.logger.info("Starting delivery scheduler loop")
        
        while not self._stop_event.is_set():
            try:
                # Run pending scheduled jobs
                self.scheduler.run_pending()
                
                # Check for immediate delivery requests
                self._process_immediate_deliveries()
                
                # Brief sleep to prevent busy waiting
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                time.sleep(60)  # Wait longer on error
        
        self.logger.info("Delivery scheduler loop stopped")
    
    def _run_daily_delivery_batch(self, delivery_window: DeliveryWindow):
        """Run daily delivery batch for morning users."""
        asyncio.run(self._execute_delivery_batch("daily_morning", delivery_window))
    
    def _run_evening_delivery_batch(self, delivery_window: DeliveryWindow):
        """Run evening delivery batch for twice-daily users.""" 
        asyncio.run(self._execute_delivery_batch("daily_evening", delivery_window))
    
    @performance_tracker("delivery_scheduler", "execute_delivery_batch")
    async def _execute_delivery_batch(self, batch_type: str, delivery_window: DeliveryWindow):
        """Execute a delivery batch for users."""
        batch_start_time = datetime.now()
        
        with log_context(operation="delivery_batch", batch_type=batch_type):
            self.logger.info(f"Starting {batch_type} delivery batch")
            
            try:
                # Get active users for this delivery window
                target_users = await self._get_users_for_delivery_window(delivery_window, batch_type)
                
                if not target_users:
                    self.logger.info(f"No users scheduled for {batch_type} delivery")
                    return
                
                # Get recent high-quality jobs
                jobs = await self._get_jobs_for_delivery()
                
                if not jobs:
                    self.logger.warning("No jobs available for delivery")
                    return
                
                # Deliver jobs to users
                delivery_results = await self._deliver_to_users(target_users, jobs)
                
                # Update statistics
                self._update_delivery_stats(delivery_results, batch_start_time)
                
                self.logger.info(f"Completed {batch_type} delivery batch: "
                               f"{len(delivery_results)} users, "
                               f"{sum(r.jobs_delivered for r in delivery_results)} jobs delivered")
                
            except Exception as e:
                self.logger.error(f"Delivery batch {batch_type} failed: {e}", exc_info=True)
    
    async def _get_users_for_delivery_window(self, 
                                           delivery_window: DeliveryWindow, 
                                           batch_type: str) -> List[TelegramUserPreferences]:
        """Get users who should receive deliveries in this window."""
        all_users = self.telegram_bot.user_db.get_all_active_users()
        target_users = []
        
        for user_id in all_users:
            try:
                preferences = self.telegram_bot.user_db.get_user_preferences(user_id)
                if not preferences or not preferences.enabled:
                    continue
                
                # Check delivery frequency and timing
                if self._should_deliver_to_user(preferences, delivery_window, batch_type):
                    target_users.append(preferences)
                    
            except Exception as e:
                self.logger.warning(f"Failed to check delivery for user {user_id}: {e}")
                continue
        
        return target_users
    
    def _should_deliver_to_user(self, 
                               preferences: TelegramUserPreferences,
                               delivery_window: DeliveryWindow,
                               batch_type: str) -> bool:
        """Check if user should receive delivery in this batch."""
        
        # Check if user has disabled deliveries
        if not preferences.enabled:
            return False
        
        # Check delivery frequency
        if preferences.frequency == DeliveryFrequency.DISABLED.value:
            return False
        
        # For immediate delivery, users are handled separately
        if preferences.frequency == DeliveryFrequency.IMMEDIATE.value:
            return False
        
        # Check if it's the right batch for this user
        if batch_type == "daily_morning":
            # Morning delivery for daily and twice-daily users
            return preferences.frequency in [DeliveryFrequency.DAILY.value, DeliveryFrequency.TWICE_DAILY.value]
        
        elif batch_type == "daily_evening":
            # Evening delivery only for twice-daily users
            return preferences.frequency == DeliveryFrequency.TWICE_DAILY.value
        
        # Check user's preferred delivery time (with timezone consideration)
        user_tz = pytz.timezone(preferences.timezone)
        delivery_tz = delivery_window.get_timezone()
        
        # Convert delivery window to user's timezone
        now_utc = datetime.now(pytz.UTC)
        user_time = now_utc.astimezone(user_tz).time()
        
        # Parse user's preferred delivery time
        try:
            preferred_hour, preferred_minute = map(int, preferences.delivery_time.split(':'))
            preferred_time = datetime_time(hour=preferred_hour, minute=preferred_minute)
            
            # Allow 2-hour window around preferred time
            time_diff = abs((user_time.hour * 60 + user_time.minute) - 
                          (preferred_time.hour * 60 + preferred_time.minute))
            
            return time_diff <= 120  # Within 2 hours
            
        except (ValueError, AttributeError):
            # Default to delivery window if user time is invalid
            return True
    
    async def _get_jobs_for_delivery(self, max_age_hours: int = 24) -> List[EnrichedJobData]:
        """Get recent high-quality jobs for delivery."""
        try:
            # Get jobs from last 24 hours
            since = datetime.now() - timedelta(hours=max_age_hours)
            recent_jobs = self.job_storage.load_jobs(limit=100, since=since)
            
            if not recent_jobs:
                self.logger.warning("No recent jobs found for delivery")
                return []
            
            # Enrich jobs with scoring (simplified for delivery)
            enriched_jobs = []
            
            for job in recent_jobs:
                try:
                    # Score job using PM scorer
                    score_result = self.telegram_bot.pm_scorer.score_job(
                        job, 
                        self.telegram_bot.pm_profile, 
                        self.telegram_bot.system_settings
                    )
                    
                    # Only include jobs above minimum threshold
                    if score_result.total_score >= 60.0:  # Default threshold
                        from processing.job_enricher import EnrichedJobData
                        enriched = EnrichedJobData(original_job=job)
                        enriched.pm_score = score_result
                        enriched_jobs.append(enriched)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to score job {job.id}: {e}")
                    continue
            
            # Sort by score (highest first)
            enriched_jobs.sort(key=lambda x: x.pm_score.total_score, reverse=True)
            
            self.logger.info(f"Prepared {len(enriched_jobs)} jobs for delivery (from {len(recent_jobs)} total)")
            return enriched_jobs
            
        except Exception as e:
            self.logger.error(f"Failed to get jobs for delivery: {e}")
            return []
    
    async def _deliver_to_users(self, 
                              users: List[TelegramUserPreferences], 
                              jobs: List[EnrichedJobData]) -> List[DeliveryAttempt]:
        """Deliver jobs to list of users."""
        delivery_results = []
        
        for preferences in users:
            delivery_start_time = datetime.now()
            
            try:
                # Filter jobs for this specific user
                user_jobs = await self._filter_jobs_for_user(jobs, preferences)
                
                if not user_jobs:
                    # Record empty delivery
                    delivery_results.append(DeliveryAttempt(
                        user_id=preferences.user_id,
                        jobs_delivered=0,
                        delivery_time=delivery_start_time,
                        success=True,
                        jobs_filtered=len(jobs),
                        jobs_scored=len(jobs)
                    ))
                    continue
                
                # Send jobs to user via Telegram bot
                from telegram.ext import ContextTypes
                context = ContextTypes.DEFAULT_TYPE(self.telegram_bot.app)
                
                await self.telegram_bot._send_jobs_to_user(
                    user_id=preferences.user_id,
                    jobs=user_jobs,
                    preferences=preferences,
                    context=context
                )
                
                # Record successful delivery
                delivery_results.append(DeliveryAttempt(
                    user_id=preferences.user_id,
                    jobs_delivered=len(user_jobs),
                    delivery_time=delivery_start_time,
                    success=True,
                    jobs_filtered=len(jobs),
                    jobs_scored=len(user_jobs)
                ))
                
                self.logger.info(f"Delivered {len(user_jobs)} jobs to user {preferences.user_id}")
                
            except Exception as e:
                # Record failed delivery
                delivery_results.append(DeliveryAttempt(
                    user_id=preferences.user_id,
                    jobs_delivered=0,
                    delivery_time=delivery_start_time,
                    success=False,
                    error_message=str(e),
                    jobs_filtered=len(jobs)
                ))
                
                self.logger.error(f"Failed to deliver jobs to user {preferences.user_id}: {e}")
        
        return delivery_results
    
    async def _filter_jobs_for_user(self, 
                                  jobs: List[EnrichedJobData], 
                                  preferences: TelegramUserPreferences) -> List[EnrichedJobData]:
        """Filter jobs based on user preferences."""
        filtered_jobs = []
        
        for job in jobs:
            try:
                # Apply score threshold
                if job.pm_score.total_score < preferences.min_score_threshold:
                    continue
                
                # Apply keyword filters
                job_text = f"{job.original_job.title} {job.original_job.company}".lower()
                
                if hasattr(job.original_job, 'description') and job.original_job.description:
                    job_text += f" {job.original_job.description}".lower()
                
                # Check excluded keywords
                if preferences.excluded_keywords:
                    if any(keyword.lower() in job_text for keyword in preferences.excluded_keywords):
                        continue
                
                # Check required keywords
                if preferences.required_keywords:
                    if not any(keyword.lower() in job_text for keyword in preferences.required_keywords):
                        continue
                
                # Check excluded companies
                if preferences.excluded_companies:
                    if any(company.lower() in job.original_job.company.lower() 
                          for company in preferences.excluded_companies):
                        continue
                
                filtered_jobs.append(job)
                
            except Exception as e:
                self.logger.warning(f"Error filtering job {job.original_job.id}: {e}")
                continue
        
        # Sort by score and limit
        filtered_jobs.sort(key=lambda x: x.pm_score.total_score, reverse=True)
        return filtered_jobs[:preferences.max_daily_jobs]
    
    def _process_immediate_deliveries(self):
        """Process immediate delivery requests."""
        # TODO: Implement immediate delivery processing
        # This would check for jobs that should be delivered immediately
        # when they meet certain criteria (very high scores, specific keywords, etc.)
        pass
    
    def _update_delivery_stats(self, 
                              delivery_results: List[DeliveryAttempt],
                              batch_start_time: datetime):
        """Update delivery statistics."""
        successful_deliveries = [d for d in delivery_results if d.success]
        failed_deliveries = [d for d in delivery_results if not d.success]
        
        self.stats.total_attempts += len(delivery_results)
        self.stats.successful_deliveries += len(successful_deliveries)
        self.stats.failed_deliveries += len(failed_deliveries)
        self.stats.total_jobs_delivered += sum(d.jobs_delivered for d in delivery_results)
        self.stats.total_users_served = len(set(d.user_id for d in delivery_results))
        self.stats.last_delivery_batch = batch_start_time
        
        # Calculate rates
        if self.stats.total_attempts > 0:
            self.stats.error_rate = self.stats.failed_deliveries / self.stats.total_attempts
        
        if successful_deliveries:
            self.stats.avg_jobs_per_user = (
                sum(d.jobs_delivered for d in successful_deliveries) / len(successful_deliveries)
            )
        
        # Store delivery attempts for history
        self.delivery_attempts.extend(delivery_results)
        
        # Keep only last 1000 attempts to prevent memory growth
        if len(self.delivery_attempts) > 1000:
            self.delivery_attempts = self.delivery_attempts[-1000:]
    
    def _cleanup_old_records(self):
        """Clean up old delivery records."""
        cutoff_date = datetime.now() - timedelta(days=30)
        
        # Remove old delivery attempts
        self.delivery_attempts = [
            attempt for attempt in self.delivery_attempts 
            if attempt.delivery_time > cutoff_date
        ]
        
        self.logger.info("Cleaned up old delivery records")
    
    @retry_on_failure(max_attempts=3, base_delay=5)
    async def trigger_immediate_delivery(self, 
                                       user_id: int, 
                                       max_jobs: int = 10) -> int:
        """Trigger immediate delivery for a specific user."""
        try:
            preferences = self.telegram_bot.user_db.get_user_preferences(user_id)
            if not preferences or not preferences.enabled:
                return 0
            
            # Get recent jobs
            jobs = await self._get_jobs_for_delivery(max_age_hours=48)  # Extended window for manual requests
            
            # Filter for user
            user_jobs = await self._filter_jobs_for_user(jobs, preferences)
            user_jobs = user_jobs[:max_jobs]
            
            if not user_jobs:
                return 0
            
            # Send jobs
            from telegram.ext import ContextTypes
            context = ContextTypes.DEFAULT_TYPE(self.telegram_bot.app)
            
            await self.telegram_bot._send_jobs_to_user(
                user_id=user_id,
                jobs=user_jobs,
                preferences=preferences,
                context=context
            )
            
            # Record delivery
            self.delivery_attempts.append(DeliveryAttempt(
                user_id=user_id,
                jobs_delivered=len(user_jobs),
                delivery_time=datetime.now(),
                success=True
            ))
            
            self.logger.info(f"Immediate delivery completed for user {user_id}: {len(user_jobs)} jobs")
            return len(user_jobs)
            
        except Exception as e:
            self.logger.error(f"Immediate delivery failed for user {user_id}: {e}")
            raise DataProcessingError(f"Immediate delivery failed: {e}")
    
    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get current delivery statistics."""
        return {
            "total_attempts": self.stats.total_attempts,
            "successful_deliveries": self.stats.successful_deliveries,
            "failed_deliveries": self.stats.failed_deliveries,
            "total_jobs_delivered": self.stats.total_jobs_delivered,
            "total_users_served": self.stats.total_users_served,
            "avg_jobs_per_user": self.stats.avg_jobs_per_user,
            "error_rate": self.stats.error_rate,
            "last_delivery_batch": self.stats.last_delivery_batch.isoformat() if self.stats.last_delivery_batch else None,
            "is_running": self.is_running,
            "recent_attempts": len([a for a in self.delivery_attempts 
                                  if a.delivery_time > datetime.now() - timedelta(hours=24)])
        }
    
    def get_user_delivery_history(self, user_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get delivery history for a specific user."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        user_attempts = [
            attempt for attempt in self.delivery_attempts
            if attempt.user_id == user_id and attempt.delivery_time > cutoff_date
        ]
        
        return [
            {
                "delivery_time": attempt.delivery_time.isoformat(),
                "jobs_delivered": attempt.jobs_delivered,
                "success": attempt.success,
                "error_message": attempt.error_message
            }
            for attempt in user_attempts
        ]