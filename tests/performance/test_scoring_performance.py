"""
Scoring System Performance Tests

Tests performance characteristics of the modular scoring system:
- Scoring speed for individual jobs
- Batch processing performance  
- Memory usage patterns
- Scalability with large datasets
"""

import unittest
import sys
import os
import time
import tracemalloc
from statistics import mean, stdev

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.default_pm_scorer import DefaultPMScorer
from core.config_loader import SystemSettings

# Import test data
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from test_data.sample_jobs import create_test_jobs
from test_data.test_profiles import get_all_test_profiles


class TestScoringPerformance(unittest.TestCase):
    """Test scoring system performance characteristics."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.scoring_engine = DefaultPMScorer()
        self.pm_profile = get_all_test_profiles()["mid_level_pm"]
        self.system_settings = SystemSettings()
        self.test_jobs = create_test_jobs()
    
    def test_single_job_scoring_speed(self):
        """Test speed of scoring individual jobs."""
        test_job = self.test_jobs[0]
        iterations = 100
        
        # Warm up
        for _ in range(10):
            self.scoring_engine.score_job(test_job, self.pm_profile, self.system_settings)
        
        # Measure performance
        start_time = time.time()
        
        for _ in range(iterations):
            result = self.scoring_engine.score_job(test_job, self.pm_profile, self.system_settings)
            self.assertIsNotNone(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_job = total_time / iterations
        
        print(f"\nSingle Job Scoring Performance:")
        print(f"  Total time for {iterations} jobs: {total_time:.3f}s")
        print(f"  Average time per job: {avg_time_per_job*1000:.2f}ms")
        print(f"  Jobs per second: {iterations/total_time:.1f}")
        
        # Performance assertion: should score jobs reasonably quickly
        self.assertLess(avg_time_per_job, 0.1, "Single job scoring should take less than 100ms")
        self.assertGreater(iterations/total_time, 10, "Should process at least 10 jobs per second")
    
    def test_batch_scoring_performance(self):
        """Test performance of batch job scoring."""
        batch_sizes = [10, 50, 100]
        
        results = {}
        
        for batch_size in batch_sizes:
            test_batch = (self.test_jobs * (batch_size // len(self.test_jobs) + 1))[:batch_size]
            
            # Warm up
            self.scoring_engine.score_jobs(test_batch[:5], self.pm_profile, self.system_settings)
            
            # Measure performance
            start_time = time.time()
            scores = self.scoring_engine.score_jobs(test_batch, self.pm_profile, self.system_settings)
            end_time = time.time()
            
            total_time = end_time - start_time
            avg_time_per_job = total_time / batch_size
            jobs_per_second = batch_size / total_time
            
            results[batch_size] = {
                'total_time': total_time,
                'avg_time_per_job': avg_time_per_job,
                'jobs_per_second': jobs_per_second
            }
            
            # Validate results
            self.assertEqual(len(scores), batch_size)
            
            print(f"\nBatch Scoring Performance ({batch_size} jobs):")
            print(f"  Total time: {total_time:.3f}s")
            print(f"  Average time per job: {avg_time_per_job*1000:.2f}ms")
            print(f"  Jobs per second: {jobs_per_second:.1f}")
        
        # Performance assertions
        for batch_size, metrics in results.items():
            self.assertLess(metrics['avg_time_per_job'], 0.05, 
                          f"Batch scoring should average <50ms per job (batch size {batch_size})")
            self.assertGreater(metrics['jobs_per_second'], 20,
                             f"Batch scoring should process >20 jobs/sec (batch size {batch_size})")
    
    def test_scoring_scalability(self):
        """Test scoring performance with increasing dataset sizes."""
        dataset_sizes = [10, 50, 100, 200]
        times = []
        
        for size in dataset_sizes:
            # Create dataset of specified size
            test_dataset = (self.test_jobs * (size // len(self.test_jobs) + 1))[:size]
            
            # Measure time
            start_time = time.time()
            scores = self.scoring_engine.score_jobs(test_dataset, self.pm_profile, self.system_settings)
            end_time = time.time()
            
            duration = end_time - start_time
            times.append(duration)
            
            self.assertEqual(len(scores), size)
            
            print(f"Dataset size {size}: {duration:.3f}s ({size/duration:.1f} jobs/sec)")
        
        # Check for roughly linear scaling
        # Time should scale roughly linearly with dataset size
        time_per_job_ratios = []
        for i in range(1, len(times)):
            size_ratio = dataset_sizes[i] / dataset_sizes[i-1]
            time_ratio = times[i] / times[i-1]
            time_per_job_ratio = time_ratio / size_ratio
            time_per_job_ratios.append(time_per_job_ratio)
        
        # Scaling should be reasonable (not exponential)
        avg_scaling_factor = mean(time_per_job_ratios)
        print(f"\nAverage scaling factor: {avg_scaling_factor:.2f}")
        print("(1.0 = perfect linear scaling, >2.0 = potential performance issues)")
        
        self.assertLess(avg_scaling_factor, 2.0, "Scoring should scale roughly linearly")
    
    def test_memory_usage(self):
        """Test memory usage patterns during scoring."""
        tracemalloc.start()
        
        # Baseline memory
        baseline_snapshot = tracemalloc.take_snapshot()
        baseline_stats = baseline_snapshot.statistics('lineno')
        baseline_memory = sum(stat.size for stat in baseline_stats)
        
        # Score many jobs
        large_dataset = self.test_jobs * 20  # 300+ jobs
        scores = self.scoring_engine.score_jobs(large_dataset, self.pm_profile, self.system_settings)
        
        # Memory after scoring
        final_snapshot = tracemalloc.take_snapshot()
        final_stats = final_snapshot.statistics('lineno')
        final_memory = sum(stat.size for stat in final_stats)
        
        memory_increase = final_memory - baseline_memory
        memory_per_job = memory_increase / len(large_dataset)
        
        print(f"\nMemory Usage Analysis:")
        print(f"  Baseline memory: {baseline_memory / 1024 / 1024:.2f} MB")
        print(f"  Final memory: {final_memory / 1024 / 1024:.2f} MB")
        print(f"  Memory increase: {memory_increase / 1024 / 1024:.2f} MB")
        print(f"  Memory per job: {memory_per_job / 1024:.2f} KB")
        
        tracemalloc.stop()
        
        # Memory usage assertions
        self.assertLess(memory_increase / 1024 / 1024, 50, "Memory increase should be <50MB")
        self.assertLess(memory_per_job / 1024, 50, "Memory per job should be <50KB")
        
        # Validate all jobs were scored
        self.assertEqual(len(scores), len(large_dataset))
    
    def test_scorer_performance_breakdown(self):
        """Test performance of individual scorer components."""
        from core.scorers import TitleScorer, SkillsScorer, ExperienceScorer, IndustryScorer, CompanyScorer
        
        scorers = [
            ("Title", TitleScorer()),
            ("Skills", SkillsScorer()),
            ("Experience", ExperienceScorer()),
            ("Industry", IndustryScorer()),
            ("Company", CompanyScorer())
        ]
        
        test_job = self.test_jobs[0]
        iterations = 1000
        
        print(f"\nIndividual Scorer Performance ({iterations} iterations):")
        
        for name, scorer in scorers:
            # Warm up
            for _ in range(10):
                scorer.score_job(test_job, self.pm_profile, self.system_settings)
            
            # Measure performance
            start_time = time.time()
            
            for _ in range(iterations):
                result = scorer.score_job(test_job, self.pm_profile, self.system_settings)
                self.assertIsNotNone(result)
            
            end_time = time.time()
            duration = end_time - start_time
            avg_time = duration / iterations
            
            print(f"  {name:12}: {avg_time*1000:.3f}ms per job ({iterations/duration:.0f} jobs/sec)")
            
            # Performance assertion
            self.assertLess(avg_time, 0.01, f"{name} scorer should take <10ms per job")
    
    def test_configuration_change_performance(self):
        """Test performance impact of configuration changes."""
        test_job = self.test_jobs[0]
        iterations = 100
        
        # Baseline performance with default settings
        start_time = time.time()
        for _ in range(iterations):
            result = self.scoring_engine.score_job(test_job, self.pm_profile, self.system_settings)
        baseline_time = time.time() - start_time
        
        # Performance with configuration changes
        self.system_settings.title_match_importance = "low"
        self.system_settings.skills_match_importance = "high"
        
        start_time = time.time()
        for _ in range(iterations):
            result = self.scoring_engine.score_job(test_job, self.pm_profile, self.system_settings)
        modified_time = time.time() - start_time
        
        print(f"\nConfiguration Change Performance Impact:")
        print(f"  Baseline time: {baseline_time:.3f}s")
        print(f"  Modified time: {modified_time:.3f}s")
        print(f"  Performance change: {((modified_time - baseline_time) / baseline_time) * 100:+.1f}%")
        
        # Configuration changes should not significantly impact performance
        performance_change = abs(modified_time - baseline_time) / baseline_time
        self.assertLess(performance_change, 0.2, "Config changes should not impact performance >20%")
    
    def test_concurrent_scoring_simulation(self):
        """Simulate concurrent scoring scenarios.""" 
        import threading
        import queue
        
        num_threads = 4
        jobs_per_thread = 25
        results_queue = queue.Queue()
        
        def score_jobs_worker(jobs, thread_id):
            """Worker function for threading test."""
            start_time = time.time()
            scores = self.scoring_engine.score_jobs(jobs, self.pm_profile, self.system_settings)
            duration = time.time() - start_time
            results_queue.put((thread_id, len(scores), duration))
        
        # Create job batches
        job_batches = []
        for i in range(num_threads):
            batch = (self.test_jobs * (jobs_per_thread // len(self.test_jobs) + 1))[:jobs_per_thread]
            job_batches.append(batch)
        
        # Run concurrent scoring
        threads = []
        overall_start = time.time()
        
        for i in range(num_threads):
            thread = threading.Thread(target=score_jobs_worker, args=(job_batches[i], i))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        overall_duration = time.time() - overall_start
        
        # Collect results
        thread_results = []
        while not results_queue.empty():
            thread_results.append(results_queue.get())
        
        total_jobs_scored = sum(result[1] for result in thread_results)
        avg_thread_duration = mean(result[2] for result in thread_results)
        
        print(f"\nConcurrent Scoring Simulation:")
        print(f"  Threads: {num_threads}")
        print(f"  Jobs per thread: {jobs_per_thread}")
        print(f"  Total jobs: {total_jobs_scored}")
        print(f"  Overall duration: {overall_duration:.3f}s")
        print(f"  Average thread duration: {avg_thread_duration:.3f}s")
        print(f"  Overall throughput: {total_jobs_scored/overall_duration:.1f} jobs/sec")
        
        # Validate results
        self.assertEqual(len(thread_results), num_threads)
        self.assertEqual(total_jobs_scored, num_threads * jobs_per_thread)


class TestPerformanceRegression(unittest.TestCase):
    """Test for performance regressions."""
    
    def test_scoring_performance_benchmarks(self):
        """Establish performance benchmarks for regression testing."""
        engine = DefaultPMScorer()
        profile = get_all_test_profiles()["mid_level_pm"]
        settings = SystemSettings()
        test_jobs = create_test_jobs()
        
        # Single job benchmark
        start_time = time.time()
        for _ in range(100):
            engine.score_job(test_jobs[0], profile, settings)
        single_job_time = (time.time() - start_time) / 100
        
        # Batch benchmark
        start_time = time.time()
        engine.score_jobs(test_jobs, profile, settings)
        batch_time = time.time() - start_time
        batch_per_job_time = batch_time / len(test_jobs)
        
        print(f"\nPerformance Benchmarks:")
        print(f"  Single job scoring: {single_job_time*1000:.2f}ms")
        print(f"  Batch per-job time: {batch_per_job_time*1000:.2f}ms")
        print(f"  Batch efficiency gain: {single_job_time/batch_per_job_time:.1f}x")
        
        # Record benchmarks for regression testing
        # These values should be updated if performance improvements are made
        SINGLE_JOB_BENCHMARK_MS = 50.0  # 50ms per job maximum
        BATCH_PER_JOB_BENCHMARK_MS = 25.0  # 25ms per job maximum in batch
        
        self.assertLess(single_job_time * 1000, SINGLE_JOB_BENCHMARK_MS,
                       f"Single job scoring exceeds benchmark of {SINGLE_JOB_BENCHMARK_MS}ms")
        self.assertLess(batch_per_job_time * 1000, BATCH_PER_JOB_BENCHMARK_MS,
                       f"Batch scoring exceeds benchmark of {BATCH_PER_JOB_BENCHMARK_MS}ms per job")


if __name__ == "__main__":
    unittest.main(verbosity=2)