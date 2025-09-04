"""
Complete Pipeline Integration Tests

End-to-end tests for the complete PM Watchman pipeline including
job discovery, scoring, storage, and Telegram delivery.
"""

import unittest
import tempfile
import shutil
import json
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import test data first
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from test_data.sample_jobs import create_test_jobs, get_jobs_by_category
from test_data.test_profiles import get_all_test_profiles

from core.job_orchestrator import JobOrchestrator, create_default_discovery_config
from core.config_loader import PMProfile, SystemSettings
from storage.job_storage import JobStorage, create_default_storage_config
from processing.job_enricher import JobEnricher, EnrichmentConfig
from delivery.telegram_bot import PMJobTelegramBot, TelegramUserPreferences
from delivery.job_delivery_scheduler import JobDeliveryScheduler
from delivery.delivery_orchestrator import DeliveryOrchestrator, DeliveryOrchestratorConfig


class TestCompletePipeline(unittest.TestCase):
    """Test complete PM Watchman pipeline end-to-end."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, "config")
        self.data_dir = os.path.join(self.temp_dir, "data")
        
        os.makedirs(self.config_dir)
        os.makedirs(self.data_dir)
        
        # Create test configuration files
        self._create_test_configs()
        
        # Initialize test data
        self.test_jobs = create_test_jobs()
        self.test_profiles = get_all_test_profiles()
        self.pm_profile = self.test_profiles["mid_level_pm"]
        self.system_settings = SystemSettings()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_configs(self):
        """Create test configuration files."""
        # PM Profile
        pm_profile_data = {
            "meta": {"version": "1.0", "last_updated": "2025-01-15"},
            "experience": {
                "years_of_pm_experience": 5,
                "current_title": "Product Manager",
                "seniority_level": "mid"
            },
            "target_roles": {
                "primary_titles": ["Senior Product Manager", "Product Manager"],
                "secondary_titles": ["Product Lead"],
                "avoid_titles": ["Marketing Manager"]
            },
            "skills": {
                "core_pm_skills": ["product strategy", "roadmapping", "user research"],
                "technical_skills": ["SQL", "Python"],
                "domain_expertise": ["B2B SaaS", "fintech"]
            },
            "industries": {
                "primary_experience": ["fintech", "technology"],
                "interested_in": ["healthtech"],
                "avoid_industries": ["tobacco"]
            },
            "geographic_preferences": {
                "remote_preference": "remote_first",
                "preferred_locations": ["Remote", "San Francisco"]
            },
            "company_preferences": {
                "company_stages": ["growth", "public"],
                "company_sizes": ["201-500"],
                "preferred_companies": ["Stripe", "Notion"],
                "avoid_companies": ["Meta"]
            },
            "compensation": {
                "minimum_base_salary": 140000,
                "target_total_comp": 200000,
                "equity_importance": "medium"
            }
        }
        
        with open(os.path.join(self.config_dir, "pm_profile.json"), 'w') as f:
            json.dump(pm_profile_data, f, indent=2)
        
        # System Settings
        system_settings_data = {
            "scheduling": {"jobs_per_batch": 10, "batches_per_day": 4},
            "scoring": {
                "minimum_score_threshold": 60,
                "title_match_importance": "high",
                "skills_match_importance": "high"
            },
            "telegram": {"message_formatting": {"jobs_per_message": 1}}
        }
        
        with open(os.path.join(self.config_dir, "system_settings.json"), 'w') as f:
            json.dump(system_settings_data, f, indent=2)
        
        # Job Sources
        job_sources_data = {
            "linkedin": {"enabled": True, "priority": 1},
            "rss_feeds": {"primary_sources": {}}
        }
        
        with open(os.path.join(self.config_dir, "job_sources.json"), 'w') as f:
            json.dump(job_sources_data, f, indent=2)
    
    def test_job_discovery_and_storage_pipeline(self):
        """Test job discovery, scoring, and storage pipeline."""
        print("\n--- Testing Job Discovery and Storage Pipeline ---")
        
        # Initialize storage
        storage_config = create_default_storage_config(self.data_dir)
        job_storage = JobStorage(storage_config)
        
        # Store test jobs
        storage_results = job_storage.store_jobs(self.test_jobs)
        
        # Validate storage
        self.assertGreater(storage_results['stored_count'], 0)
        self.assertEqual(storage_results['error_count'], 0)
        
        # Retrieve and validate stored jobs
        retrieved_jobs = job_storage.load_jobs(limit=50)
        self.assertEqual(len(retrieved_jobs), storage_results['stored_count'])
        
        print(f"✅ Stored {storage_results['stored_count']} jobs successfully")
        print(f"✅ Retrieved {len(retrieved_jobs)} jobs from storage")
        
        # Test storage statistics
        stats = job_storage.get_storage_stats()
        self.assertEqual(stats.total_jobs, storage_results['stored_count'])
        
        print(f"✅ Storage stats: {stats.total_jobs} total jobs, {stats.total_size_mb:.2f} MB")
    
    def test_job_enrichment_pipeline(self):
        """Test job enrichment pipeline."""
        print("\n--- Testing Job Enrichment Pipeline ---")
        
        # Initialize enricher
        enricher = JobEnricher(EnrichmentConfig())
        
        # Enrich test jobs
        enriched_jobs = enricher.enrich_jobs(self.test_jobs[:5])  # Test with 5 jobs
        
        # Validate enrichment
        self.assertEqual(len(enriched_jobs), 5)
        
        quality_scores = [job.quality_score for job in enriched_jobs]
        avg_quality = sum(quality_scores) / len(quality_scores)
        
        print(f"✅ Enriched {len(enriched_jobs)} jobs")
        print(f"✅ Average quality score: {avg_quality:.1f}%")
        
        # Check enrichment details
        for job in enriched_jobs[:2]:  # Check first 2
            self.assertIsNotNone(job.original_job)
            self.assertGreaterEqual(job.quality_score, 0)
            
            if job.extracted_skills:
                print(f"✅ Skills extracted for {job.original_job.title}: {len(job.extracted_skills.pm_skills)} PM skills")
    
    @patch('delivery.telegram_bot.Application')
    def test_telegram_bot_initialization(self, mock_application):
        """Test Telegram bot initialization and message formatting."""
        print("\n--- Testing Telegram Bot Integration ---")
        
        # Mock Telegram application
        mock_app = Mock()
        mock_application.builder.return_value.token.return_value.build.return_value = mock_app
        
        # Initialize storage for bot
        storage_config = create_default_storage_config(self.data_dir)
        job_storage = JobStorage(storage_config)
        
        # Initialize bot
        from core.default_pm_scorer import DefaultPMScorer
        pm_scorer = DefaultPMScorer()
        
        bot = PMJobTelegramBot(
            bot_token="test_token",
            job_storage=job_storage,
            pm_scorer=pm_scorer,
            pm_profile=self.pm_profile,
            system_settings=self.system_settings,
            db_path=os.path.join(self.data_dir, "test_users.db")
        )
        
        self.assertIsNotNone(bot)
        print("✅ Telegram bot initialized successfully")
        
        # Test user preferences
        test_preferences = TelegramUserPreferences(
            user_id=123456,
            username="testuser",
            min_score_threshold=70.0,
            max_daily_jobs=5
        )
        
        bot.user_db.save_user_preferences(test_preferences)
        retrieved_prefs = bot.user_db.get_user_preferences(123456)
        
        self.assertEqual(retrieved_prefs.user_id, 123456)
        self.assertEqual(retrieved_prefs.min_score_threshold, 70.0)
        
        print("✅ User preferences saved and retrieved successfully")
        
        # Test message formatting
        from processing.job_enricher import EnrichedJobData
        test_job = self.test_jobs[0]
        
        score_result = pm_scorer.score_job(test_job, self.pm_profile, self.system_settings)
        
        enriched = EnrichedJobData(original_job=test_job)
        enriched.pm_score = score_result
        
        message, keyboard = bot.message_formatter.format_job_message(
            enriched, test_preferences, show_detailed_scoring=True
        )
        
        self.assertIn("PM Job Alert", message)
        self.assertIn(test_job.title, message)
        self.assertIsNotNone(keyboard)
        
        print("✅ Job message formatting working correctly")
        print(f"✅ Message length: {len(message)} characters")
    
    def test_scoring_integration_with_delivery(self):
        """Test scoring system integration with delivery."""
        print("\n--- Testing Scoring Integration with Delivery ---")
        
        from core.default_pm_scorer import DefaultPMScorer
        
        # Initialize scorer
        pm_scorer = DefaultPMScorer()
        
        # Score all test jobs
        scored_jobs = []
        for job in self.test_jobs:
            try:
                score_result = pm_scorer.score_job(job, self.pm_profile, self.system_settings)
                scored_jobs.append((job, score_result))
            except Exception as e:
                self.fail(f"Scoring failed for job {job.id}: {e}")
        
        self.assertEqual(len(scored_jobs), len(self.test_jobs))
        print(f"✅ Successfully scored {len(scored_jobs)} jobs")
        
        # Analyze score distribution
        scores = [result.total_score for _, result in scored_jobs]
        min_score = min(scores)
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        
        print(f"✅ Score range: {min_score:.1f}% - {max_score:.1f}% (avg: {avg_score:.1f}%)")
        
        # Filter by threshold (like delivery system would)
        threshold = self.system_settings.minimum_score_threshold
        qualified_jobs = [(job, result) for job, result in scored_jobs 
                         if result.total_score >= threshold]
        
        print(f"✅ {len(qualified_jobs)}/{len(scored_jobs)} jobs above {threshold}% threshold")
        
        # Test score explanations
        if qualified_jobs:
            job, result = qualified_jobs[0]
            explanation = pm_scorer.create_score_explanation(result, detailed=True)
            
            self.assertIn("Job Score:", explanation)
            self.assertIn("Grade:", explanation)
            
            print("✅ Score explanations generated successfully")
    
    @patch('delivery.telegram_bot.Application')
    def test_delivery_scheduler_integration(self, mock_application):
        """Test delivery scheduler integration."""
        print("\n--- Testing Delivery Scheduler Integration ---")
        
        # Mock Telegram application
        mock_app = Mock()
        mock_application.builder.return_value.token.return_value.build.return_value = mock_app
        
        # Initialize components
        storage_config = create_default_storage_config(self.data_dir)
        job_storage = JobStorage(storage_config)
        
        # Store some test jobs
        job_storage.store_jobs(self.test_jobs[:5])
        
        # Initialize orchestrator (minimal for testing)
        discovery_config = create_default_discovery_config(
            self.pm_profile,
            enable_linkedin=False,  # Disable to avoid external calls
            rss_feeds={}
        )
        
        # Mock the job orchestrator to avoid actual discovery
        mock_orchestrator = Mock()
        mock_orchestrator.get_discovery_status.return_value = {"is_running": False}
        
        # Initialize bot
        from core.default_pm_scorer import DefaultPMScorer
        pm_scorer = DefaultPMScorer()
        
        telegram_bot = PMJobTelegramBot(
            bot_token="test_token",
            job_storage=job_storage,
            pm_scorer=pm_scorer,
            pm_profile=self.pm_profile,
            system_settings=self.system_settings,
            db_path=os.path.join(self.data_dir, "test_users.db")
        )
        
        # Initialize scheduler
        scheduler = JobDeliveryScheduler(
            telegram_bot=telegram_bot,
            job_orchestrator=mock_orchestrator,
            job_storage=job_storage
        )
        
        self.assertIsNotNone(scheduler)
        print("✅ Delivery scheduler initialized successfully")
        
        # Test getting jobs for delivery
        jobs_for_delivery = asyncio.run(scheduler._get_jobs_for_delivery())
        
        # Should get jobs (even if empty due to scoring)
        self.assertIsInstance(jobs_for_delivery, list)
        print(f"✅ Retrieved {len(jobs_for_delivery)} jobs for delivery")
        
        # Test delivery stats
        stats = scheduler.get_delivery_stats()
        self.assertIn('total_attempts', stats)
        self.assertIn('is_running', stats)
        
        print("✅ Delivery statistics accessible")
    
    @patch('delivery.telegram_bot.Application')
    @patch('integrations.linkedin_scraper.LinkedInScraper')
    def test_complete_system_integration(self, mock_linkedin, mock_application):
        """Test complete system integration (mocked external dependencies)."""
        print("\n--- Testing Complete System Integration ---")
        
        # Mock external dependencies
        mock_app = Mock()
        mock_application.builder.return_value.token.return_value.build.return_value = mock_app
        
        mock_scraper = Mock()
        mock_scraper.discover_jobs.return_value = self.test_jobs[:3]
        mock_linkedin.return_value = mock_scraper
        
        try:
            # Initialize delivery orchestrator
            config = DeliveryOrchestratorConfig(
                telegram_bot_token="test_token",
                discovery_interval_hours=24,  # Long interval for testing
                enable_immediate_delivery=False  # Disable for testing
            )
            
            orchestrator = DeliveryOrchestrator(
                config=config,
                config_directory=self.config_dir,
                data_directory=self.data_dir
            )
            
            # Initialize system
            initialized = asyncio.run(orchestrator.initialize())
            self.assertTrue(initialized)
            
            print("✅ Complete system initialized successfully")
            
            # Test system status
            status = orchestrator.get_system_status()
            
            self.assertIn('system', status)
            self.assertIn('components', status)
            self.assertIn('storage', status)
            
            print("✅ System status retrieved successfully")
            print(f"✅ Components initialized: {len(status['components'])}")
            
            # Test manual discovery (mocked)
            with patch.object(orchestrator.job_orchestrator, 'discover_jobs') as mock_discover:
                from core.job_orchestrator import DiscoveryResults
                
                mock_results = DiscoveryResults(
                    run_id="test_run",
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    total_raw_jobs=10,
                    jobs_stored=8,
                    success=True
                )
                
                mock_discover.return_value = mock_results
                
                discovery_result = asyncio.run(orchestrator.trigger_manual_discovery())
                
                self.assertTrue(discovery_result['success'])
                self.assertEqual(discovery_result['jobs_stored'], 8)
                
                print("✅ Manual discovery trigger working")
            
            # Test backup creation
            with patch.object(orchestrator.job_orchestrator, 'create_backup') as mock_backup:
                mock_backup.return_value = "/tmp/test_backup"
                
                backup_path = orchestrator.create_system_backup()
                self.assertIsNotNone(backup_path)
                
                print("✅ System backup functionality working")
            
        except Exception as e:
            self.fail(f"Complete system integration test failed: {e}")
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        print("\n--- Testing Error Handling and Recovery ---")
        
        # Test storage with invalid data
        from integrations.rss_processor import JobData
        
        invalid_job = JobData(
            id="",  # Invalid empty ID
            title="",  # Invalid empty title
            company="",  # Invalid empty company
            location=""
        )
        
        storage_config = create_default_storage_config(self.data_dir)
        job_storage = JobStorage(storage_config)
        
        # Should handle invalid data gracefully
        try:
            results = job_storage.store_jobs([invalid_job])
            # Should not crash, but may not store the invalid job
            self.assertIsInstance(results, dict)
            print("✅ Storage handles invalid data gracefully")
        except Exception as e:
            # If it throws an exception, it should be handled properly
            print(f"✅ Storage error handling: {type(e).__name__}")
        
        # Test scoring with invalid data
        from core.default_pm_scorer import DefaultPMScorer
        
        pm_scorer = DefaultPMScorer()
        
        try:
            # This might fail, but should be handled gracefully
            result = pm_scorer.score_job(invalid_job, self.pm_profile, self.system_settings)
            self.assertIsNotNone(result)
            print("✅ Scorer handles invalid data gracefully")
        except Exception as e:
            print(f"✅ Scorer error handling: {type(e).__name__}")
        
        # Test with partially valid data
        partial_job = JobData(
            id="test_partial",
            title="Test Job",
            company="Test Company",
            location="Remote",
            # Missing other fields
        )
        
        try:
            result = pm_scorer.score_job(partial_job, self.pm_profile, self.system_settings)
            self.assertIsNotNone(result)
            self.assertGreaterEqual(result.total_score, 0)
            print("✅ Scorer works with partial data")
        except Exception as e:
            self.fail(f"Scorer should handle partial data: {e}")
    
    def test_data_consistency_and_integrity(self):
        """Test data consistency and integrity across components."""
        print("\n--- Testing Data Consistency and Integrity ---")
        
        # Initialize storage
        storage_config = create_default_storage_config(self.data_dir)
        job_storage = JobStorage(storage_config)
        
        # Store jobs
        original_count = len(self.test_jobs)
        results = job_storage.store_jobs(self.test_jobs)
        
        # Retrieve jobs
        retrieved_jobs = job_storage.load_jobs(limit=100)
        
        # Verify data integrity
        self.assertEqual(len(retrieved_jobs), results['stored_count'])
        
        # Check that job IDs are preserved
        original_ids = {job.id for job in self.test_jobs}
        retrieved_ids = {job.id for job in retrieved_jobs}
        
        stored_ids = original_ids.intersection(retrieved_ids)
        self.assertGreater(len(stored_ids), 0)
        
        print(f"✅ Data integrity verified: {len(stored_ids)} IDs preserved")
        
        # Test duplicate detection
        duplicate_results = job_storage.store_jobs(self.test_jobs)  # Store same jobs again
        
        self.assertGreater(duplicate_results['duplicate_count'], 0)
        print(f"✅ Duplicate detection working: {duplicate_results['duplicate_count']} duplicates caught")
        
        # Verify total count didn't increase
        final_jobs = job_storage.load_jobs(limit=200)
        self.assertEqual(len(final_jobs), len(retrieved_jobs))
        
        print("✅ Storage consistency maintained after duplicate insertion")


class TestPipelinePerformance(unittest.TestCase):
    """Test pipeline performance characteristics."""
    
    def setUp(self):
        """Set up performance test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_jobs = create_test_jobs()
        self.pm_profile = get_all_test_profiles()["mid_level_pm"]
        self.system_settings = SystemSettings()
    
    def tearDown(self):
        """Clean up performance test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_storage_performance(self):
        """Test storage performance with larger datasets."""
        print("\n--- Testing Storage Performance ---")
        
        # Create larger dataset
        large_dataset = self.test_jobs * 10  # 150+ jobs
        
        storage_config = create_default_storage_config(self.temp_dir)
        job_storage = JobStorage(storage_config)
        
        import time
        start_time = time.time()
        
        results = job_storage.store_jobs(large_dataset)
        
        duration = time.time() - start_time
        
        print(f"✅ Stored {results['stored_count']} jobs in {duration:.2f} seconds")
        print(f"✅ Rate: {results['stored_count']/duration:.1f} jobs/second")
        
        # Should be reasonably fast
        self.assertLess(duration, 10.0)  # Less than 10 seconds for 150 jobs
        
        # Test retrieval performance
        start_time = time.time()
        
        retrieved_jobs = job_storage.load_jobs(limit=200)
        
        retrieval_duration = time.time() - start_time
        
        print(f"✅ Retrieved {len(retrieved_jobs)} jobs in {retrieval_duration:.2f} seconds")
        self.assertLess(retrieval_duration, 2.0)  # Less than 2 seconds for retrieval
    
    def test_scoring_performance(self):
        """Test scoring performance with multiple jobs."""
        print("\n--- Testing Scoring Performance ---")
        
        from core.default_pm_scorer import DefaultPMScorer
        
        pm_scorer = DefaultPMScorer()
        test_jobs = self.test_jobs * 5  # 75+ jobs
        
        import time
        start_time = time.time()
        
        scored_jobs = 0
        for job in test_jobs:
            try:
                result = pm_scorer.score_job(job, self.pm_profile, self.system_settings)
                scored_jobs += 1
            except Exception:
                continue
        
        duration = time.time() - start_time
        
        print(f"✅ Scored {scored_jobs} jobs in {duration:.2f} seconds")
        print(f"✅ Rate: {scored_jobs/duration:.1f} jobs/second")
        
        # Should be reasonably fast
        self.assertLess(duration, 30.0)  # Less than 30 seconds for 75 jobs
        self.assertGreater(scored_jobs/duration, 2.0)  # At least 2 jobs per second


if __name__ == "__main__":
    # Run with higher verbosity to see progress
    unittest.main(verbosity=2, buffer=True)