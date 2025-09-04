"""
Comprehensive Scoring System Test Suite

Tests all components of the modular scoring system:
- Individual scorers (Title, Skills, Experience, etc.)
- Scoring engine functionality 
- Score explanations and reasoning
- Modular scorer swapping
- Weight configuration
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.scoring_engine import (
    ScoringEngine, BaseScorer, ScoringReason, JobScore, 
    ScoreWeight, ScoringRegistry, get_scoring_registry
)
from core.scorers import (
    TitleScorer, SkillsScorer, ExperienceScorer, 
    IndustryScorer, CompanyScorer
)
from core.default_pm_scorer import DefaultPMScorer, BonusScorer
from core.config_loader import SystemSettings
from integrations.rss_processor import JobData

# Import test data
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from test_data.sample_jobs import create_test_jobs, get_jobs_by_category, get_expected_score_ranges
from test_data.test_profiles import get_all_test_profiles


class TestIndividualScorers(unittest.TestCase):
    """Test individual scorer components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_jobs = create_test_jobs()
        self.test_profiles = get_all_test_profiles()
        self.settings = SystemSettings()
        
        # Get specific test cases
        jobs_by_category = get_jobs_by_category()
        self.perfect_job = jobs_by_category["perfect_match"][0]  # Stripe PM job
        self.poor_job = jobs_by_category["poor_match"][0]       # Accenture Project Manager
        self.edge_case_job = jobs_by_category["edge_cases"][0]  # Empty job
    
    def test_title_scorer_perfect_match(self):
        """Test TitleScorer with perfect title match."""
        scorer = TitleScorer()
        profile = self.test_profiles["mid_level_pm"]
        
        result = scorer.score_job(self.perfect_job, profile, self.settings)
        
        # Should get high score for "Senior Product Manager" 
        self.assertGreaterEqual(result.points, 25.0)
        self.assertEqual(result.max_points, 30.0)
        self.assertIn("title match", result.explanation.lower())
        self.assertEqual(result.category, "title")
    
    def test_title_scorer_poor_match(self):
        """Test TitleScorer with poor title match."""
        scorer = TitleScorer()
        profile = self.test_profiles["mid_level_pm"]
        
        result = scorer.score_job(self.poor_job, profile, self.settings)
        
        # "Project Manager - IT Operations" should score poorly
        self.assertLessEqual(result.points, 10.0)
        self.assertEqual(result.max_points, 30.0)
    
    def test_title_scorer_avoid_titles(self):
        """Test TitleScorer correctly penalizes avoided titles.""" 
        scorer = TitleScorer()
        profile = self.test_profiles["mid_level_pm"]
        
        # Create job with avoided title
        avoided_job = JobData(
            id="avoid_test",
            title="Marketing Manager",  # In avoid_titles list
            company="TestCorp",
            location="Remote",
            description="Marketing role"
        )
        
        result = scorer.score_job(avoided_job, profile, self.settings)
        
        self.assertEqual(result.points, 0.0)
        self.assertIn("avoided term", result.explanation)
    
    def test_skills_scorer_multiple_matches(self):
        """Test SkillsScorer with multiple skill matches."""
        scorer = SkillsScorer()
        profile = self.test_profiles["mid_level_pm"]
        
        result = scorer.score_job(self.perfect_job, profile, self.settings)
        
        # Perfect job has many matching skills
        self.assertGreater(result.points, 10.0)
        self.assertEqual(result.max_points, 25.0)
        self.assertIn("skills matched", result.explanation)
        self.assertIn("matched_skills", result.details)
    
    def test_skills_scorer_no_matches(self):
        """Test SkillsScorer with no skill matches."""
        scorer = SkillsScorer()
        profile = self.test_profiles["mid_level_pm"]
        
        result = scorer.score_job(self.edge_case_job, profile, self.settings)
        
        self.assertEqual(result.points, 0.0)
        self.assertIn("No skill matches", result.explanation)
    
    def test_experience_scorer_good_fit(self):
        """Test ExperienceScorer with appropriate experience match."""
        scorer = ExperienceScorer()
        profile = self.test_profiles["mid_level_pm"]  # 5 years experience
        
        result = scorer.score_job(self.perfect_job, profile, self.settings)
        
        # Job requires "5+ years", user has 5 years - should be good match
        self.assertGreaterEqual(result.points, 15.0)
        self.assertEqual(result.max_points, 20.0)
    
    def test_experience_scorer_over_qualified(self):
        """Test ExperienceScorer when user is over-qualified."""
        scorer = ExperienceScorer()
        profile = self.test_profiles["senior_pm"]  # 9 years experience
        
        # Create junior role requiring 2-3 years
        junior_job = JobData(
            id="junior_test",
            title="Associate Product Manager",
            company="TestCorp",
            location="Remote",
            experience_required="2-3 years experience",
            description="Entry level PM role requiring 2-3 years experience"
        )
        
        result = scorer.score_job(junior_job, profile, self.settings)
        
        # Should still get points for being qualified
        self.assertGreaterEqual(result.points, 15.0)
    
    def test_industry_scorer_primary_match(self):
        """Test IndustryScorer with primary industry match."""
        scorer = IndustryScorer()
        profile = self.test_profiles["fintech_specialist"]
        
        result = scorer.score_job(self.perfect_job, profile, self.settings)  # Fintech job
        
        # Should get high score for fintech industry match
        self.assertGreaterEqual(result.points, 10.0)
        self.assertEqual(result.max_points, 15.0)
    
    def test_industry_scorer_avoided_industry(self):
        """Test IndustryScorer with avoided industry."""
        scorer = IndustryScorer()
        profile = self.test_profiles["mid_level_pm"]
        
        # Get tobacco industry job (should be avoided)
        tobacco_job = next((job for job in self.test_jobs if job.industry == "tobacco"), None)
        
        if tobacco_job:
            result = scorer.score_job(tobacco_job, profile, self.settings)
            
            # Should get negative score for avoided industry
            self.assertLess(result.points, 0.0)
            self.assertIn("Avoided industry", result.explanation)
    
    def test_company_scorer_preferred_company(self):
        """Test CompanyScorer with preferred company."""
        scorer = CompanyScorer()
        profile = self.test_profiles["mid_level_pm"]
        
        result = scorer.score_job(self.perfect_job, profile, self.settings)  # Stripe job
        
        # Stripe is in preferred companies list
        self.assertGreaterEqual(result.points, 8.0)
        self.assertEqual(result.max_points, 10.0)
        self.assertIn("Preferred company", result.explanation)
    
    def test_company_scorer_avoided_company(self):
        """Test CompanyScorer with avoided company."""
        scorer = CompanyScorer()
        profile = self.test_profiles["mid_level_pm"]
        
        # Create job with avoided company
        avoided_company_job = JobData(
            id="avoid_company_test", 
            title="Product Manager",
            company="Meta",  # In avoid_companies list
            location="Remote",
            description="PM role at Meta"
        )
        
        result = scorer.score_job(avoided_company_job, profile, self.settings)
        
        # Should get significant penalty
        self.assertLess(result.points, -10.0)
        self.assertIn("Avoided company", result.explanation)


class TestBonusScorer(unittest.TestCase):
    """Test bonus/penalty scoring logic."""
    
    def setUp(self):
        """Set up test fixtures.""" 
        self.profile = get_all_test_profiles()["mid_level_pm"]
        self.settings = SystemSettings()
    
    def test_remote_work_bonus(self):
        """Test remote work bonus for remote-preferring profile."""
        # Profile prefers remote work
        self.profile.remote_preference = "remote_first"
        
        remote_job = JobData(
            id="remote_test",
            title="Product Manager", 
            company="TestCorp",
            location="Remote",
            description="Fully remote Product Manager role with distributed team."
        )
        
        result = BonusScorer.calculate_bonus_score(remote_job, self.profile, self.settings)
        
        self.assertGreater(result.points, 0.0)
        self.assertIn("Remote work", result.explanation)
    
    def test_salary_bonus(self):
        """Test salary bonus calculation."""
        high_salary_job = JobData(
            id="salary_test",
            title="Product Manager",
            company="TestCorp", 
            location="Remote",
            salary_range="$220,000 - $280,000",  # Above target
            description="High paying PM role."
        )
        
        result = BonusScorer.calculate_bonus_score(high_salary_job, self.profile, self.settings)
        
        # Should get bonus for high salary
        self.assertGreater(result.points, 0.0)
        self.assertIn("salary", result.explanation.lower())
    
    def test_equity_bonus(self):
        """Test equity mention bonus."""
        equity_job = JobData(
            id="equity_test",
            title="Product Manager",
            company="TestCorp",
            location="Remote", 
            description="Product Manager role with significant equity upside and stock options."
        )
        
        # Set equity importance to high
        self.profile.equity_importance = "high"
        
        result = BonusScorer.calculate_bonus_score(equity_job, self.profile, self.settings)
        
        self.assertGreater(result.points, 0.0)
        self.assertIn("Equity", result.explanation)
    
    def test_recent_posting_bonus(self):
        """Test recent posting bonus."""
        recent_job = JobData(
            id="recent_test",
            title="Product Manager",
            company="TestCorp",
            location="Remote",
            description="Recently posted PM role.",
            posted_date=datetime.now()  # Just posted
        )
        
        result = BonusScorer.calculate_bonus_score(recent_job, self.profile, self.settings)
        
        self.assertGreater(result.points, 0.0)
        self.assertIn("Recently posted", result.explanation)
    
    def test_brief_description_penalty(self):
        """Test penalty for brief job descriptions."""
        brief_job = JobData(
            id="brief_test",
            title="Product Manager",
            company="TestCorp", 
            location="Remote",
            description="Short description."  # Very brief
        )
        
        result = BonusScorer.calculate_bonus_score(brief_job, self.profile, self.settings)
        
        self.assertLess(result.points, 0.0)
        self.assertIn("Brief job description", result.explanation)
    
    def test_recruiter_penalty(self):
        """Test penalty for third-party recruiters."""
        recruiter_job = JobData(
            id="recruiter_test",
            title="Product Manager", 
            company="TechRecruiting Solutions",  # Recruiting company
            location="Remote",
            description="Great PM opportunity with our client."
        )
        
        result = BonusScorer.calculate_bonus_score(recruiter_job, self.profile, self.settings)
        
        self.assertLess(result.points, 0.0)
        self.assertIn("Third-party recruiter", result.explanation)


class TestScoringEngine(unittest.TestCase):
    """Test scoring engine functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = DefaultPMScorer()
        self.profile = get_all_test_profiles()["mid_level_pm"]
        self.settings = SystemSettings()
        self.perfect_job = get_jobs_by_category()["perfect_match"][0]
    
    def test_engine_initialization(self):
        """Test scoring engine initializes with all scorers."""
        self.assertEqual(len(self.engine.scorers), 5)  # 5 main scorers
        
        scorer_names = self.engine.list_scorers()
        expected_scorers = ["title", "skills", "experience", "industry", "company"]
        
        for expected in expected_scorers:
            self.assertIn(expected, scorer_names)
    
    def test_scorer_addition_removal(self):
        """Test adding and removing scorers."""
        initial_count = len(self.engine.scorers)
        
        # Create custom scorer
        class CustomScorer(BaseScorer):
            def get_max_score(self):
                return 5.0
            
            def score_job(self, job, profile, settings):
                return ScoringReason(
                    category="custom",
                    points=5.0,
                    max_points=5.0, 
                    explanation="Custom scoring"
                )
        
        # Add custom scorer
        custom_scorer = CustomScorer()
        self.engine.add_scorer(custom_scorer)
        
        self.assertEqual(len(self.engine.scorers), initial_count + 1)
        self.assertIn("custom", self.engine.list_scorers())
        
        # Remove scorer
        removed = self.engine.remove_scorer("custom")
        self.assertTrue(removed)
        self.assertEqual(len(self.engine.scorers), initial_count)
    
    def test_weight_configuration(self):
        """Test scorer weight configuration from settings."""
        # Modify settings
        self.settings.title_match_importance = "low"
        self.settings.skills_match_importance = "high" 
        
        # Configure weights
        self.engine.configure_weights_from_settings(self.settings)
        
        # Check weights were applied
        title_scorer = self.engine.get_scorer("title")
        skills_scorer = self.engine.get_scorer("skills")
        
        self.assertEqual(title_scorer.weight, ScoreWeight.LOW)
        self.assertEqual(skills_scorer.weight, ScoreWeight.HIGH)
    
    def test_complete_job_scoring(self):
        """Test complete job scoring with all components."""
        result = self.engine.score_job(self.perfect_job, self.profile, self.settings)
        
        # Validate JobScore structure
        self.assertIsInstance(result, JobScore)
        self.assertEqual(result.job_id, self.perfect_job.id)
        self.assertGreater(result.total_score, 0.0)
        self.assertGreaterEqual(len(result.scoring_reasons), 5)  # At least 5 scorers + bonus
        
        # Check for all expected scoring categories
        categories = [reason.category for reason in result.scoring_reasons]
        expected_categories = ["title", "skills", "experience", "industry", "company", "bonus"]
        
        for expected in expected_categories:
            self.assertIn(expected, categories)
    
    def test_score_explanation_generation(self):
        """Test score explanation text generation."""
        result = self.engine.score_job(self.perfect_job, self.profile, self.settings)
        
        # Test detailed explanation
        detailed_explanation = self.engine.create_score_explanation(result, detailed=True)
        
        self.assertIn("Job Score:", detailed_explanation)
        self.assertIn("Grade:", detailed_explanation)
        self.assertIn("Detailed Breakdown:", detailed_explanation)
        
        # Test summary explanation
        summary_explanation = self.engine.create_score_explanation(result, detailed=False)
        
        self.assertIn("Job Score:", summary_explanation)
        self.assertIn("Top Matches:", summary_explanation)
    
    def test_batch_job_scoring(self):
        """Test scoring multiple jobs."""
        test_jobs = create_test_jobs()[:5]  # First 5 jobs
        
        results = self.engine.score_jobs(test_jobs, self.profile, self.settings)
        
        self.assertEqual(len(results), 5)
        
        for result in results:
            self.assertIsInstance(result, JobScore)
            self.assertGreaterEqual(result.total_score, 0.0)
            self.assertGreater(len(result.scoring_reasons), 0)


class TestScoringRegistry(unittest.TestCase):
    """Test scoring registry functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.registry = ScoringRegistry()
        self.engine1 = DefaultPMScorer("test_engine_1")
        self.engine2 = DefaultPMScorer("test_engine_2")
    
    def test_engine_registration(self):
        """Test engine registration and retrieval."""
        self.registry.register_engine(self.engine1, set_as_default=True)
        self.registry.register_engine(self.engine2)
        
        # Check registration
        self.assertIn("test_engine_1", self.registry.list_engines())
        self.assertIn("test_engine_2", self.registry.list_engines())
        self.assertEqual(self.registry.default_engine, "test_engine_1")
        
        # Test retrieval
        retrieved_engine = self.registry.get_engine("test_engine_1")
        self.assertEqual(retrieved_engine.name, "test_engine_1")
    
    def test_default_engine_management(self):
        """Test default engine setting and usage."""
        self.registry.register_engine(self.engine1)
        self.registry.register_engine(self.engine2)
        
        # Set default
        self.assertTrue(self.registry.set_default_engine("test_engine_2"))
        self.assertEqual(self.registry.default_engine, "test_engine_2")
        
        # Get default engine
        default_engine = self.registry.get_engine()  # No name = default
        self.assertEqual(default_engine.name, "test_engine_2")
    
    def test_engine_removal(self):
        """Test engine removal from registry.""" 
        self.registry.register_engine(self.engine1, set_as_default=True)
        self.registry.register_engine(self.engine2)
        
        # Remove non-default engine
        self.assertTrue(self.registry.remove_engine("test_engine_2"))
        self.assertNotIn("test_engine_2", self.registry.list_engines())
        
        # Remove default engine (should reset default)
        self.assertTrue(self.registry.remove_engine("test_engine_1"))
        self.assertIsNone(self.registry.default_engine)


class TestScoringAccuracy(unittest.TestCase):
    """Test scoring accuracy against expected ranges."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = DefaultPMScorer()
        self.profiles = get_all_test_profiles()
        self.settings = SystemSettings()
        self.jobs_by_category = get_jobs_by_category()
        self.expected_ranges = get_expected_score_ranges()
    
    def test_perfect_match_scores(self):
        """Test that perfect match jobs score in expected range.""" 
        profile = self.profiles["mid_level_pm"]
        perfect_jobs = self.jobs_by_category["perfect_match"]
        expected_min, expected_max = self.expected_ranges["perfect_match"]
        
        for job in perfect_jobs:
            result = self.engine.score_job(job, profile, self.settings)
            
            self.assertGreaterEqual(
                result.total_score, expected_min,
                f"Job {job.id} scored {result.total_score}, expected >= {expected_min}"
            )
            self.assertLessEqual(
                result.total_score, expected_max,
                f"Job {job.id} scored {result.total_score}, expected <= {expected_max}"
            )
    
    def test_good_match_scores(self):
        """Test that good match jobs score in expected range."""
        profile = self.profiles["mid_level_pm"] 
        good_jobs = self.jobs_by_category["good_match"]
        expected_min, expected_max = self.expected_ranges["good_match"]
        
        for job in good_jobs:
            result = self.engine.score_job(job, profile, self.settings)
            
            self.assertGreaterEqual(result.total_score, expected_min)
            self.assertLessEqual(result.total_score, expected_max)
    
    def test_poor_match_scores(self):
        """Test that poor match jobs score in expected range."""
        profile = self.profiles["mid_level_pm"]
        poor_jobs = self.jobs_by_category["poor_match"]
        expected_min, expected_max = self.expected_ranges["poor_match"]
        
        for job in poor_jobs:
            result = self.engine.score_job(job, profile, self.settings)
            
            self.assertGreaterEqual(result.total_score, expected_min)
            self.assertLessEqual(result.total_score, expected_max)
    
    def test_penalized_job_scores(self):
        """Test that penalized jobs score very low."""
        profile = self.profiles["mid_level_pm"]
        penalized_jobs = self.jobs_by_category["penalized"]
        expected_min, expected_max = self.expected_ranges["penalized"]
        
        for job in penalized_jobs:
            result = self.engine.score_job(job, profile, self.settings)
            
            self.assertGreaterEqual(result.total_score, expected_min)
            self.assertLessEqual(result.total_score, expected_max)
    
    def test_profile_specificity(self):
        """Test that different profiles score same job differently."""
        test_job = self.jobs_by_category["perfect_match"][0]  # Stripe fintech job
        
        # Score with different profiles
        fintech_result = self.engine.score_job(
            test_job, self.profiles["fintech_specialist"], self.settings
        )
        healthcare_result = self.engine.score_job(
            test_job, self.profiles["healthcare_pm"], self.settings
        )
        
        # Fintech specialist should score fintech job higher
        self.assertGreater(
            fintech_result.total_score, healthcare_result.total_score,
            "Fintech specialist should score fintech job higher than healthcare PM"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)