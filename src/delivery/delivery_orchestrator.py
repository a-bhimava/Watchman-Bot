"""
Delivery Orchestrator

Comprehensive orchestrator that integrates job discovery, scoring, and
Telegram delivery into a complete automated PM job notification system.
"""

import asyncio
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from delivery.telegram_bot import PMJobTelegramBot
from delivery.job_delivery_scheduler import JobDeliveryScheduler
from core.job_orchestrator import JobOrchestrator
from core.config_loader import PMProfile, SystemSettings, ConfigLoader
from storage.job_storage import JobStorage, create_default_storage_config
from monitoring.health_monitor import HealthMonitor
from processing.job_enricher import JobEnricher, EnrichedJobData

from utils.logger import get_logger, performance_tracker, log_context
from utils.error_handler import retry_on_failure, DataProcessingError


@dataclass
class DeliveryOrchestratorConfig:
    """Configuration for the delivery orchestrator."""
    # Telegram configuration
    telegram_bot_token: str
    
    # Discovery configuration
    discovery_interval_hours: int = 6
    enable_immediate_delivery: bool = True
    
    # Job processing
    min_job_quality_score: float = 60.0
    max_jobs_per_discovery: int = 100
    
    # Delivery optimization
    batch_delivery_enabled: bool = True
    delivery_retry_attempts: int = 3
    
    # System monitoring
    enable_health_monitoring: bool = True
    health_check_interval_minutes: int = 5


class DeliveryOrchestrator:
    """
    Master orchestrator for the complete PM Watchman system.
    
    Coordinates:
    - Automated job discovery (RSS + LinkedIn)
    - Job scoring and filtering
    - Telegram bot interactions
    - Scheduled delivery to users
    - System health monitoring
    - Error handling and recovery
    """
    
    def __init__(self, 
                 config: DeliveryOrchestratorConfig,
                 config_directory: str = "config",
                 data_directory: str = "data"):
        """Initialize delivery orchestrator."""
        self.config = config
        self.config_directory = config_directory
        self.data_directory = data_directory
        self.logger = get_logger(__name__)
        
        # Core components
        self.config_loader: Optional[ConfigLoader] = None
        self.pm_profile: Optional[PMProfile] = None
        self.system_settings: Optional[SystemSettings] = None
        
        self.job_storage: Optional[JobStorage] = None
        self.job_orchestrator: Optional[JobOrchestrator] = None
        self.telegram_bot: Optional[PMJobTelegramBot] = None
        self.delivery_scheduler: Optional[JobDeliveryScheduler] = None
        self.health_monitor: Optional[HealthMonitor] = None
        
        # Runtime state
        self.is_running = False
        self._shutdown_event = threading.Event()
        self._discovery_task = None
        
        # Statistics
        self.start_time: Optional[datetime] = None
        self.last_discovery: Optional[datetime] = None
        self.total_jobs_discovered = 0
        self.total_jobs_delivered = 0
    
    async def initialize(self) -> bool:
        """Initialize all system components."""
        try:
            with log_context(operation="orchestrator_initialization"):
                self.logger.info("Initializing PM Watchman Delivery Orchestrator")
                
                # Load configuration
                if not await self._load_configuration():
                    return False
                
                # Initialize storage
                if not await self._initialize_storage():
                    return False
                
                # Initialize job discovery
                if not await self._initialize_job_discovery():
                    return False
                
                # Initialize Telegram bot
                if not await self._initialize_telegram_bot():
                    return False
                
                # Initialize delivery scheduler
                if not await self._initialize_delivery_scheduler():
                    return False
                
                # Initialize health monitoring
                if not await self._initialize_health_monitoring():
                    return False
                
                self.logger.info("PM Watchman Delivery Orchestrator initialized successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to initialize orchestrator: {e}", exc_info=True)
            return False
    
    async def _load_configuration(self) -> bool:
        """Load system configuration."""
        try:
            self.config_loader = ConfigLoader(self.config_directory)
            
            self.pm_profile, self.system_settings, job_sources = self.config_loader.load_all_configs()
            
            self.logger.info("Configuration loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            return False
    
    async def _initialize_storage(self) -> bool:
        """Initialize job storage system."""
        try:
            storage_config = create_default_storage_config(self.data_directory)
            self.job_storage = JobStorage(storage_config)
            
            # Test storage
            stats = self.job_storage.get_storage_stats()
            self.logger.info(f"Storage initialized: {stats.total_jobs} jobs stored")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize storage: {e}")
            return False
    
    async def _initialize_job_discovery(self) -> bool:
        """Initialize job discovery orchestrator."""
        try:
            from core.job_orchestrator import create_default_discovery_config
            
            discovery_config = create_default_discovery_config(
                pm_profile=self.pm_profile,
                enable_linkedin=True,
                rss_feeds={}  # Add RSS feeds from config if needed
            )
            
            # Override some settings for delivery optimization
            discovery_config.max_jobs_per_source = self.config.max_jobs_per_discovery
            discovery_config.discovery_interval_hours = self.config.discovery_interval_hours
            
            self.job_orchestrator = JobOrchestrator(
                config=discovery_config,
                pm_profile=self.pm_profile,
                system_settings=self.system_settings
            )
            
            self.logger.info("Job discovery orchestrator initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize job discovery: {e}")
            return False
    
    async def _initialize_telegram_bot(self) -> bool:
        """Initialize Telegram bot."""
        try:
            from core.default_pm_scorer import DefaultPMScorer
            
            pm_scorer = DefaultPMScorer()
            
            self.telegram_bot = PMJobTelegramBot(
                bot_token=self.config.telegram_bot_token,
                job_storage=self.job_storage,
                pm_scorer=pm_scorer,
                pm_profile=self.pm_profile,
                system_settings=self.system_settings,
                db_path=f"{self.data_directory}/telegram/users.db"
            )
            
            self.logger.info("Telegram bot initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}")
            return False
    
    async def _initialize_delivery_scheduler(self) -> bool:
        """Initialize delivery scheduler."""
        try:
            self.delivery_scheduler = JobDeliveryScheduler(
                telegram_bot=self.telegram_bot,
                job_orchestrator=self.job_orchestrator,
                job_storage=self.job_storage
            )
            
            self.logger.info("Delivery scheduler initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize delivery scheduler: {e}")
            return False
    
    async def _initialize_health_monitoring(self) -> bool:
        """Initialize health monitoring."""
        if not self.config.enable_health_monitoring:
            self.logger.info("Health monitoring disabled by configuration")
            return True
        
        try:
            self.health_monitor = HealthMonitor(
                storage_directory=self.data_directory,
                check_interval_seconds=self.config.health_check_interval_minutes * 60
            )
            
            self.logger.info("Health monitoring initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize health monitoring: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the complete PM Watchman system."""
        if self.is_running:
            self.logger.warning("System is already running")
            return True
        
        try:
            with log_context(operation="system_startup"):
                self.logger.info("Starting PM Watchman delivery system")
                
                self.is_running = True
                self.start_time = datetime.now()
                self._shutdown_event.clear()
                
                # Start health monitoring first
                if self.health_monitor:
                    self.health_monitor.start_monitoring()
                    self.logger.info("Health monitoring started")
                
                # Start Telegram bot
                await self.telegram_bot.start_bot()
                self.logger.info("Telegram bot started")
                
                # Start delivery scheduler
                self.delivery_scheduler.start_scheduler()
                self.logger.info("Delivery scheduler started")
                
                # Start discovery loop
                self._discovery_task = asyncio.create_task(self._discovery_loop())
                self.logger.info("Discovery loop started")
                
                self.logger.info("PM Watchman delivery system started successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start system: {e}", exc_info=True)
            self.is_running = False
            return False
    
    async def stop(self):
        """Stop the complete PM Watchman system."""
        if not self.is_running:
            self.logger.info("System is not running")
            return
        
        try:
            with log_context(operation="system_shutdown"):
                self.logger.info("Stopping PM Watchman delivery system")
                
                self.is_running = False
                self._shutdown_event.set()
                
                # Stop discovery loop
                if self._discovery_task and not self._discovery_task.done():
                    self._discovery_task.cancel()
                    try:
                        await self._discovery_task
                    except asyncio.CancelledError:
                        pass
                
                # Stop delivery scheduler
                if self.delivery_scheduler:
                    self.delivery_scheduler.stop_scheduler()
                    self.logger.info("Delivery scheduler stopped")
                
                # Stop Telegram bot
                if self.telegram_bot:
                    await self.telegram_bot.stop_bot()
                    self.logger.info("Telegram bot stopped")
                
                # Stop health monitoring
                if self.health_monitor:
                    self.health_monitor.stop_monitoring()
                    self.logger.info("Health monitoring stopped")
                
                # Shutdown job orchestrator
                if self.job_orchestrator:
                    self.job_orchestrator.shutdown(wait_for_completion=False)
                    self.logger.info("Job orchestrator stopped")
                
                self.logger.info("PM Watchman delivery system stopped")
                
        except Exception as e:
            self.logger.error(f"Error during system shutdown: {e}", exc_info=True)
    
    async def _discovery_loop(self):
        """Main discovery loop that runs continuously."""
        self.logger.info(f"Starting discovery loop (interval: {self.config.discovery_interval_hours} hours)")
        
        while not self._shutdown_event.is_set():
            try:
                # Run job discovery
                await self._run_discovery_cycle()
                
                # Wait for next interval
                await asyncio.sleep(self.config.discovery_interval_hours * 3600)
                
            except asyncio.CancelledError:
                self.logger.info("Discovery loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in discovery loop: {e}", exc_info=True)
                # Wait shorter time on error
                await asyncio.sleep(600)  # 10 minutes
        
        self.logger.info("Discovery loop stopped")
    
    @performance_tracker("delivery_orchestrator", "discovery_cycle")
    async def _run_discovery_cycle(self):
        """Run a single discovery cycle."""
        cycle_start_time = datetime.now()
        
        with log_context(operation="discovery_cycle"):
            self.logger.info("Starting discovery cycle")
            
            try:
                # Run job discovery
                discovery_results = self.job_orchestrator.discover_jobs(
                    progress_callback=lambda msg, pct: self.logger.info(f"Discovery: {msg} ({pct:.0f}%)")
                )
                
                if not discovery_results.success:
                    self.logger.error(f"Discovery failed: {len(discovery_results.errors)} errors")
                    return
                
                # Update statistics
                self.last_discovery = cycle_start_time
                self.total_jobs_discovered += discovery_results.jobs_stored
                
                self.logger.info(f"Discovery cycle completed: {discovery_results.jobs_stored} jobs stored")
                
                # Record discovery in health monitor
                if self.health_monitor:
                    self.health_monitor.metrics_collector.record_discovery_run(discovery_results)
                
                # Trigger immediate delivery for high-priority jobs if enabled
                if self.config.enable_immediate_delivery:
                    await self._check_immediate_delivery_triggers(discovery_results)
                
            except Exception as e:
                self.logger.error(f"Discovery cycle failed: {e}", exc_info=True)
    
    async def _check_immediate_delivery_triggers(self, discovery_results):
        """Check if any jobs should trigger immediate delivery."""
        try:
            # Get recently discovered high-scoring jobs
            recent_jobs = self.job_storage.load_jobs(
                limit=20, 
                since=datetime.now() - timedelta(minutes=30)
            )
            
            if not recent_jobs:
                return
            
            # Find jobs with very high scores (90%+) for immediate delivery
            high_priority_jobs = []
            
            for job in recent_jobs:
                try:
                    score_result = self.telegram_bot.pm_scorer.score_job(
                        job, self.pm_profile, self.system_settings
                    )
                    
                    if score_result.total_score >= 90.0:  # Excellent jobs
                        from processing.job_enricher import EnrichedJobData
                        enriched = EnrichedJobData(original_job=job)
                        enriched.pm_score = score_result
                        high_priority_jobs.append(enriched)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to score job {job.id} for immediate delivery: {e}")
                    continue
            
            if high_priority_jobs:
                self.logger.info(f"Found {len(high_priority_jobs)} high-priority jobs for immediate delivery")
                
                # Get users who have immediate delivery enabled
                immediate_users = []
                all_users = self.telegram_bot.user_db.get_all_active_users()
                
                for user_id in all_users:
                    preferences = self.telegram_bot.user_db.get_user_preferences(user_id)
                    if (preferences and preferences.enabled and 
                        preferences.frequency == "immediate"):
                        immediate_users.append(user_id)
                
                # Send high-priority jobs immediately
                for user_id in immediate_users:
                    try:
                        await self.delivery_scheduler.trigger_immediate_delivery(
                            user_id=user_id,
                            max_jobs=3  # Limit immediate delivery to top 3 jobs
                        )
                    except Exception as e:
                        self.logger.error(f"Failed immediate delivery to user {user_id}: {e}")
                        continue
                
                if immediate_users:
                    self.logger.info(f"Immediate delivery completed for {len(immediate_users)} users")
            
        except Exception as e:
            self.logger.error(f"Failed to check immediate delivery triggers: {e}")
    
    async def trigger_manual_discovery(self) -> Dict[str, Any]:
        """Trigger manual discovery cycle."""
        if not self.job_orchestrator:
            return {"success": False, "error": "Job orchestrator not initialized"}
        
        try:
            self.logger.info("Manual discovery triggered")
            
            discovery_results = self.job_orchestrator.discover_jobs(
                run_id=f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            # Update stats
            if discovery_results.success:
                self.total_jobs_discovered += discovery_results.jobs_stored
                self.last_discovery = datetime.now()
            
            return {
                "success": discovery_results.success,
                "jobs_found": discovery_results.total_raw_jobs,
                "jobs_stored": discovery_results.jobs_stored,
                "duplicates": discovery_results.duplicates_detected,
                "duration_seconds": discovery_results.total_duration_seconds,
                "errors": discovery_results.errors
            }
            
        except Exception as e:
            self.logger.error(f"Manual discovery failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def trigger_manual_delivery(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Trigger manual delivery for specific user or all users."""
        if not self.delivery_scheduler:
            return {"success": False, "error": "Delivery scheduler not initialized"}
        
        try:
            if user_id:
                # Single user delivery
                jobs_delivered = await self.delivery_scheduler.trigger_immediate_delivery(user_id)
                
                return {
                    "success": True,
                    "user_id": user_id,
                    "jobs_delivered": jobs_delivered
                }
            else:
                # All users delivery (simulate daily batch)
                from delivery.job_delivery_scheduler import DeliveryWindow
                delivery_window = DeliveryWindow(hour=datetime.now().hour)
                
                await self.delivery_scheduler._execute_delivery_batch("manual", delivery_window)
                
                return {"success": True, "message": "Manual delivery batch completed"}
                
        except Exception as e:
            self.logger.error(f"Manual delivery failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        uptime = datetime.now() - self.start_time if self.start_time else timedelta(0)
        
        status = {
            "system": {
                "is_running": self.is_running,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "uptime_seconds": uptime.total_seconds(),
                "last_discovery": self.last_discovery.isoformat() if self.last_discovery else None
            },
            "statistics": {
                "total_jobs_discovered": self.total_jobs_discovered,
                "total_jobs_delivered": self.total_jobs_delivered
            },
            "components": {
                "telegram_bot": {
                    "running": self.telegram_bot.is_running() if self.telegram_bot else False,
                    "active_users": len(self.telegram_bot.user_db.get_all_active_users()) if self.telegram_bot else 0
                },
                "delivery_scheduler": {
                    "running": self.delivery_scheduler.is_running if self.delivery_scheduler else False,
                    "stats": self.delivery_scheduler.get_delivery_stats() if self.delivery_scheduler else {}
                },
                "job_orchestrator": {
                    "initialized": bool(self.job_orchestrator),
                    "status": self.job_orchestrator.get_discovery_status() if self.job_orchestrator else {}
                },
                "health_monitor": {
                    "running": self.health_monitor.is_monitoring if self.health_monitor else False,
                    "status": self.health_monitor.get_health_status() if self.health_monitor else {}
                }
            }
        }
        
        # Add storage stats
        if self.job_storage:
            storage_stats = self.job_storage.get_storage_stats()
            status["storage"] = {
                "total_jobs": storage_stats.total_jobs,
                "unique_jobs": storage_stats.unique_jobs,
                "duplicates_detected": storage_stats.duplicates_detected,
                "total_size_mb": storage_stats.total_size_mb,
                "files_count": storage_stats.files_count
            }
        
        return status
    
    def create_system_backup(self) -> str:
        """Create comprehensive system backup."""
        if not self.job_orchestrator:
            raise RuntimeError("System not initialized")
        
        backup_path = self.job_orchestrator.create_backup()
        self.logger.info(f"System backup created: {backup_path}")
        return backup_path


# Convenience functions for easy system management

async def create_and_start_delivery_system(
    telegram_bot_token: str,
    config_directory: str = "config",
    data_directory: str = "data",
    discovery_interval_hours: int = 6
) -> DeliveryOrchestrator:
    """Create and start the complete PM Watchman delivery system."""
    
    config = DeliveryOrchestratorConfig(
        telegram_bot_token=telegram_bot_token,
        discovery_interval_hours=discovery_interval_hours
    )
    
    orchestrator = DeliveryOrchestrator(
        config=config,
        config_directory=config_directory,
        data_directory=data_directory
    )
    
    # Initialize system
    if not await orchestrator.initialize():
        raise RuntimeError("Failed to initialize delivery system")
    
    # Start system
    if not await orchestrator.start():
        raise RuntimeError("Failed to start delivery system")
    
    return orchestrator


async def run_delivery_system_cli():
    """Run delivery system from command line interface."""
    import os
    
    # Get bot token from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set")
        return
    
    try:
        # Create and start system
        orchestrator = await create_and_start_delivery_system(bot_token)
        
        print("PM Watchman delivery system started successfully!")
        print("Press Ctrl+C to stop...")
        
        # Wait for shutdown signal
        try:
            while orchestrator.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutdown signal received...")
            
        await orchestrator.stop()
        print("PM Watchman delivery system stopped.")
        
    except Exception as e:
        print(f"Error: {e}")
        return