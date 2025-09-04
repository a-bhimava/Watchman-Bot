"""
Individual Scorer Modules

Pluggable scoring components for the PM Watchman job scoring system.
Each scorer evaluates one aspect of job relevance.
"""

import re
from typing import List, Set, Dict, Any, Optional
from difflib import SequenceMatcher
from datetime import datetime, timedelta

from core.scoring_engine import BaseScorer, ScoringReason, ScoreWeight
from integrations.rss_processor import JobData
from core.config_loader import PMProfile, SystemSettings


class TitleScorer(BaseScorer):
    """
    Scores jobs based on title match with user preferences.
    
    Scoring breakdown (30 points max):
    - Perfect title match: 30 points
    - Close title match: 20 points  
    - Partial title match: 10 points
    - No match: 0 points
    """
    
    def get_max_score(self) -> float:
        """Maximum possible score from title matching."""
        return 30.0
    
    def score_job(self, 
                  job: JobData, 
                  pm_profile: PMProfile, 
                  settings: SystemSettings) -> ScoringReason:
        """Score job based on title relevance."""
        job_title = job.title.lower().strip()
        
        # Check for avoid titles first
        for avoid_title in pm_profile.avoid_titles:
            if avoid_title.lower() in job_title:
                return ScoringReason(
                    category="title",
                    points=0.0,
                    max_points=self.get_max_score(),
                    explanation=f"Title contains avoided term: '{avoid_title}'",
                    details={"matched_avoid_title": avoid_title}
                )
        
        # Check primary titles (perfect match)
        for primary_title in pm_profile.primary_titles:
            if self._is_exact_match(job_title, primary_title.lower()):
                return ScoringReason(
                    category="title",
                    points=self.get_max_score(),
                    max_points=self.get_max_score(),
                    explanation=f"Perfect title match: '{primary_title}'",
                    details={"matched_title": primary_title, "match_type": "exact"}
                )
        
        # Check secondary titles (perfect match)
        for secondary_title in pm_profile.secondary_titles:
            if self._is_exact_match(job_title, secondary_title.lower()):
                return ScoringReason(
                    category="title", 
                    points=25.0,
                    max_points=self.get_max_score(),
                    explanation=f"Secondary title match: '{secondary_title}'",
                    details={"matched_title": secondary_title, "match_type": "secondary_exact"}
                )
        
        # Check for close matches (contains key terms)
        best_match_score = 0.0
        best_match_title = ""
        best_match_type = ""
        
        # Primary titles - close match
        for primary_title in pm_profile.primary_titles:
            score = self._calculate_similarity_score(job_title, primary_title.lower())
            if score > 0.7:  # 70% similarity threshold
                match_score = 20.0
                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match_title = primary_title
                    best_match_type = "close_primary"
        
        # Secondary titles - close match
        for secondary_title in pm_profile.secondary_titles:
            score = self._calculate_similarity_score(job_title, secondary_title.lower())
            if score > 0.7:
                match_score = 15.0
                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match_title = secondary_title
                    best_match_type = "close_secondary"
        
        # Check for partial matches (contains keywords)
        if best_match_score == 0.0:
            pm_keywords = self._extract_pm_keywords(pm_profile)
            matched_keywords = []
            
            for keyword in pm_keywords:
                if keyword in job_title:
                    matched_keywords.append(keyword)
            
            if matched_keywords:
                # Score based on number of matched keywords
                partial_score = min(10.0, len(matched_keywords) * 3)
                return ScoringReason(
                    category="title",
                    points=partial_score,
                    max_points=self.get_max_score(),
                    explanation=f"Partial match: {', '.join(matched_keywords)}",
                    details={
                        "matched_keywords": matched_keywords,
                        "match_type": "partial",
                        "keyword_count": len(matched_keywords)
                    }
                )
        
        # Return best match found
        if best_match_score > 0:
            return ScoringReason(
                category="title",
                points=best_match_score,
                max_points=self.get_max_score(),
                explanation=f"Similar to '{best_match_title}'",
                details={
                    "matched_title": best_match_title,
                    "match_type": best_match_type
                }
            )
        
        # No meaningful match
        return ScoringReason(
            category="title",
            points=0.0,
            max_points=self.get_max_score(),
            explanation="No title match found",
            details={"job_title": job.title}
        )
    
    def _is_exact_match(self, job_title: str, target_title: str) -> bool:
        """Check if job title exactly matches target title."""
        # Clean both titles
        job_clean = re.sub(r'[^\w\s]', ' ', job_title)
        target_clean = re.sub(r'[^\w\s]', ' ', target_title)
        
        # Normalize whitespace
        job_clean = ' '.join(job_clean.split())
        target_clean = ' '.join(target_clean.split())
        
        return job_clean == target_clean
    
    def _calculate_similarity_score(self, job_title: str, target_title: str) -> float:
        """Calculate similarity score between two titles."""
        return SequenceMatcher(None, job_title, target_title).ratio()
    
    def _extract_pm_keywords(self, pm_profile: PMProfile) -> List[str]:
        """Extract PM-related keywords for partial matching."""
        keywords = ["product", "manager", "pm", "lead", "owner"]
        
        # Add keywords from titles
        for title in pm_profile.primary_titles + pm_profile.secondary_titles:
            words = title.lower().split()
            keywords.extend(words)
        
        # Remove duplicates and common words
        stop_words = {"the", "and", "or", "of", "in", "at", "to", "for", "a", "an"}
        return list(set(word for word in keywords if word not in stop_words))


class SkillsScorer(BaseScorer):
    """
    Scores jobs based on skill matches with user profile.
    
    Scoring breakdown (25 points max):
    - Each core PM skill match: 3 points
    - Each technical skill match: 2 points
    - Each domain expertise match: 2 points
    - Maximum 25 points total
    """
    
    def get_max_score(self) -> float:
        """Maximum possible score from skills matching."""
        return 25.0
    
    def score_job(self, 
                  job: JobData, 
                  pm_profile: PMProfile, 
                  settings: SystemSettings) -> ScoringReason:
        """Score job based on skills relevance."""
        job_text = f"{job.title} {job.description}".lower()
        
        matched_skills = []
        total_points = 0.0
        
        # Core PM skills (3 points each)
        for skill in pm_profile.core_pm_skills:
            if self._skill_mentioned_in_text(skill, job_text):
                matched_skills.append(f"Core: {skill}")
                total_points += 3.0
        
        # Technical skills (2 points each)
        for skill in pm_profile.technical_skills:
            if self._skill_mentioned_in_text(skill, job_text):
                matched_skills.append(f"Tech: {skill}")
                total_points += 2.0
        
        # Domain expertise (2 points each)
        for domain in pm_profile.domain_expertise:
            if self._skill_mentioned_in_text(domain, job_text):
                matched_skills.append(f"Domain: {domain}")
                total_points += 2.0
        
        # Cap at maximum score
        final_score = min(total_points, self.get_max_score())
        
        if matched_skills:
            return ScoringReason(
                category="skills",
                points=final_score,
                max_points=self.get_max_score(),
                explanation=f"{len(matched_skills)} skills matched",
                details={
                    "matched_skills": matched_skills,
                    "skill_count": len(matched_skills),
                    "raw_points": total_points
                }
            )
        else:
            return ScoringReason(
                category="skills",
                points=0.0,
                max_points=self.get_max_score(),
                explanation="No skill matches found",
                details={"searched_skills_count": len(pm_profile.core_pm_skills + 
                                                      pm_profile.technical_skills + 
                                                      pm_profile.domain_expertise)}
            )
    
    def _skill_mentioned_in_text(self, skill: str, text: str) -> bool:
        """Check if skill is mentioned in job text."""
        skill_lower = skill.lower()
        
        # Direct match
        if skill_lower in text:
            return True
        
        # Handle multi-word skills
        if ' ' in skill_lower:
            # Check if all words are present (order doesn't matter for some cases)
            words = skill_lower.split()
            if all(word in text for word in words):
                return True
        
        # Handle common variations
        skill_variations = self._get_skill_variations(skill_lower)
        for variation in skill_variations:
            if variation in text:
                return True
        
        return False
    
    def _get_skill_variations(self, skill: str) -> List[str]:
        """Get common variations of a skill name."""
        variations = [skill]
        
        # Common skill variations
        skill_map = {
            'product strategy': ['strategy', 'strategic planning'],
            'data analysis': ['analytics', 'data analytics', 'data science'],
            'user research': ['user studies', 'ux research', 'customer research'],
            'a/b testing': ['ab testing', 'experimentation', 'split testing'],
            'sql': ['structured query language', 'database queries'],
            'figma': ['design tools', 'prototyping'],
            'jira': ['project management', 'ticket management'],
            'agile': ['scrum', 'agile methodology'],
            'roadmapping': ['roadmap', 'product roadmap', 'strategic roadmap']
        }
        
        if skill in skill_map:
            variations.extend(skill_map[skill])
        
        return variations


class ExperienceScorer(BaseScorer):
    """
    Scores jobs based on experience level match.
    
    Scoring breakdown (20 points max):
    - Required years <= Your years: 20 points
    - Required years = Your years + 1: 15 points
    - Required years = Your years + 2: 10 points
    - Required years > Your years + 2: 0 points
    """
    
    def get_max_score(self) -> float:
        """Maximum possible score from experience matching."""
        return 20.0
    
    def score_job(self, 
                  job: JobData, 
                  pm_profile: PMProfile, 
                  settings: SystemSettings) -> ScoringReason:
        """Score job based on experience requirements."""
        user_years = pm_profile.years_of_pm_experience
        
        # Extract experience requirement from job
        required_experience = self._extract_experience_requirement(job)
        
        if required_experience is None:
            # No specific requirement mentioned - assume it's suitable
            return ScoringReason(
                category="experience",
                points=15.0,  # Neutral score
                max_points=self.get_max_score(),
                explanation="No specific experience requirement mentioned",
                details={"user_years": user_years}
            )
        
        required_years = required_experience.get("years")
        seniority_level = required_experience.get("level")
        
        # Score based on years if available
        if required_years is not None:
            if required_years <= user_years:
                score = 20.0
                explanation = f"You have {user_years} years, {required_years} required"
            elif required_years == user_years + 1:
                score = 15.0
                explanation = f"Slightly more experience preferred ({required_years} vs {user_years} years)"
            elif required_years == user_years + 2:
                score = 10.0
                explanation = f"More experience preferred ({required_years} vs {user_years} years)"
            else:
                score = 0.0
                explanation = f"Significantly more experience required ({required_years} vs {user_years} years)"
            
            return ScoringReason(
                category="experience",
                points=score,
                max_points=self.get_max_score(),
                explanation=explanation,
                details={
                    "user_years": user_years,
                    "required_years": required_years,
                    "experience_gap": required_years - user_years
                }
            )
        
        # Score based on seniority level
        if seniority_level:
            user_seniority = pm_profile.seniority_level.lower()
            required_seniority = seniority_level.lower()
            
            seniority_order = ["junior", "mid", "senior", "principal", "director", "vp"]
            
            try:
                user_index = seniority_order.index(user_seniority)
                required_index = seniority_order.index(required_seniority)
                
                if user_index >= required_index:
                    score = 20.0
                    explanation = f"Your {user_seniority} level meets {required_seniority} requirement"
                elif user_index == required_index - 1:
                    score = 15.0
                    explanation = f"Close match: {user_seniority} level for {required_seniority} role"
                else:
                    score = 5.0
                    explanation = f"Seniority gap: {user_seniority} level for {required_seniority} role"
                
                return ScoringReason(
                    category="experience",
                    points=score,
                    max_points=self.get_max_score(),
                    explanation=explanation,
                    details={
                        "user_seniority": user_seniority,
                        "required_seniority": required_seniority,
                        "seniority_gap": required_index - user_index
                    }
                )
                
            except ValueError:
                # Unrecognized seniority level
                pass
        
        # Fallback - neutral score
        return ScoringReason(
            category="experience",
            points=10.0,
            max_points=self.get_max_score(),
            explanation="Experience requirement unclear",
            details={"extracted_requirement": required_experience}
        )
    
    def _extract_experience_requirement(self, job: JobData) -> Optional[Dict[str, Any]]:
        """Extract experience requirements from job description."""
        text = f"{job.title} {job.description}".lower()
        
        # Look for years of experience
        years_patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'(\d+)\+?\s*years?\s+(?:of\s+)?pm\s+experience',
            r'(\d+)\+?\s*years?\s+product\s+management',
            r'minimum\s+(\d+)\s+years?',
            r'at\s+least\s+(\d+)\s+years?'
        ]
        
        for pattern in years_patterns:
            match = re.search(pattern, text)
            if match:
                years = int(match.group(1))
                return {"years": years, "level": None}
        
        # Look for seniority levels
        level_patterns = [
            r'\b(junior|entry.?level)\b',
            r'\b(mid.?level|mid)\b', 
            r'\b(senior)\b',
            r'\b(principal|staff)\b',
            r'\b(director|lead)\b'
        ]
        
        for pattern in level_patterns:
            match = re.search(pattern, text)
            if match:
                level = match.group(1).replace('-level', '').replace('_level', '')
                return {"years": None, "level": level}
        
        return None


class IndustryScorer(BaseScorer):
    """
    Scores jobs based on industry preferences.
    
    Scoring breakdown (15 points max):
    - Primary industry experience: 15 points
    - Secondary industry experience: 10 points
    - Interested industry: 8 points
    - Avoided industry: -15 points (penalty)
    - No match: 0 points
    """
    
    def get_max_score(self) -> float:
        """Maximum possible score from industry matching."""
        return 15.0
    
    def score_job(self, 
                  job: JobData, 
                  pm_profile: PMProfile, 
                  settings: SystemSettings) -> ScoringReason:
        """Score job based on industry relevance."""
        job_industry = job.industry
        job_text = f"{job.title} {job.description} {job.company}".lower()
        
        # Check for avoided industries first (penalty)
        for avoid_industry in pm_profile.avoid_industries:
            if self._industry_mentioned(avoid_industry, job_text, job_industry):
                return ScoringReason(
                    category="industry",
                    points=-15.0,
                    max_points=self.get_max_score(),
                    explanation=f"Avoided industry: {avoid_industry}",
                    details={"matched_avoid_industry": avoid_industry}
                )
        
        # Check primary industries
        for primary_industry in pm_profile.primary_industries:
            if self._industry_mentioned(primary_industry, job_text, job_industry):
                return ScoringReason(
                    category="industry",
                    points=15.0,
                    max_points=self.get_max_score(),
                    explanation=f"Primary industry match: {primary_industry}",
                    details={"matched_industry": primary_industry, "match_type": "primary"}
                )
        
        # Check interested industries
        for interested_industry in pm_profile.interested_industries:
            if self._industry_mentioned(interested_industry, job_text, job_industry):
                return ScoringReason(
                    category="industry",
                    points=8.0,
                    max_points=self.get_max_score(),
                    explanation=f"Interested industry: {interested_industry}",
                    details={"matched_industry": interested_industry, "match_type": "interested"}
                )
        
        # No industry match
        return ScoringReason(
            category="industry",
            points=0.0,
            max_points=self.get_max_score(),
            explanation="No industry preference match",
            details={"detected_industry": job_industry}
        )
    
    def _industry_mentioned(self, industry: str, job_text: str, job_industry: Optional[str]) -> bool:
        """Check if industry is mentioned in job."""
        industry_lower = industry.lower()
        
        # Direct match with detected industry
        if job_industry and industry_lower == job_industry.lower():
            return True
        
        # Text-based matching
        if industry_lower in job_text:
            return True
        
        # Industry keyword variations
        industry_keywords = {
            'fintech': ['financial technology', 'finance', 'banking', 'payments', 'crypto'],
            'healthtech': ['healthcare', 'health', 'medical', 'biotech', 'pharma'],
            'edtech': ['education technology', 'learning', 'e-learning', 'educational'],
            'saas': ['software as a service', 'cloud software', 'enterprise software'],
            'e-commerce': ['ecommerce', 'retail', 'marketplace', 'shopping'],
            'social': ['social media', 'social network', 'community'],
            'gaming': ['games', 'gaming', 'entertainment', 'esports'],
            'mobility': ['transportation', 'automotive', 'rideshare', 'logistics']
        }
        
        if industry_lower in industry_keywords:
            keywords = industry_keywords[industry_lower]
            return any(keyword in job_text for keyword in keywords)
        
        return False


class CompanyScorer(BaseScorer):
    """
    Scores jobs based on company preferences.
    
    Scoring breakdown (10 points max):
    - Preferred company: 10 points
    - Company stage/size match: 5 points
    - Avoided company: -20 points (major penalty)
    - No preference: 0 points
    """
    
    def get_max_score(self) -> float:
        """Maximum possible score from company matching."""
        return 10.0
    
    def score_job(self, 
                  job: JobData, 
                  pm_profile: PMProfile, 
                  settings: SystemSettings) -> ScoringReason:
        """Score job based on company preferences."""
        company_name = job.company.lower()
        
        # Check for avoided companies first (major penalty)
        for avoid_company in pm_profile.avoid_companies:
            if avoid_company.lower() in company_name:
                return ScoringReason(
                    category="company",
                    points=-20.0,
                    max_points=self.get_max_score(),
                    explanation=f"Avoided company: {avoid_company}",
                    details={"matched_avoid_company": avoid_company}
                )
        
        # Check preferred companies
        for preferred_company in pm_profile.preferred_companies:
            if preferred_company.lower() in company_name:
                return ScoringReason(
                    category="company",
                    points=10.0,
                    max_points=self.get_max_score(),
                    explanation=f"Preferred company: {preferred_company}",
                    details={"matched_company": preferred_company}
                )
        
        # Check company stage/size preferences from job description
        job_text = f"{job.description} {job.company}".lower()
        stage_size_score = self._score_company_attributes(job_text, pm_profile)
        
        if stage_size_score > 0:
            return ScoringReason(
                category="company",
                points=stage_size_score,
                max_points=self.get_max_score(),
                explanation="Company attributes match preferences",
                details={"attribute_score": stage_size_score}
            )
        
        # No company preference match
        return ScoringReason(
            category="company",
            points=0.0,
            max_points=self.get_max_score(),
            explanation="No company preference match",
            details={"company": job.company}
        )
    
    def _score_company_attributes(self, job_text: str, pm_profile: PMProfile) -> float:
        """Score based on company stage and size preferences."""
        score = 0.0
        
        # Check company stages
        stage_keywords = {
            'startup': ['startup', 'early stage', 'seed', 'series a'],
            'growth': ['growth stage', 'series b', 'series c', 'scaling'],
            'enterprise': ['enterprise', 'established', 'fortune'],
            'public': ['public company', 'publicly traded', 'nasdaq', 'nyse']
        }
        
        for preferred_stage in pm_profile.company_stages:
            if preferred_stage.lower() in stage_keywords:
                keywords = stage_keywords[preferred_stage.lower()]
                if any(keyword in job_text for keyword in keywords):
                    score += 3.0
                    break
        
        # Check company sizes
        size_keywords = {
            '1-10': ['small team', 'startup', '< 10'],
            '11-50': ['small company', 'team of'],
            '51-200': ['growing company', 'medium size'],
            '201-500': ['established company', 'hundreds'],
            '501-1000': ['large company', 'enterprise'],
            '1000+': ['large enterprise', 'thousands', 'fortune']
        }
        
        for preferred_size in pm_profile.company_sizes:
            if preferred_size in size_keywords:
                keywords = size_keywords[preferred_size]
                if any(keyword in job_text for keyword in keywords):
                    score += 2.0
                    break
        
        return min(score, 5.0)  # Cap at 5 points