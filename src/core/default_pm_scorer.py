"""
Default PM Scoring Engine

Complete scoring system that combines all individual scorers
into a comprehensive job relevance algorithm for Product Managers.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .scoring_engine import ScoringEngine, ScoringReason, ScoreWeight, JobScore
from .scorers import TitleScorer, SkillsScorer, ExperienceScorer, IndustryScorer, CompanyScorer
from ..integrations.rss_processor import JobData
from ..core.config_loader import PMProfile, SystemSettings
from ..utils.logger import get_logger


class BonusScorer:
    """
    Additional bonus/penalty scoring for special cases.
    
    Bonuses (up to +10 points):
    - Remote work (if preferred): +5 points
    - Salary above target: +3 points
    - Equity mentioned: +2 points
    - Recent posting (<24 hours): +2 points
    - High-priority source: +1 point
    
    Penalties:
    - Vague job description: -5 points
    - No salary information: -2 points
    - Third-party recruiter: -3 points
    """
    
    @staticmethod
    def calculate_bonus_score(job: JobData, pm_profile: PMProfile, settings: SystemSettings) -> ScoringReason:
        """Calculate bonus/penalty points for job."""
        total_bonus = 0.0
        bonus_reasons = []
        penalty_reasons = []
        
        job_text = f"{job.title} {job.description}".lower()
        
        # Remote work bonus
        if pm_profile.remote_preference in ['remote_only', 'remote_first']:
            remote_indicators = ['remote', 'work from home', 'wfh', 'distributed', 'anywhere']
            if any(indicator in job_text or indicator in job.location.lower() 
                   for indicator in remote_indicators):
                total_bonus += 5.0
                bonus_reasons.append("Remote work available (+5)")
        
        # Salary bonus
        if job.salary_range:
            salary_bonus = BonusScorer._calculate_salary_bonus(job.salary_range, pm_profile)
            if salary_bonus > 0:
                total_bonus += salary_bonus
                bonus_reasons.append(f"Competitive salary (+{salary_bonus})")
        
        # Equity bonus
        equity_indicators = ['equity', 'stock options', 'rsu', 'ownership', 'shares']
        if any(indicator in job_text for indicator in equity_indicators):
            if pm_profile.equity_importance == 'high':
                total_bonus += 2.0
                bonus_reasons.append("Equity mentioned (+2)")
            elif pm_profile.equity_importance == 'medium':
                total_bonus += 1.0
                bonus_reasons.append("Equity mentioned (+1)")
        
        # Recent posting bonus
        if job.posted_date:
            hours_since_posted = (datetime.now() - job.posted_date.replace(tzinfo=None)).total_seconds() / 3600
            if hours_since_posted < 24:
                total_bonus += 2.0
                bonus_reasons.append("Recently posted (+2)")
        
        # High-priority source bonus
        if job.source in ['linkedin', 'company_direct']:
            total_bonus += 1.0
            bonus_reasons.append("High-priority source (+1)")
        
        # Description quality penalty
        if len(job.description) < 200:
            total_bonus -= 5.0
            penalty_reasons.append("Brief job description (-5)")
        
        # Missing salary penalty
        if not job.salary_range:
            no_salary_indicators = ['competitive', 'market rate', 'based on experience']
            if not any(indicator in job_text for indicator in no_salary_indicators):
                total_bonus -= 2.0
                penalty_reasons.append("No salary information (-2)")
        
        # Third-party recruiter penalty
        recruiter_indicators = ['recruiting', 'staffing', 'headhunter', 'talent acquisition']
        if any(indicator in job.company.lower() for indicator in recruiter_indicators):
            total_bonus -= 3.0
            penalty_reasons.append("Third-party recruiter (-3)")
        
        # Combine all explanations
        all_reasons = bonus_reasons + penalty_reasons
        if all_reasons:
            explanation = f"Bonus factors: {'; '.join(all_reasons)}"
        else:
            explanation = "No bonus factors applied"
        
        return ScoringReason(
            category="bonus",
            points=total_bonus,
            max_points=10.0,
            explanation=explanation,
            details={
                "bonus_reasons": bonus_reasons,
                "penalty_reasons": penalty_reasons,
                "total_adjustments": len(all_reasons)
            }
        )
    
    @staticmethod
    def _calculate_salary_bonus(salary_range: str, pm_profile: PMProfile) -> float:
        """Calculate salary-based bonus points."""
        try:
            # Extract numbers from salary range
            import re
            numbers = re.findall(r'[\d,]+', salary_range.replace('k', '000'))
            
            if not numbers:
                return 0.0
            
            # Convert to integers and find the maximum
            salaries = []
            for num_str in numbers:
                try:
                    salary = int(num_str.replace(',', ''))
                    if salary < 1000:  # Probably in thousands (e.g., "120k")
                        salary *= 1000
                    salaries.append(salary)
                except ValueError:
                    continue
            
            if not salaries:
                return 0.0
            
            max_salary = max(salaries)
            
            # Compare with user's target
            if max_salary >= pm_profile.target_total_comp:
                return 3.0
            elif max_salary >= pm_profile.minimum_base_salary:
                return 1.0
            
        except Exception:
            pass
        
        return 0.0


class DefaultPMScorer(ScoringEngine):
    """
    Default Product Manager scoring engine.
    
    Combines all individual scorers with configurable weights
    to produce comprehensive job relevance scores.
    
    Scoring breakdown (100+ points possible):
    - Title Match: 30 points (configurable weight)
    - Skills Match: 25 points (configurable weight)
    - Experience Match: 20 points (configurable weight)
    - Industry Match: 15 points (configurable weight)
    - Company Match: 10 points (configurable weight)
    - Bonus/Penalty: ±10 points (additional factors)
    """
    
    def __init__(self, name: str = "default_pm_scorer"):
        """Initialize default PM scoring engine."""
        super().__init__(name)
        self.logger = get_logger(__name__)
        
        # Initialize scorers with default weights
        self._initialize_scorers()
    
    def _initialize_scorers(self):
        """Initialize all scorer components."""
        # Add individual scorers
        self.add_scorer(TitleScorer(weight=ScoreWeight.HIGH))
        self.add_scorer(SkillsScorer(weight=ScoreWeight.HIGH))
        self.add_scorer(ExperienceScorer(weight=ScoreWeight.MEDIUM))
        self.add_scorer(IndustryScorer(weight=ScoreWeight.MEDIUM))
        self.add_scorer(CompanyScorer(weight=ScoreWeight.LOW))
        
        self.logger.info(f"Initialized {len(self.scorers)} scorers for {self.name}")
    
    def configure_weights_from_settings(self, settings: SystemSettings):
        """
        Configure scorer weights based on system settings.
        
        Args:
            settings: System settings with importance levels
        """
        weight_map = {
            'low': ScoreWeight.LOW,
            'medium': ScoreWeight.MEDIUM, 
            'high': ScoreWeight.HIGH
        }
        
        # Update weights based on settings
        title_scorer = self.get_scorer('title')
        if title_scorer:
            title_scorer.weight = weight_map.get(settings.title_match_importance.lower(), ScoreWeight.HIGH)
        
        skills_scorer = self.get_scorer('skills')
        if skills_scorer:
            skills_scorer.weight = weight_map.get(settings.skills_match_importance.lower(), ScoreWeight.HIGH)
        
        experience_scorer = self.get_scorer('experience')
        if experience_scorer:
            experience_scorer.weight = weight_map.get(settings.experience_match_importance.lower(), ScoreWeight.MEDIUM)
        
        industry_scorer = self.get_scorer('industry')
        if industry_scorer:
            industry_scorer.weight = weight_map.get(settings.industry_match_importance.lower(), ScoreWeight.MEDIUM)
        
        company_scorer = self.get_scorer('company')
        if company_scorer:
            company_scorer.weight = weight_map.get(settings.company_match_importance.lower(), ScoreWeight.LOW)
        
        self.logger.info("Updated scorer weights from system settings")
    
    def score_job(self, 
                  job: JobData, 
                  pm_profile: PMProfile, 
                  settings: SystemSettings) -> JobScore:
        """
        Score job using all scorers plus bonus factors.
        
        Args:
            job: Job to score
            pm_profile: User's PM profile
            settings: System settings
            
        Returns:
            Complete JobScore with detailed breakdown
        """
        # Configure weights from settings
        self.configure_weights_from_settings(settings)
        
        # Get base score from parent class
        base_score = super().score_job(job, pm_profile, settings)
        
        # Add bonus scoring
        try:
            bonus_reason = BonusScorer.calculate_bonus_score(job, pm_profile, settings)
            base_score.scoring_reasons.append(bonus_reason)
            base_score.total_score += bonus_reason.points
            base_score.max_possible_score += bonus_reason.max_points
            
        except Exception as e:
            self.logger.error(
                f"Error calculating bonus score for job {job.id}: {str(e)}",
                exc_info=True
            )
            # Add error reason
            base_score.scoring_reasons.append(ScoringReason(
                category="bonus",
                points=0.0,
                max_points=10.0,
                explanation="Bonus scoring failed",
                details={"error": str(e)}
            ))
        
        # Ensure score is within reasonable bounds
        base_score.total_score = max(0.0, min(120.0, base_score.total_score))  # Allow up to 120 with bonuses
        
        return base_score
    
    def get_scoring_summary(self) -> Dict[str, Any]:
        """Get summary of scoring configuration."""
        scorer_info = []
        
        for scorer in self.scorers:
            scorer_info.append({
                "name": scorer.name,
                "weight": scorer.weight.name,
                "max_score": scorer.get_max_score(),
                "weighted_max": scorer.get_max_score() * scorer.weight.value
            })
        
        return {
            "engine_name": self.name,
            "scorers": scorer_info,
            "total_scorers": len(self.scorers),
            "base_max_score": sum(scorer.get_max_score() for scorer in self.scorers),
            "weighted_max_score": sum(scorer.get_max_score() * scorer.weight.value for scorer in self.scorers),
            "includes_bonus": True,
            "bonus_max": 10.0
        }
    
    def create_score_explanation(self, job_score: JobScore, detailed: bool = False) -> str:
        """
        Create human-readable explanation of job score.
        
        Args:
            job_score: Job score to explain
            detailed: Include detailed breakdown
            
        Returns:
            Formatted explanation string
        """
        lines = [
            f"🎯 Job Score: {job_score.percentage:.0f}% ({job_score.total_score:.1f}/{job_score.max_possible_score:.1f} points)",
            f"📊 Grade: {job_score.letter_grade}",
            ""
        ]
        
        if detailed:
            lines.append("📋 Detailed Breakdown:")
            
            # Sort reasons by points (highest first)
            sorted_reasons = sorted(
                job_score.scoring_reasons,
                key=lambda r: r.points,
                reverse=True
            )
            
            for reason in sorted_reasons:
                if reason.points != 0:  # Only show non-zero scores
                    emoji = "✅" if reason.points > 0 else "❌"
                    lines.append(
                        f"   {emoji} {reason.category.title()}: "
                        f"{reason.points:+.1f} pts - {reason.explanation}"
                    )
        else:
            # Show top 3 positive reasons
            positive_reasons = [r for r in job_score.scoring_reasons if r.points > 0]
            top_reasons = sorted(positive_reasons, key=lambda r: r.points, reverse=True)[:3]
            
            if top_reasons:
                lines.append("🔥 Top Matches:")
                for reason in top_reasons:
                    lines.append(f"   • {reason.explanation} (+{reason.points:.0f} pts)")
            
            # Show penalties if any
            penalties = [r for r in job_score.scoring_reasons if r.points < 0]
            if penalties:
                lines.append("⚠️ Concerns:")
                for penalty in penalties:
                    lines.append(f"   • {penalty.explanation} ({penalty.points:.0f} pts)")
        
        return "\n".join(lines)


def create_default_pm_scoring_engine() -> DefaultPMScorer:
    """
    Factory function to create default PM scoring engine.
    
    Returns:
        Configured DefaultPMScorer instance
    """
    engine = DefaultPMScorer()
    
    # Log creation
    logger = get_logger(__name__)
    logger.info(f"Created default PM scoring engine with {len(engine.scorers)} scorers")
    
    return engine


def setup_default_scoring() -> DefaultPMScorer:
    """
    Set up and register default scoring engine.
    
    Returns:
        DefaultPMScorer instance
    """
    from .scoring_engine import register_scoring_engine
    
    engine = create_default_pm_scoring_engine()
    register_scoring_engine(engine, set_as_default=True)
    
    return engine