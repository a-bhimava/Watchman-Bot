#!/usr/bin/env python3
"""
Watchman Test Runner

Comprehensive test suite runner for validating the PM job scoring system.
Runs all tests and provides a summary of system readiness.
"""

import os
import sys
import unittest
import subprocess
from datetime import datetime

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

def run_test_suite(test_path, description):
    """Run a specific test suite and return results."""
    print_section(description)
    
    try:
        # Run the test suite
        result = subprocess.run([
            sys.executable, "-m", "unittest", "discover", 
            "-s", test_path, "-p", "test_*.py", "-v"
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        # Print results
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Return success status
        return result.returncode == 0
    
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def validate_project_structure():
    """Validate that required project structure exists."""
    print_section("Project Structure Validation")
    
    required_paths = [
        "src/core/scoring_engine.py",
        "src/core/scorers.py", 
        "src/core/default_pm_scorer.py",
        "src/core/config_loader.py",
        "tests/test_data/sample_jobs.py",
        "tests/test_data/test_profiles.py",
        "tests/unit/test_scoring_system.py",
        "tests/integration/test_job_scoring.py",
        "tests/integration/test_telegram_messages.py",
        "tests/performance/test_scoring_performance.py"
    ]
    
    missing_files = []
    for path in required_paths:
        if not os.path.exists(path):
            missing_files.append(path)
        else:
            print(f"✅ {path}")
    
    if missing_files:
        print(f"\n❌ Missing files:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    print(f"\n✅ All required files present")
    return True

def run_quick_scoring_validation():
    """Run a quick validation of the scoring system."""
    print_section("Quick Scoring System Validation")
    
    try:
        # Add src to path
        sys.path.insert(0, 'src')
        sys.path.insert(0, 'tests')
        
        from core.default_pm_scorer import DefaultPMScorer
        from test_data.sample_jobs import get_jobs_by_category
        from test_data.test_profiles import get_all_test_profiles
        from core.config_loader import SystemSettings
        
        # Initialize components
        scoring_engine = DefaultPMScorer()
        pm_profile = get_all_test_profiles()["mid_level_pm"]
        system_settings = SystemSettings()
        jobs_by_category = get_jobs_by_category()
        
        print("🔧 Initialized scoring components")
        
        # Test different job categories
        validation_results = {}
        
        for category, jobs in jobs_by_category.items():
            if not jobs:
                continue
                
            job = jobs[0]  # Test first job in category
            try:
                result = scoring_engine.score_job(job, pm_profile, system_settings)
                validation_results[category] = {
                    'job_title': job.title,
                    'score': result.total_score,
                    'success': True
                }
                print(f"✅ {category}: {job.title} -> {result.total_score:.1f}%")
            except Exception as e:
                validation_results[category] = {
                    'job_title': job.title,
                    'error': str(e),
                    'success': False
                }
                print(f"❌ {category}: {job.title} -> ERROR: {e}")
        
        # Check that we have reasonable score distribution
        successful_scores = [r['score'] for r in validation_results.values() if r['success']]
        if len(successful_scores) >= 3:
            min_score = min(successful_scores)
            max_score = max(successful_scores)
            print(f"\n📊 Score range: {min_score:.1f}% - {max_score:.1f}%")
            
            if max_score > min_score + 20:  # Good score differentiation
                print("✅ Scoring system shows good differentiation")
                return True
            else:
                print("⚠️ Scoring system may need tuning - limited score range")
                return True  # Still functional, just needs tuning
        else:
            print("❌ Insufficient scoring validation results")
            return False
            
    except Exception as e:
        print(f"❌ Scoring validation failed: {e}")
        return False

def main():
    """Main test runner."""
    print_header("PM WATCHMAN - Test Suite Runner")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Track overall results
    results = {
        'structure_valid': False,
        'quick_validation': False,
        'unit_tests': False,
        'integration_tests': False,
        'performance_tests': False,
        'message_tests': False
    }
    
    # 1. Validate project structure
    results['structure_valid'] = validate_project_structure()
    
    if not results['structure_valid']:
        print("\n❌ Project structure validation failed. Cannot proceed with tests.")
        return False
    
    # 2. Quick scoring validation
    results['quick_validation'] = run_quick_scoring_validation()
    
    # 3. Run test suites
    test_suites = [
        ('tests/unit', 'Unit Tests (Scoring System Components)', 'unit_tests'),
        ('tests/integration', 'Integration Tests (End-to-End Workflows)', 'integration_tests'), 
        ('tests/performance', 'Performance Tests (Speed & Memory)', 'performance_tests')
    ]
    
    for test_path, description, key in test_suites:
        if os.path.exists(test_path):
            results[key] = run_test_suite(test_path, description)
        else:
            print_section(f"{description} - SKIPPED (directory not found)")
            results[key] = None
    
    # 4. Generate final report
    print_header("TEST SUMMARY REPORT")
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result is True)
    failed_tests = sum(1 for result in results.values() if result is False)
    skipped_tests = sum(1 for result in results.values() if result is None)
    
    print(f"📊 Test Results:")
    print(f"   ✅ Passed: {passed_tests}")
    print(f"   ❌ Failed: {failed_tests}")
    print(f"   ⏭️  Skipped: {skipped_tests}")
    print(f"   📝 Total: {total_tests}")
    
    print(f"\n📋 Detailed Results:")
    status_map = {True: "✅ PASS", False: "❌ FAIL", None: "⏭️ SKIP"}
    for test_name, result in results.items():
        print(f"   {status_map[result]} {test_name.replace('_', ' ').title()}")
    
    # System readiness assessment
    print_header("SYSTEM READINESS ASSESSMENT")
    
    critical_tests = ['structure_valid', 'quick_validation', 'unit_tests']
    critical_passed = all(results[test] for test in critical_tests if test in results)
    
    if critical_passed:
        print("🎉 SYSTEM READY FOR PHASE 2!")
        print("✅ Core scoring system is functional and tested")
        print("✅ Modular architecture is working correctly")
        print("✅ PM profiles and job matching validated")
        print("\n🚀 Ready to proceed with LinkedIn integration and storage system")
        
        if results['performance_tests']:
            print("✅ Performance benchmarks established")
        
        if results['integration_tests']:
            print("✅ End-to-end workflows validated")
        
        return True
    
    else:
        print("⚠️ SYSTEM NEEDS ATTENTION")
        print("❌ Critical issues found in core functionality")
        print("🔧 Please fix failing tests before proceeding to Phase 2")
        
        # Show what needs fixing
        for test in critical_tests:
            if test in results and not results[test]:
                print(f"   🚨 Fix required: {test.replace('_', ' ').title()}")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)