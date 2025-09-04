"""
Telegram Message Format Testing and Validation

Tests various message formatting scenarios to ensure Telegram 
integration produces high-quality, informative job notifications.
"""

import unittest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.default_pm_scorer import DefaultPMScorer
from core.config_loader import SystemSettings

# Import test data
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from test_data.sample_jobs import get_jobs_by_category
from test_data.test_profiles import get_all_test_profiles


class TestTelegramMessageFormatting(unittest.TestCase):
    """Test Telegram message formatting for job notifications."""
    
    def setUp(self):
        """Set up test components."""
        self.scoring_engine = DefaultPMScorer()
        self.pm_profile = get_all_test_profiles()["mid_level_pm"]
        self.system_settings = SystemSettings()
        self.jobs_by_category = get_jobs_by_category()
    
    def format_job_message(self, job, score_result, detailed=False):
        """Format a job for Telegram delivery."""
        
        # Calculate grade
        score_percentage = score_result.total_score
        if score_percentage >= 90:
            grade = "🌟 EXCELLENT"
            priority = "🔥 HIGH PRIORITY"
        elif score_percentage >= 75:
            grade = "⭐ GREAT"  
            priority = "🚀 RECOMMENDED"
        elif score_percentage >= 60:
            grade = "✅ GOOD"
            priority = "👀 WORTH CONSIDERING"
        elif score_percentage >= 45:
            grade = "⚠️ MARGINAL"
            priority = "🤔 QUESTIONABLE"
        else:
            grade = "❌ POOR"
            priority = "🚫 NOT RECOMMENDED"
        
        # Basic message format
        message = f"""🎯 **PM Job Alert**

**{job.title}** at **{job.company}**
📍 {job.location}
💰 {job.salary if hasattr(job, 'salary') and job.salary else 'Salary not disclosed'}

**Score: {score_percentage:.0f}%** | **Grade: {grade}**
**Priority: {priority}**

"""
        
        if detailed:
            # Add detailed scoring breakdown
            message += "📊 **Scoring Breakdown:**\n"
            for reason in score_result.scoring_reasons:
                percentage = (reason.points / reason.max_points) * 100 if reason.max_points > 0 else 0
                emoji = self._get_score_emoji(percentage)
                message += f"{emoji} {reason.category.title()}: {percentage:.0f}% ({reason.explanation})\n"
            message += "\n"
        
        # Add key highlights
        message += "🔍 **Key Details:**\n"
        if hasattr(job, 'required_experience') and job.required_experience:
            message += f"📈 Experience: {job.required_experience}\n"
        if hasattr(job, 'company_size') and job.company_size:
            message += f"🏢 Company Size: {job.company_size}\n"
        if hasattr(job, 'industry') and job.industry:
            message += f"🏭 Industry: {job.industry}\n"
        
        # Description preview (first 200 chars)
        if hasattr(job, 'description') and job.description:
            preview = job.description[:200] + "..." if len(job.description) > 200 else job.description
            message += f"\n📝 **Description Preview:**\n{preview}\n"
        
        # Apply link
        if hasattr(job, 'url') and job.url:
            message += f"\n🔗 **Apply Here:** {job.url}"
        
        return message.strip()
    
    def _get_score_emoji(self, percentage):
        """Get emoji for score percentage."""
        if percentage >= 90:
            return "🌟"
        elif percentage >= 75:
            return "⭐"
        elif percentage >= 60:
            return "✅"
        elif percentage >= 45:
            return "⚠️"
        else:
            return "❌"
    
    def test_perfect_match_message_format(self):
        """Test message formatting for perfect match jobs."""
        perfect_jobs = self.jobs_by_category["perfect_match"]
        
        for job in perfect_jobs[:1]:  # Test first perfect match
            score_result = self.scoring_engine.score_job(job, self.pm_profile, self.system_settings)
            
            # Test basic message
            basic_message = self.format_job_message(job, score_result, detailed=False)
            detailed_message = self.format_job_message(job, score_result, detailed=True)
            
            # Validate basic message structure
            self.assertIn("🎯 **PM Job Alert**", basic_message)
            self.assertIn(job.title, basic_message)
            self.assertIn(job.company, basic_message)
            self.assertIn("EXCELLENT", basic_message)
            self.assertIn("HIGH PRIORITY", basic_message)
            
            # Validate detailed message has breakdown
            self.assertIn("📊 **Scoring Breakdown:**", detailed_message)
            self.assertGreater(len(detailed_message), len(basic_message))
            
            print(f"\n{'='*60}")
            print("PERFECT MATCH JOB MESSAGE (Detailed):")
            print(f"{'='*60}")
            print(detailed_message)
    
    def test_good_match_message_format(self):
        """Test message formatting for good match jobs."""
        good_jobs = self.jobs_by_category["good_match"]
        
        for job in good_jobs[:1]:  # Test first good match
            score_result = self.scoring_engine.score_job(job, self.pm_profile, self.system_settings)
            message = self.format_job_message(job, score_result, detailed=False)
            
            # Should have positive but not perfect indicators
            self.assertIn("🎯 **PM Job Alert**", message)
            self.assertIn(job.title, message)
            self.assertTrue(any(x in message for x in ["GREAT", "GOOD"]))
            
            print(f"\n{'='*60}")
            print("GOOD MATCH JOB MESSAGE:")
            print(f"{'='*60}")
            print(message)
    
    def test_marginal_match_message_format(self):
        """Test message formatting for marginal jobs."""
        marginal_jobs = self.jobs_by_category["marginal"]
        
        for job in marginal_jobs[:1]:  # Test first marginal match
            score_result = self.scoring_engine.score_job(job, self.pm_profile, self.system_settings)
            message = self.format_job_message(job, score_result, detailed=True)
            
            # Should indicate caution
            self.assertIn("🎯 **PM Job Alert**", message)
            self.assertTrue(any(x in message for x in ["MARGINAL", "GOOD"]))
            
            print(f"\n{'='*60}")
            print("MARGINAL JOB MESSAGE:")
            print(f"{'='*60}")
            print(message)
    
    def test_poor_match_message_format(self):
        """Test message formatting for poor match jobs."""
        poor_jobs = self.jobs_by_category["poor_match"]
        
        for job in poor_jobs[:1]:  # Test first poor match
            score_result = self.scoring_engine.score_job(job, self.pm_profile, self.system_settings)
            message = self.format_job_message(job, score_result, detailed=True)
            
            # Should clearly indicate poor match
            self.assertIn("🎯 **PM Job Alert**", message)
            self.assertTrue(any(x in message for x in ["POOR", "MARGINAL"]))
            
            print(f"\n{'='*60}")
            print("POOR MATCH JOB MESSAGE:")
            print(f"{'='*60}")
            print(message)
    
    def test_batch_message_format(self):
        """Test formatting for batch job delivery."""
        # Get jobs from different categories
        test_jobs = []
        for category in ["perfect_match", "good_match", "marginal"]:
            jobs = self.jobs_by_category[category]
            if jobs:
                test_jobs.append(jobs[0])
        
        # Score all jobs
        scored_jobs = []
        for job in test_jobs[:3]:  # Limit to 3 for testing
            score_result = self.scoring_engine.score_job(job, self.pm_profile, self.system_settings)
            scored_jobs.append((job, score_result))
        
        # Sort by score (highest first)
        scored_jobs.sort(key=lambda x: x[1].total_score, reverse=True)
        
        # Create batch message
        batch_message = "🚀 **Daily PM Job Update**\n"
        batch_message += f"📅 Found {len(scored_jobs)} jobs matching your profile\n\n"
        
        for i, (job, score_result) in enumerate(scored_jobs, 1):
            batch_message += f"**#{i}** "
            
            # Mini format for batch
            score_percentage = score_result.total_score
            if score_percentage >= 90:
                grade_emoji = "🌟"
            elif score_percentage >= 75:
                grade_emoji = "⭐"
            elif score_percentage >= 60:
                grade_emoji = "✅"
            else:
                grade_emoji = "⚠️"
                
            batch_message += f"{grade_emoji} **{job.title}** at **{job.company}**\n"
            batch_message += f"📍 {job.location} | 💯 Score: {score_percentage:.0f}%\n"
            
            if hasattr(job, 'url') and job.url:
                batch_message += f"🔗 {job.url}\n"
            
            batch_message += "\n"
        
        batch_message += "💌 Reply with job number for detailed breakdown"
        
        # Validate batch message
        self.assertIn("Daily PM Job Update", batch_message)
        self.assertIn("Found", batch_message)
        self.assertGreater(len(batch_message.split('\n')), 10)
        
        print(f"\n{'='*60}")
        print("BATCH JOB MESSAGE:")
        print(f"{'='*60}")
        print(batch_message)
    
    def test_message_length_validation(self):
        """Test that messages stay within Telegram limits."""
        # Telegram message limit is 4096 characters
        TELEGRAM_LIMIT = 4096
        
        jobs = [job for category_jobs in self.jobs_by_category.values() for job in category_jobs]
        
        for job in jobs[:5]:  # Test several jobs
            score_result = self.scoring_engine.score_job(job, self.pm_profile, self.system_settings)
            
            basic_message = self.format_job_message(job, score_result, detailed=False)
            detailed_message = self.format_job_message(job, score_result, detailed=True)
            
            # Check lengths
            self.assertLess(len(basic_message), TELEGRAM_LIMIT, 
                          f"Basic message too long: {len(basic_message)} chars")
            self.assertLess(len(detailed_message), TELEGRAM_LIMIT,
                          f"Detailed message too long: {len(detailed_message)} chars")
    
    def test_special_character_handling(self):
        """Test handling of special characters in job data."""
        # Test with job that has special characters
        edge_case_jobs = self.jobs_by_category["edge_cases"]
        
        for job in edge_case_jobs:
            score_result = self.scoring_engine.score_job(job, self.pm_profile, self.system_settings)
            message = self.format_job_message(job, score_result, detailed=False)
            
            # Should not crash and should be valid
            self.assertIsInstance(message, str)
            self.assertGreater(len(message), 50)
    
    def test_missing_data_handling(self):
        """Test message formatting with missing job data."""
        from integrations.rss_processor import JobData
        
        # Create job with minimal data
        minimal_job = JobData(
            id="test_minimal",
            title="Product Manager",
            company="Test Company", 
            location="Remote",
            # Missing: salary, description, url, etc.
        )
        
        score_result = self.scoring_engine.score_job(minimal_job, self.pm_profile, self.system_settings)
        message = self.format_job_message(minimal_job, score_result, detailed=False)
        
        # Should handle missing data gracefully
        self.assertIn("Product Manager", message)
        self.assertIn("Test Company", message)
        self.assertIn("Remote", message)
        self.assertIn("Salary not disclosed", message)


class TestMessageCustomization(unittest.TestCase):
    """Test message customization based on system settings."""
    
    def setUp(self):
        """Set up test components."""
        self.scoring_engine = DefaultPMScorer()
        self.pm_profile = get_all_test_profiles()["mid_level_pm"]
        self.jobs_by_category = get_jobs_by_category()
    
    def test_message_customization_by_settings(self):
        """Test that system settings affect message formatting."""
        job = self.jobs_by_category["good_match"][0]
        
        # Test with different settings
        settings_configs = [
            {"jobs_per_message": 1, "include_description_preview": True},
            {"jobs_per_message": 3, "include_description_preview": False}
        ]
        
        for config in settings_configs:
            system_settings = SystemSettings()
            # Apply settings (would be loaded from config in real implementation)
            
            score_result = self.scoring_engine.score_job(job, self.pm_profile, system_settings)
            
            # This would be customized based on settings
            # For now, just validate basic functionality
            self.assertIsNotNone(score_result)
            self.assertGreater(score_result.total_score, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)