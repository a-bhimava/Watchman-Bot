"""
PM Watchman - Main Application Entry Point

Automated Product Manager job discovery, scoring, and delivery system.
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime
import signal
import json

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_loader import ConfigLoader
from core.job_orchestrator import JobOrchestrator, create_default_discovery_config, run_scheduled_discovery
from monitoring.health_monitor import HealthMonitor, create_webhook_alert_handler
from utils.logger import initialize_logging, get_logger
from integrations.linkedin_scraper import create_pm_search_config


class PMWatchman:
    """Main PM Watchman application class."""
    
    def __init__(self, config_directory: str = "config", data_directory: str = "data"):
        """Initialize PM Watchman."""
        self.config_directory = config_directory
        self.data_directory = data_directory
        self.logger = None
        
        # Application components
        self.config_loader = None
        self.orchestrator = None
        self.health_monitor = None
        
        # Runtime state
        self.is_running = False
        self._shutdown_requested = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\nShutdown signal received. Gracefully shutting down...")
        self._shutdown_requested = True
        if self.is_running:
            self.shutdown()
    
    def initialize(self, log_level: str = "INFO", enable_console: bool = True):
        """Initialize the application."""
        try:
            # Create directories
            os.makedirs(self.config_directory, exist_ok=True)
            os.makedirs(self.data_directory, exist_ok=True)
            
            # Initialize logging
            log_dir = os.path.join(self.data_directory, "logs")
            initialize_logging(log_dir=log_dir, log_level=log_level, enable_console=enable_console)
            self.logger = get_logger(__name__)
            
            self.logger.info("PM Watchman initializing...")
            
            # Load configuration
            self.config_loader = ConfigLoader(self.config_directory)
            
            try:
                pm_profile, system_settings, job_sources = self.config_loader.load_all_configs()
                self.logger.info("Configuration loaded successfully")
            except FileNotFoundError as e:
                self.logger.error(f"Configuration files not found: {e}")
                self.logger.info("Please run 'python main.py init' to create default configuration")
                return False
            
            # Extract LinkedIn enabled status from job_sources configuration
            linkedin_enabled = False  # Default to disabled for optimization
            
            # Check for LinkedIn configuration
            job_sources_dict = job_sources.__dict__ if hasattr(job_sources, '__dict__') else job_sources
            if 'linkedin' in job_sources_dict:
                linkedin_data = job_sources_dict.get('linkedin', {})
                linkedin_enabled = linkedin_data.get('enabled', False)
            
            # Extract RSS feeds configuration
            rss_feeds = {}
            if 'rss_feeds' in job_sources_dict:
                rss_data = job_sources_dict.get('rss_feeds', {})
                if isinstance(rss_data, dict) and rss_data.get('enabled', False):
                    feeds = rss_data.get('feeds', {})
                    for feed_name, feed_config in feeds.items():
                        if isinstance(feed_config, dict) and feed_config.get('enabled', False):
                            rss_feeds[feed_name] = feed_config.get('url', '')

            # Create discovery configuration
            discovery_config = create_default_discovery_config(
                pm_profile=pm_profile,
                enable_linkedin=linkedin_enabled,
                rss_feeds=rss_feeds
            )
            
            # Initialize orchestrator
            self.orchestrator = JobOrchestrator(
                config=discovery_config,
                pm_profile=pm_profile,
                system_settings=system_settings
            )
            
            # Initialize health monitoring
            alert_handlers = []
            
            # Add webhook alerting if configured
            webhook_url = os.getenv('WATCHMAN_WEBHOOK_URL')
            if webhook_url:
                alert_handlers.append(create_webhook_alert_handler(webhook_url))
            
            self.health_monitor = HealthMonitor(
                storage_directory=self.data_directory,
                check_interval_seconds=300,  # 5 minutes
                alert_handlers=alert_handlers
            )
            
            self.logger.info("PM Watchman initialized successfully")
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Initialization failed: {e}", exc_info=True)
            else:
                print(f"Initialization failed: {e}")
            return False
    
    def run_discovery(self, run_id: str = None) -> bool:
        """Run a single job discovery cycle."""
        if not self.orchestrator:
            self.logger.error("Orchestrator not initialized")
            return False
        
        def progress_callback(message: str, percentage: float):
            self.logger.info(f"Discovery progress: {message} ({percentage:.0f}%)")
        
        try:
            self.logger.info("Starting job discovery...")
            results = self.orchestrator.discover_jobs(
                run_id=run_id,
                progress_callback=progress_callback
            )
            
            # Record results in health monitor
            if self.health_monitor:
                self.health_monitor.metrics_collector.record_discovery_run(results)
            
            if results.success:
                self.logger.info(f"Discovery completed successfully: {results.jobs_stored} jobs stored")
                return True
            else:
                self.logger.error(f"Discovery failed: {len(results.errors)} errors")
                return False
                
        except Exception as e:
            self.logger.error(f"Discovery run failed: {e}", exc_info=True)
            return False
    
    def run_scheduled(self, interval_hours: int = 6):
        """Run scheduled job discovery."""
        if not self.orchestrator:
            self.logger.error("Orchestrator not initialized")
            return
        
        self.is_running = True
        self.logger.info(f"Starting scheduled discovery (every {interval_hours} hours)")
        
        # Start health monitoring
        if self.health_monitor:
            self.health_monitor.start_monitoring()
        
        try:
            # Run the scheduled discovery loop
            asyncio.run(run_scheduled_discovery(
                orchestrator=self.orchestrator,
                interval_hours=interval_hours,
                progress_callback=lambda msg, pct: self.logger.info(f"{msg} ({pct:.0f}%)")
            ))
            
        except KeyboardInterrupt:
            self.logger.info("Scheduled discovery interrupted by user")
        except Exception as e:
            self.logger.error(f"Scheduled discovery failed: {e}", exc_info=True)
        finally:
            self.is_running = False
            self.shutdown()
    
    def get_status(self) -> dict:
        """Get current application status."""
        status = {
            'timestamp': datetime.now().isoformat(),
            'is_running': self.is_running,
            'components': {
                'orchestrator': bool(self.orchestrator),
                'health_monitor': bool(self.health_monitor),
                'config_loader': bool(self.config_loader)
            }
        }
        
        # Add orchestrator status
        if self.orchestrator:
            status['discovery'] = self.orchestrator.get_discovery_status()
        
        # Add health status
        if self.health_monitor:
            status['health'] = self.health_monitor.get_health_status()
        
        return status
    
    def create_backup(self) -> str:
        """Create system backup."""
        if not self.orchestrator:
            raise RuntimeError("Orchestrator not initialized")
        
        backup_path = self.orchestrator.create_backup()
        self.logger.info(f"Backup created: {backup_path}")
        return backup_path
    
    def shutdown(self):
        """Graceful shutdown."""
        if not self.is_running and not any([self.orchestrator, self.health_monitor]):
            return
        
        self.logger.info("Shutting down PM Watchman...")
        
        # Stop health monitoring
        if self.health_monitor:
            self.health_monitor.stop_monitoring()
        
        # Shutdown orchestrator
        if self.orchestrator:
            self.orchestrator.shutdown(wait_for_completion=False)
        
        self.is_running = False
        self.logger.info("PM Watchman shutdown complete")


def init_config_files(config_dir: str):
    """Initialize default configuration files."""
    print(f"Initializing configuration files in {config_dir}...")
    
    os.makedirs(config_dir, exist_ok=True)
    
    # Default PM Profile
    pm_profile = {
        "meta": {
            "version": "1.0",
            "last_updated": datetime.now().strftime("%Y-%m-%d")
        },
        "experience": {
            "years_of_pm_experience": 5,
            "current_title": "Product Manager",
            "seniority_level": "mid"
        },
        "target_roles": {
            "primary_titles": ["Senior Product Manager", "Product Manager"],
            "secondary_titles": ["Product Lead", "Principal PM"],
            "avoid_titles": ["Marketing Manager", "Sales Manager"]
        },
        "skills": {
            "core_pm_skills": [
                "product strategy", "roadmapping", "user research", 
                "data analysis", "A/B testing", "stakeholder management"
            ],
            "technical_skills": ["SQL", "Python", "Figma", "Jira"],
            "domain_expertise": ["B2B SaaS", "fintech", "platform products"]
        },
        "industries": {
            "primary_experience": ["fintech", "SaaS", "technology"],
            "interested_in": ["healthtech", "climate tech"],
            "avoid_industries": ["tobacco", "gambling"]
        },
        "geographic_preferences": {
            "remote_preference": "remote_first",
            "preferred_locations": ["Remote", "San Francisco", "New York"]
        },
        "company_preferences": {
            "company_stages": ["growth", "public"],
            "company_sizes": ["201-500", "501-1000"],
            "preferred_companies": ["Stripe", "Notion", "Linear"],
            "avoid_companies": ["Meta", "TikTok"]
        },
        "compensation": {
            "minimum_base_salary": 140000,
            "target_total_comp": 200000,
            "equity_importance": "medium"
        }
    }
    
    # System Settings
    system_settings = {
        "scheduling": {
            "jobs_per_batch": 10,
            "batches_per_day": 4,
            "hours_between_batches": 6
        },
        "scoring": {
            "minimum_score_threshold": 60,
            "title_match_importance": "high",
            "skills_match_importance": "high",
            "experience_match_importance": "medium",
            "industry_match_importance": "medium",
            "company_match_importance": "low"
        },
        "telegram": {
            "message_formatting": {
                "jobs_per_message": 1,
                "include_description_preview": True
            }
        }
    }
    
    # Job Sources
    job_sources = {
        "linkedin": {
            "enabled": True,
            "priority": 1
        },
        "rss_feeds": {
            "primary_sources": {
                "pm_jobs_feed": {
                    "url": "https://example.com/pm-jobs.rss",
                    "enabled": True
                }
            }
        }
    }
    
    # Write configuration files
    configs = [
        ("pm_profile.json", pm_profile),
        ("system_settings.json", system_settings),
        ("job_sources.json", job_sources)
    ]
    
    for filename, config_data in configs:
        file_path = os.path.join(config_dir, filename)
        with open(file_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"Created: {file_path}")
    
    print("\nConfiguration files created successfully!")
    print(f"Please edit the files in {config_dir} to match your preferences.")


def main():
    parser = argparse.ArgumentParser(
        description="PM Watchman - Automated PM job discovery and scoring system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py init                    # Initialize default config files
  python main.py discover                # Run single discovery cycle
  python main.py run                     # Run scheduled discovery (default: every 6 hours)
  python main.py run --interval 4        # Run scheduled discovery every 4 hours
  python main.py status                  # Get current system status
  python main.py backup                  # Create system backup
        """
    )
    
    parser.add_argument(
        "command",
        choices=["init", "discover", "run", "telegram", "status", "backup"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Configuration directory (default: config)"
    )
    
    parser.add_argument(
        "--data-dir", 
        default="data",
        help="Data directory (default: data)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=6,
        help="Discovery interval in hours (default: 6)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Disable console logging"
    )
    
    parser.add_argument(
        "--telegram-token",
        help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)"
    )
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_config_files(args.config_dir)
        return 0
    
    # Initialize application
    app = PMWatchman(config_directory=args.config_dir, data_directory=args.data_dir)
    
    if not app.initialize(log_level=args.log_level, enable_console=not args.no_console):
        print("Failed to initialize PM Watchman")
        return 1
    
    try:
        if args.command == "discover":
            success = app.run_discovery()
            return 0 if success else 1
            
        elif args.command == "run":
            app.run_scheduled(interval_hours=args.interval)
            return 0
            
        elif args.command == "status":
            status = app.get_status()
            print(json.dumps(status, indent=2, default=str))
            return 0
            
        elif args.command == "telegram":
            # Run full delivery system with Telegram
            bot_token = args.telegram_token or os.getenv("TELEGRAM_BOT_TOKEN")
            if not bot_token:
                print("Error: Telegram bot token required. Use --telegram-token or set TELEGRAM_BOT_TOKEN env var")
                return 1
            
            try:
                from delivery.delivery_orchestrator import run_delivery_system_cli
                import asyncio
                
                # Set token in environment for the CLI function
                os.environ["TELEGRAM_BOT_TOKEN"] = bot_token
                
                print("Starting PM Watchman with Telegram delivery...")
                
                # Run the async delivery system
                asyncio.run(run_delivery_system_cli())
                return 0
                
            except Exception as e:
                print(f"Telegram delivery failed: {e}")
                return 1
        
        elif args.command == "backup":
            backup_path = app.create_backup()
            print(f"Backup created: {backup_path}")
            return 0
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    finally:
        if 'app' in locals():
            app.shutdown()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)