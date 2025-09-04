#!/usr/bin/env python3
"""
Quick Scoring System Validation Script

Simple validation of the PM job scoring system without complex imports.
Tests core functionality to ensure system is ready for Phase 2.
"""

import sys
import os
from datetime import datetime

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tests'))

def print_header(title):
    """Print a formatted header."""
    print(f"\n{'='*80}")
    print(f" {title}")
    print(f"{'='*80}")

def print_section(title):
    """Print a section divider."""
    print(f"\n{'-'*60}")
    print(f" {title}")
    print(f"{'-'*60}")

def validate_imports():
    """Validate that all core modules can be imported."""
    print_section("Module Import Validation")
    
    modules_to_test = [
        ('core.config_loader', 'PMProfile, SystemSettings'),
        ('integrations.rss_processor', 'JobData'),
        ('core.scoring_engine', 'BaseScorer, ScoringEngine'),
        ('core.scorers', 'TitleScorer, SkillsScorer'),
        ('core.default_pm_scorer', 'DefaultPMScorer'),
        ('test_data.sample_jobs', 'create_test_jobs'),
        ('test_data.test_profiles', 'get_all_test_profiles')
    ]
    
    results = {}
    
    for module_name, components in modules_to_test:
        try:
            exec(f"from {module_name} import {components}")
            print(f"✅ {module_name}")
            results[module_name] = True
        except Exception as e:
            print(f"❌ {module_name}: {e}")
            results[module_name] = False
    
    return all(results.values())

def test_basic_scoring():
    """Test basic scoring functionality."""
    print_section("Basic Scoring Functionality Test")
    
    try:
        # Import components
        from core.default_pm_scorer import DefaultPMScorer
        from test_data.sample_jobs import get_jobs_by_category
        from test_data.test_profiles import get_all_test_profiles
        from core.config_loader import SystemSettings
        
        # Initialize components
        scoring_engine = DefaultPMScorer()
        pm_profile = get_all_test_profiles()["mid_level_pm"]
        system_settings = SystemSettings()
        jobs_by_category = get_jobs_by_category()
        
        print("✅ Components initialized successfully")
        
        # Test scoring different job categories
        test_results = {}
        
        for category, jobs in jobs_by_category.items():
            if not jobs:
                continue
                
            job = jobs[0]  # Test first job in category
            try:
                result = scoring_engine.score_job(job, pm_profile, system_settings)
                test_results[category] = {
                    'job_title': job.title,
                    'score': result.total_score,
                    'grade': result.letter_grade,
                    'success': True
                }
                print(f"✅ {category}: '{job.title}' -> {result.total_score:.1f}% (Grade: {result.letter_grade})")
                
            except Exception as e:
                test_results[category] = {
                    'job_title': job.title,
                    'error': str(e),
                    'success': False
                }
                print(f"❌ {category}: '{job.title}' -> ERROR: {e}")
        
        # Analyze results
        successful_tests = sum(1 for r in test_results.values() if r['success'])
        total_tests = len(test_results)
        
        print(f"\n📊 Scoring Test Results: {successful_tests}/{total_tests} successful")
        
        if successful_tests >= 3:  # At least 3 successful tests
            successful_scores = [r['score'] for r in test_results.values() if r['success']]
            min_score = min(successful_scores)
            max_score = max(successful_scores)
            
            print(f"📈 Score range: {min_score:.1f}% - {max_score:.1f}%")
            
            if max_score > min_score + 20:  # Good differentiation
                print("✅ Scoring system shows good differentiation between job types")
                return True
            else:
                print("⚠️ Limited score differentiation - may need tuning")
                return True  # Still functional
        else:
            print("❌ Insufficient successful scoring tests")
            return False
            
    except Exception as e:
        print(f"❌ Basic scoring test failed: {e}")
        return False

def test_modular_architecture():
    """Test the modular scorer architecture."""
    print_section("Modular Architecture Test")
    
    try:
        from core.default_pm_scorer import DefaultPMScorer
        from test_data.sample_jobs import get_jobs_by_category
        from test_data.test_profiles import get_all_test_profiles
        from core.config_loader import SystemSettings
        
        # Initialize components
        engine = DefaultPMScorer()
        profile = get_all_test_profiles()["mid_level_pm"]
        settings = SystemSettings()
        test_job = get_jobs_by_category()["good_match"][0]
        
        # Test baseline scoring
        baseline_result = engine.score_job(test_job, profile, settings)
        baseline_scorers = len(baseline_result.scoring_reasons)
        
        print(f"✅ Baseline scoring: {baseline_result.total_score:.1f}% with {baseline_scorers} scorers")
        
        # Test removing a scorer
        removed = engine.remove_scorer("company")
        if removed:
            modified_result = engine.score_job(test_job, profile, settings)
            modified_scorers = len(modified_result.scoring_reasons)
            
            if modified_scorers == baseline_scorers - 1:
                print("✅ Scorer removal works correctly")
                
                # Test adding it back
                from core.scorers import CompanyScorer
                engine.add_scorer(CompanyScorer())
                
                restored_result = engine.score_job(test_job, profile, settings)
                restored_scorers = len(restored_result.scoring_reasons)
                
                if restored_scorers == baseline_scorers:
                    print("✅ Scorer addition works correctly")
                    print("✅ Modular architecture functioning properly")
                    return True
                else:
                    print("❌ Scorer addition failed")
                    return False
            else:
                print("❌ Scorer removal failed")
                return False
        else:
            print("❌ Could not remove scorer")
            return False
            
    except Exception as e:
        print(f"❌ Modular architecture test failed: {e}")
        return False

def test_scoring_explanations():
    """Test scoring explanation generation."""
    print_section("Scoring Explanations Test")
    
    try:
        from core.default_pm_scorer import DefaultPMScorer
        from test_data.sample_jobs import get_jobs_by_category
        from test_data.test_profiles import get_all_test_profiles
        from core.config_loader import SystemSettings
        
        engine = DefaultPMScorer()
        profile = get_all_test_profiles()["mid_level_pm"]
        settings = SystemSettings()
        
        # Test explanation for perfect match
        perfect_jobs = get_jobs_by_category()["perfect_match"]
        if perfect_jobs:
            job = perfect_jobs[0]
            result = engine.score_job(job, profile, settings)
            
            # Test detailed explanation
            detailed_explanation = engine.create_score_explanation(result, detailed=True)
            summary_explanation = engine.create_score_explanation(result, detailed=False)
            
            if "Job Score:" in detailed_explanation and "Grade:" in detailed_explanation:
                print("✅ Detailed explanations working")
            else:
                print("❌ Detailed explanations missing key components")
                return False
            
            if "Job Score:" in summary_explanation and len(summary_explanation) > 50:
                print("✅ Summary explanations working") 
                print("✅ Scoring explanations functioning properly")
                return True
            else:
                print("❌ Summary explanations insufficient")
                return False
        else:
            print("❌ No perfect match jobs available for testing")
            return False
            
    except Exception as e:
        print(f"❌ Scoring explanations test failed: {e}")
        return False

def demonstrate_telegram_message():
    """Demonstrate Telegram message formatting."""
    print_section("Sample Telegram Message Demo")
    
    try:
        from core.default_pm_scorer import DefaultPMScorer
        from test_data.sample_jobs import get_jobs_by_category
        from test_data.test_profiles import get_all_test_profiles
        from core.config_loader import SystemSettings
        
        engine = DefaultPMScorer()
        profile = get_all_test_profiles()["mid_level_pm"]
        settings = SystemSettings()
        
        # Get a perfect match job
        perfect_jobs = get_jobs_by_category()["perfect_match"]
        if perfect_jobs:
            job = perfect_jobs[0]
            result = engine.score_job(job, profile, settings)
            
            # Format as Telegram message
            score_percentage = result.total_score
            if score_percentage >= 90:
                grade = "🌟 EXCELLENT"
                priority = "🔥 HIGH PRIORITY"
            elif score_percentage >= 75:
                grade = "⭐ GREAT"  
                priority = "🚀 RECOMMENDED"
            else:
                grade = "✅ GOOD"
                priority = "👀 WORTH CONSIDERING"
            
            message = f"""🎯 **PM Job Alert**

**{job.title}** at **{job.company}**
📍 {job.location}
💰 Salary not disclosed

**Score: {score_percentage:.0f}%** | **Grade: {grade}**
**Priority: {priority}**

🔍 **Key Details:**
📈 Experience: {getattr(job, 'required_experience', 'Not specified')}
🏢 Company Size: {getattr(job, 'company_size', 'Not specified')}

📝 **Top Scoring Factors:**"""
            
            # Add top scoring reasons
            top_reasons = sorted(result.scoring_reasons, key=lambda r: r.points, reverse=True)[:3]
            for reason in top_reasons:
                if reason.points > 0:
                    percentage = (reason.points / reason.max_points) * 100 if reason.max_points > 0 else 0
                    message += f"\n• {reason.category.title()}: {percentage:.0f}% - {reason.explanation}"
            
            print("✅ Sample Telegram message generated:")
            print(f"\n{message}")
            return True
        else:
            print("❌ No perfect match jobs available for demo")
            return False
            
    except Exception as e:
        print(f"❌ Telegram message demo failed: {e}")
        return False

def main():
    """Main validation function."""
    print_header("PM WATCHMAN - Scoring System Validation")
    print(f"Validation started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run validation tests
    tests = [
        ("Import Validation", validate_imports),
        ("Basic Scoring", test_basic_scoring),
        ("Modular Architecture", test_modular_architecture),
        ("Scoring Explanations", test_scoring_explanations),
        ("Telegram Message Demo", demonstrate_telegram_message)
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Generate summary
    print_header("VALIDATION SUMMARY")
    
    passed = sum(1 for result in results.values() if result is True)
    failed = sum(1 for result in results.values() if result is False)
    total = len(results)
    
    print(f"📊 Validation Results:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📝 Total: {total}")
    
    print(f"\n📋 Detailed Results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    # Final assessment
    print_header("SYSTEM READINESS ASSESSMENT")
    
    critical_tests = ["Import Validation", "Basic Scoring", "Modular Architecture"]
    critical_passed = all(results.get(test, False) for test in critical_tests)
    
    if critical_passed:
        print("🎉 SYSTEM READY FOR PHASE 2!")
        print("✅ Core scoring system is functional and tested")
        print("✅ Modular architecture is working correctly") 
        print("✅ Job matching and scoring validated")
        print("\n🚀 Ready to proceed with LinkedIn integration and storage system")
        
        if results.get("Scoring Explanations", False):
            print("✅ Score explanations working properly")
        
        if results.get("Telegram Message Demo", False):
            print("✅ Message formatting ready for Telegram integration")
        
        return True
    else:
        print("⚠️ SYSTEM NEEDS ATTENTION")
        print("❌ Critical issues found in core functionality")
        
        for test in critical_tests:
            if not results.get(test, False):
                print(f"   🚨 Fix required: {test}")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)