"""
Modular Job Scoring System Architecture

Pluggable scoring system that allows easy modification and swapping
of scoring algorithms without affecting the core system.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime

from integrations.rss_processor import JobData
from core.config_loader import PMProfile, SystemSettings
from utils.logger import get_logger, performance_tracker


class ScoreWeight(Enum):
    """Score importance weights."""
    LOW = 1.0
    MEDIUM = 1.5
    HIGH = 2.0


@dataclass
class ScoringReason:
    """Individual scoring reason/explanation."""
    category: str
    points: float
    max_points: float
    explanation: str
    details: Optional[Dict[str, Any]] = None
    
    @property
    def percentage(self) -> float:
        """Get percentage of max possible points."""
        if self.max_points == 0:
            return 0.0
        return (self.points / self.max_points) * 100


@dataclass
class JobScore:
    """Complete job scoring result."""
    job_id: str
    total_score: float
    max_possible_score: float = 100.0
    scoring_reasons: List[ScoringReason] = field(default_factory=list)
    scoring_engine: str = ""
    scored_at: datetime = field(default_factory=datetime.now)
    
    @property
    def percentage(self) -> float:
        """Get score as percentage."""
        if self.max_possible_score == 0:
            return 0.0
        return min(100.0, (self.total_score / self.max_possible_score) * 100)
    
    @property
    def letter_grade(self) -> str:
        """Get letter grade for score."""
        pct = self.percentage
        if pct >= 90:
            return "A"
        elif pct >= 80:
            return "B"
        elif pct >= 70:
            return "C"
        elif pct >= 60:
            return "D"
        else:
            return "F"
    
    def get_top_reasons(self, limit: int = 3) -> List[ScoringReason]:
        """Get top scoring reasons by points."""
        return sorted(
            self.scoring_reasons,
            key=lambda r: r.points,
            reverse=True
        )[:limit]
    
    def get_explanation_text(self, max_reasons: int = 3) -> str:
        """Get human-readable scoring explanation."""
        if not self.scoring_reasons:
            return f"Score: {self.percentage:.0f}% (No detailed breakdown available)"
        
        top_reasons = self.get_top_reasons(max_reasons)
        explanations = []
        
        for reason in top_reasons:
            if reason.points > 0:
                explanations.append(f"• {reason.explanation} (+{reason.points:.0f} pts)")
        
        return f"Score: {self.percentage:.0f}%\n" + "\n".join(explanations)


class BaseScorer(ABC):
    """
    Abstract base class for individual scoring components.
    
    Each scorer focuses on one aspect of job relevance
    (e.g., title match, skills match, experience match).
    """
    
    def __init__(self, weight: ScoreWeight = ScoreWeight.MEDIUM):
        """
        Initialize scorer.
        
        Args:
            weight: Importance weight for this scorer
        """
        self.weight = weight
        self.logger = get_logger(__name__)
    
    @abstractmethod
    def get_max_score(self) -> float:
        """Get maximum possible score from this scorer."""
        pass
    
    @abstractmethod
    def score_job(self, 
                  job: JobData, 
                  pm_profile: PMProfile, 
                  settings: SystemSettings) -> ScoringReason:
        """
        Score a job based on this scorer's criteria.
        
        Args:
            job: Job to score
            pm_profile: User's PM profile
            settings: System settings
            
        Returns:
            ScoringReason with score and explanation
        """
        pass
    
    @property
    def name(self) -> str:
        """Get scorer name."""
        return self.__class__.__name__.replace("Scorer", "").lower()
    
    def apply_weight(self, base_score: float) -> float:
        """Apply weight multiplier to base score."""
        return base_score * self.weight.value


class ScoringEngine(ABC):
    """
    Abstract base class for complete scoring systems.
    
    A scoring engine combines multiple scorers to produce
    a final job relevance score.
    """
    
    def __init__(self, name: str):
        """
        Initialize scoring engine.
        
        Args:
            name: Engine name/identifier
        """
        self.name = name
        self.logger = get_logger(__name__)
        self.scorers: List[BaseScorer] = []
    
    def add_scorer(self, scorer: BaseScorer) -> None:
        """
        Add scorer to the engine.
        
        Args:
            scorer: Scorer instance to add
        """
        self.scorers.append(scorer)
        self.logger.debug(f"Added scorer {scorer.name} to engine {self.name}")
    
    def remove_scorer(self, scorer_name: str) -> bool:
        """
        Remove scorer by name.
        
        Args:
            scorer_name: Name of scorer to remove
            
        Returns:
            True if scorer was found and removed
        """
        initial_count = len(self.scorers)
        self.scorers = [s for s in self.scorers if s.name != scorer_name]
        removed = len(self.scorers) < initial_count
        
        if removed:
            self.logger.debug(f"Removed scorer {scorer_name} from engine {self.name}")
        
        return removed
    
    def get_scorer(self, scorer_name: str) -> Optional[BaseScorer]:
        """
        Get scorer by name.
        
        Args:
            scorer_name: Name of scorer to find
            
        Returns:
            Scorer instance or None if not found
        """
        for scorer in self.scorers:
            if scorer.name == scorer_name:
                return scorer
        return None
    
    def list_scorers(self) -> List[str]:
        """Get list of all scorer names."""
        return [scorer.name for scorer in self.scorers]
    
    @performance_tracker("scoring_engine", "score_job")
    def score_job(self, 
                  job: JobData, 
                  pm_profile: PMProfile, 
                  settings: SystemSettings) -> JobScore:
        """
        Score job using all registered scorers.
        
        Args:
            job: Job to score
            pm_profile: User's PM profile  
            settings: System settings
            
        Returns:
            Complete JobScore with breakdown
        """
        scoring_reasons = []
        total_score = 0.0
        max_possible = 0.0
        
        for scorer in self.scorers:
            try:
                reason = scorer.score_job(job, pm_profile, settings)
                scoring_reasons.append(reason)
                total_score += reason.points
                max_possible += reason.max_points
                
            except Exception as e:
                self.logger.error(
                    f"Error in scorer {scorer.name}: {str(e)}",
                    extra={"job_id": job.id, "scorer": scorer.name},
                    exc_info=True
                )
                # Add zero-score reason for failed scorer
                scoring_reasons.append(ScoringReason(
                    category=scorer.name,
                    points=0.0,
                    max_points=scorer.get_max_score(),
                    explanation=f"{scorer.name} scoring failed",
                    details={"error": str(e)}
                ))
        
        return JobScore(
            job_id=job.id,
            total_score=total_score,
            max_possible_score=max_possible,
            scoring_reasons=scoring_reasons,
            scoring_engine=self.name
        )
    
    def score_jobs(self, 
                   jobs: List[JobData],
                   pm_profile: PMProfile,
                   settings: SystemSettings) -> List[JobScore]:
        """
        Score multiple jobs.
        
        Args:
            jobs: List of jobs to score
            pm_profile: User's PM profile
            settings: System settings
            
        Returns:
            List of JobScore results
        """
        scores = []
        
        for job in jobs:
            try:
                score = self.score_job(job, pm_profile, settings)
                scores.append(score)
            except Exception as e:
                self.logger.error(
                    f"Failed to score job {job.id}: {str(e)}",
                    exc_info=True
                )
                # Create minimal score for failed job
                scores.append(JobScore(
                    job_id=job.id,
                    total_score=0.0,
                    scoring_reasons=[ScoringReason(
                        category="error",
                        points=0.0,
                        max_points=100.0,
                        explanation="Scoring failed due to error",
                        details={"error": str(e)}
                    )],
                    scoring_engine=self.name
                ))
        
        return scores
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get engine configuration information."""
        return {
            "name": self.name,
            "scorers": [
                {
                    "name": scorer.name,
                    "weight": scorer.weight.name,
                    "max_score": scorer.get_max_score()
                }
                for scorer in self.scorers
            ],
            "total_max_score": sum(scorer.get_max_score() for scorer in self.scorers),
            "scorer_count": len(self.scorers)
        }


class ScoringRegistry:
    """
    Registry for managing multiple scoring engines.
    
    Allows dynamic loading, switching, and management of
    different scoring approaches.
    """
    
    def __init__(self):
        """Initialize scoring registry."""
        self.engines: Dict[str, ScoringEngine] = {}
        self.default_engine: Optional[str] = None
        self.logger = get_logger(__name__)
    
    def register_engine(self, engine: ScoringEngine, set_as_default: bool = False) -> None:
        """
        Register a scoring engine.
        
        Args:
            engine: Scoring engine to register
            set_as_default: Whether to set as default engine
        """
        self.engines[engine.name] = engine
        
        if set_as_default or self.default_engine is None:
            self.default_engine = engine.name
        
        self.logger.info(f"Registered scoring engine: {engine.name}")
    
    def get_engine(self, name: Optional[str] = None) -> Optional[ScoringEngine]:
        """
        Get scoring engine by name.
        
        Args:
            name: Engine name (uses default if None)
            
        Returns:
            ScoringEngine instance or None
        """
        if name is None:
            name = self.default_engine
        
        if name is None:
            return None
        
        return self.engines.get(name)
    
    def set_default_engine(self, name: str) -> bool:
        """
        Set default scoring engine.
        
        Args:
            name: Engine name to set as default
            
        Returns:
            True if successful
        """
        if name in self.engines:
            self.default_engine = name
            self.logger.info(f"Set default scoring engine: {name}")
            return True
        return False
    
    def list_engines(self) -> List[str]:
        """Get list of registered engine names."""
        return list(self.engines.keys())
    
    def remove_engine(self, name: str) -> bool:
        """
        Remove engine from registry.
        
        Args:
            name: Engine name to remove
            
        Returns:
            True if engine was found and removed
        """
        if name in self.engines:
            del self.engines[name]
            
            # Reset default if removed
            if self.default_engine == name:
                self.default_engine = next(iter(self.engines.keys())) if self.engines else None
            
            self.logger.info(f"Removed scoring engine: {name}")
            return True
        return False
    
    def score_job(self, 
                  job: JobData,
                  pm_profile: PMProfile,
                  settings: SystemSettings,
                  engine_name: Optional[str] = None) -> Optional[JobScore]:
        """
        Score job using specified or default engine.
        
        Args:
            job: Job to score
            pm_profile: User's PM profile
            settings: System settings
            engine_name: Engine to use (default if None)
            
        Returns:
            JobScore or None if engine not found
        """
        engine = self.get_engine(engine_name)
        if engine is None:
            return None
        
        return engine.score_job(job, pm_profile, settings)
    
    def score_jobs(self,
                   jobs: List[JobData],
                   pm_profile: PMProfile,
                   settings: SystemSettings,
                   engine_name: Optional[str] = None) -> List[JobScore]:
        """
        Score multiple jobs using specified or default engine.
        
        Args:
            jobs: Jobs to score
            pm_profile: User's PM profile
            settings: System settings
            engine_name: Engine to use (default if None)
            
        Returns:
            List of JobScore results
        """
        engine = self.get_engine(engine_name)
        if engine is None:
            return []
        
        return engine.score_jobs(jobs, pm_profile, settings)
    
    def get_registry_info(self) -> Dict[str, Any]:
        """Get registry status information."""
        return {
            "total_engines": len(self.engines),
            "default_engine": self.default_engine,
            "engines": {
                name: engine.get_engine_info()
                for name, engine in self.engines.items()
            }
        }


# Global scoring registry
_scoring_registry: Optional[ScoringRegistry] = None


def get_scoring_registry() -> ScoringRegistry:
    """Get global scoring registry instance."""
    global _scoring_registry
    if _scoring_registry is None:
        _scoring_registry = ScoringRegistry()
    return _scoring_registry


def register_scoring_engine(engine: ScoringEngine, set_as_default: bool = False):
    """
    Register scoring engine globally.
    
    Args:
        engine: Engine to register
        set_as_default: Set as default engine
    """
    registry = get_scoring_registry()
    registry.register_engine(engine, set_as_default)


def score_job(job: JobData,
              pm_profile: PMProfile,
              settings: SystemSettings,
              engine_name: Optional[str] = None) -> Optional[JobScore]:
    """
    Score job using global registry.
    
    Args:
        job: Job to score
        pm_profile: User PM profile
        settings: System settings
        engine_name: Engine name (uses default if None)
        
    Returns:
        JobScore or None
    """
    registry = get_scoring_registry()
    return registry.score_job(job, pm_profile, settings, engine_name)


def score_jobs(jobs: List[JobData],
               pm_profile: PMProfile, 
               settings: SystemSettings,
               engine_name: Optional[str] = None) -> List[JobScore]:
    """
    Score multiple jobs using global registry.
    
    Args:
        jobs: Jobs to score
        pm_profile: User PM profile
        settings: System settings
        engine_name: Engine name (uses default if None)
        
    Returns:
        List of JobScore results
    """
    registry = get_scoring_registry()
    return registry.score_jobs(jobs, pm_profile, settings, engine_name)