"""
End-to-End Job Scoring Integration Tests

Tests the complete job scoring pipeline including:
- Configuration loading
- Job data processing  
- Complete scoring workflow
- Score explanations and formatting
- System integration points
"""

import unittest
import sys
import os
import tempfile
import json
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.config_loader import ConfigLoader, PMProfile, SystemSettings
from core.default_pm_scorer import DefaultPMScorer
from integrations.rss_processor import JobData
from utils.logger import initialize_logging

# Import test data
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from test_data.sample_jobs import create_test_jobs, get_jobs_by_category
from test_data.test_profiles import get_all_test_profiles


class TestEndToEndJobScoring(unittest.TestCase):
    """Integration tests for complete job scoring workflow."""
    
    def setUp(self):
        """Set up test environment with temporary config files."""
        # Create temporary directory for test configs
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize logging for tests
        initialize_logging(
            log_dir=os.path.join(self.temp_dir, "logs"),
            log_level="INFO",
            enable_console=False
        )
        
        # Create test configuration files
        self._create_test_config_files()
        
        # Initialize components
        self.config_loader = ConfigLoader(self.temp_dir)
        self.scoring_engine = DefaultPMScorer()
        
        # Load test data
        self.test_jobs = create_test_jobs()
        self.jobs_by_category = get_jobs_by_category()
        
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_config_files(self):
        """Create temporary configuration files for testing."""
        # PM Profile
        pm_profile_data = {
            "meta": {
                "version": "1.0",
                "last_updated": "2025-01-15"
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
        
        with open(os.path.join(self.temp_dir, "pm_profile.json"), 'w') as f:
            json.dump(pm_profile_data, f, indent=2)
        
        # System Settings
        system_settings_data = {
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
        
        with open(os.path.join(self.temp_dir, "system_settings.json"), 'w') as f:
            json.dump(system_settings_data, f, indent=2)
        
        # Job Sources
        job_sources_data = {
            "linkedin": {
                "enabled": True,
                "priority": 1
            },
            "rss_feeds": {
                "primary_sources": {
                    "test_feed": {
                        "url": "https://example.com/feed.rss",
                        "enabled": True
                    }
                }
            }
        }
        
        with open(os.path.join(self.temp_dir, "job_sources.json"), 'w') as f:
            json.dump(job_sources_data, f, indent=2)
    
    def test_configuration_loading_integration(self):
        """Test that configuration loading integrates properly with scoring."""
        # Load all configurations
        pm_profile, system_settings, job_sources = self.config_loader.load_all_configs()
        
        # Validate loaded configurations
        self.assertIsInstance(pm_profile, PMProfile)
        self.assertIsInstance(system_settings, SystemSettings)
        self.assertEqual(pm_profile.years_of_pm_experience, 5)
        self.assertEqual(system_settings.minimum_score_threshold, 60)
        
        # Test scoring with loaded config
        test_job = self.jobs_by_category["perfect_match"][0]
        result = self.scoring_engine.score_job(test_job, pm_profile, system_settings)
        
        self.assertIsNotNone(result)
        self.assertGreater(result.total_score, 0)
    
    def test_complete_scoring_workflow(self):
        """Test complete scoring workflow from job data to final score."""
        pm_profile = self.config_loader.load_pm_profile()
        system_settings = self.config_loader.load_system_settings()
        
        # Test with different job categories
        for category, jobs in self.jobs_by_category.items():
            if not jobs:  # Skip empty categories
                continue
                
            for job in jobs[:1]:  # Test first job in each category
                with self.subTest(category=category, job_id=job.id):
                    result = self.scoring_engine.score_job(job, pm_profile, system_settings)
                    
                    # Validate result structure
                    self.assertIsNotNone(result.job_id)
                    self.assertIsInstance(result.total_score, (int, float))
                    self.assertGreaterEqual(len(result.scoring_reasons), 5)  # At least 5 scorers
                    
                    # Validate score explanation
                    explanation = self.scoring_engine.create_score_explanation(result)
                    self.assertIn("Job Score:", explanation)
                    self.assertIn("%", explanation)
    
    def test_batch_job_processing(self):
        """Test processing multiple jobs in batch."""
        pm_profile = self.config_loader.load_pm_profile()
        system_settings = self.config_loader.load_system_settings()
        
        # Process batch of jobs
        test_jobs_batch = self.test_jobs[:10]  # First 10 jobs
        results = self.scoring_engine.score_jobs(test_jobs_batch, pm_profile, system_settings)
        
        # Validate batch results
        self.assertEqual(len(results), len(test_jobs_batch))
        
        for i, result in enumerate(results):
            self.assertEqual(result.job_id, test_jobs_batch[i].id)
            self.assertGreaterEqual(result.total_score, 0.0)
    
    def test_scoring_consistency(self):
        """Test that scoring is consistent across multiple runs."""
        pm_profile = self.config_loader.load_pm_profile()
        system_settings = self.config_loader.load_system_settings()
        test_job = self.jobs_by_category["perfect_match"][0]
        
        # Score same job multiple times
        scores = []
        for _ in range(5):
            result = self.scoring_engine.score_job(test_job, pm_profile, system_settings)
            scores.append(result.total_score)
        
        # All scores should be identical (deterministic)
        for score in scores[1:]:
            self.assertEqual(score, scores[0], "Scoring should be deterministic")
    
    def test_configuration_changes_affect_scoring(self):
        """Test that configuration changes properly affect scoring results."""
        pm_profile = self.config_loader.load_pm_profile()
        system_settings = self.config_loader.load_system_settings()
        test_job = self.jobs_by_category["good_match"][0]
        
        # Get baseline score
        baseline_result = self.scoring_engine.score_job(test_job, pm_profile, system_settings)
        baseline_score = baseline_result.total_score
        
        # Modify settings to emphasize different factors
        system_settings.title_match_importance = "low"   # Reduce title importance
        system_settings.skills_match_importance = "high"  # Increase skills importance
        
        # Score again with modified settings
        modified_result = self.scoring_engine.score_job(test_job, pm_profile, system_settings)
        modified_score = modified_result.total_score
        
        # Scores should be different (though direction depends on job content)
        self.assertNotEqual(baseline_score, modified_score, 
                          "Configuration changes should affect scoring")
    
    def test_edge_case_handling(self):
        """Test handling of edge cases and malformed job data.""" 
        pm_profile = self.config_loader.load_pm_profile()
        system_settings = self.config_loader.load_system_settings()
        
        edge_case_jobs = self.jobs_by_category["edge_cases"]
        
        for job in edge_case_jobs:
            with self.subTest(job_id=job.id):
                # Should not crash on edge cases
                try:
                    result = self.scoring_engine.score_job(job, pm_profile, system_settings)
                    self.assertIsNotNone(result)
                    self.assertIsInstance(result.total_score, (int, float))
                except Exception as e:
                    self.fail(f"Edge case job {job.id} caused exception: {e}")
    
    def test_scoring_explanations_quality(self):
        """Test that scoring explanations are helpful and accurate."""
        pm_profile = self.config_loader.load_pm_profile()
        system_settings = self.config_loader.load_system_settings()
        
        # Test different job types
        test_cases = [
            ("perfect_match", "Should have positive explanations"),
            ("poor_match", "Should explain why score is low"),
            ("penalized", "Should mention penalties")
        ]
        
        for category, expectation in test_cases:
            jobs = self.jobs_by_category[category]
            if not jobs:
                continue
                
            job = jobs[0]
            result = self.scoring_engine.score_job(job, pm_profile, system_settings)
            
            # Test both detailed and summary explanations
            detailed_explanation = self.scoring_engine.create_score_explanation(result, detailed=True)
            summary_explanation = self.scoring_engine.create_score_explanation(result, detailed=False)
            
            with self.subTest(category=category, explanation_type="detailed"):
                self.assertIn("Job Score:", detailed_explanation)
                self.assertIn("Grade:", detailed_explanation)
                self.assertGreater(len(detailed_explanation.split('\n')), 3)
            
            with self.subTest(category=category, explanation_type="summary"):
                self.assertIn("Job Score:", summary_explanation) 
                self.assertGreater(len(summary_explanation), 50)  # Should be substantial
    
    def test_scorer_modularity_integration(self):
        """Test that scorer modularity works in integration."""
        pm_profile = self.config_loader.load_pm_profile()
        system_settings = self.config_loader.load_system_settings()
        test_job = self.jobs_by_category["good_match"][0]
        
        # Get baseline with all scorers
        baseline_result = self.scoring_engine.score_job(test_job, pm_profile, system_settings)
        baseline_categories = [r.category for r in baseline_result.scoring_reasons]
        
        # Remove one scorer
        removed = self.scoring_engine.remove_scorer("company")
        self.assertTrue(removed)
        
        # Score again
        modified_result = self.scoring_engine.score_job(test_job, pm_profile, system_settings)
        modified_categories = [r.category for r in modified_result.scoring_reasons]
        
        # Should have one fewer category
        self.assertEqual(len(modified_categories), len(baseline_categories) - 1)
        self.assertNotIn("company", modified_categories)
        
        # Add a custom scorer
        from core.scoring_engine import BaseScorer, ScoringReason
        
        class TestScorer(BaseScorer):
            def get_max_score(self):
                return 5.0
                
            def score_job(self, job, profile, settings):
                return ScoringReason(
                    category="test",
                    points=3.0,
                    max_points=5.0,
                    explanation="Test scorer result"
                )
        
        self.scoring_engine.add_scorer(TestScorer())
        
        # Score with custom scorer
        custom_result = self.scoring_engine.score_job(test_job, pm_profile, system_settings)
        custom_categories = [r.category for r in custom_result.scoring_reasons]
        
        self.assertIn("test", custom_categories)
        
        # Find test scorer result
        test_reason = next((r for r in custom_result.scoring_reasons if r.category == "test"), None)
        self.assertIsNotNone(test_reason)
        self.assertEqual(test_reason.points, 3.0)


class TestSystemReliability(unittest.TestCase):
    """Test system reliability and error handling."""
    
    def test_invalid_configuration_handling(self):
        """Test handling of invalid configuration data."""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create invalid config file
            invalid_config = {
                "experience": {
                    "years_of_pm_experience": -5,  # Invalid: negative years
                    "seniority_level": "invalid_level"  # Invalid: unknown level
                }
            }
            
            with open(os.path.join(temp_dir, "pm_profile.json"), 'w') as f:
                json.dump(invalid_config, f)
            
            config_loader = ConfigLoader(temp_dir)
            
            # Should raise ConfigValidationError
            with self.assertRaises(Exception):
                config_loader.load_pm_profile()
        
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_missing_configuration_files(self):
        """Test handling of missing configuration files."""
        temp_dir = tempfile.mkdtemp()
        
        try:
            config_loader = ConfigLoader(temp_dir)
            
            # Should raise error for missing file
            with self.assertRaises(Exception):
                config_loader.load_pm_profile()
        
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_scorer_error_isolation(self):
        """Test that errors in individual scorers don't crash the system."""
        from core.scoring_engine import BaseScorer, ScoringReason
        
        class FailingScorer(BaseScorer):
            def get_max_score(self):
                return 10.0
                
            def score_job(self, job, profile, settings):
                raise ValueError("Test scorer failure")
        
        # Create engine with failing scorer
        engine = DefaultPMScorer()
        engine.add_scorer(FailingScorer())
        
        pm_profile = get_all_test_profiles()["mid_level_pm"]
        system_settings = SystemSettings()
        test_job = create_test_jobs()[0]
        
        # Should not crash, should handle error gracefully
        result = engine.score_job(test_job, pm_profile, system_settings)
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.total_score, 0.0)
        
        # Should have error reason for failed scorer
        failing_reasons = [r for r in result.scoring_reasons if "failed" in r.explanation.lower()]
        self.assertGreater(len(failing_reasons), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)