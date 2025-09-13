"""
Trading Project 004 - Performance Tester
Tests bulk data download performance with different configurations
"""

import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from batch_optimizer import BatchOptimizer, BatchStrategy
from logging_setup import get_logger
from rate_limiter import IBRateLimiter, Priority, RequestType


class TestScenario(Enum):
    """Different test scenarios"""

    SMALL_BATCH = "small_batch"  # 5 requests
    MEDIUM_BATCH = "medium_batch"  # 20 requests
    LARGE_BATCH = "large_batch"  # 50 requests
    MULTI_SYMBOL = "multi_symbol"  # Multiple symbols, same timeframe
    MULTI_TIMEFRAME = "multi_timeframe"  # Same symbol, multiple timeframes
    COMPREHENSIVE = "comprehensive"  # Multiple symbols and timeframes


@dataclass
class PerformanceMetrics:
    """Performance test results"""

    scenario: str
    strategy: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time_seconds: float
    average_request_time: float
    requests_per_minute: float
    rate_limit_hits: int
    retry_count: int
    success_rate_percentage: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percentage: Optional[float] = None


class PerformanceTester:
    """
    Performance tester for bulk data downloads
    Tests different configurations and strategies
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.test_results: List[PerformanceMetrics] = []

        # Test data configurations
        self.test_symbols = [
            "MSTR",
            "TSLA",
            "AAPL",
            "NVDA",
            "MSFT",
            "GOOGL",
            "AMZN",
            "META",
        ]
        self.test_timeframes = [
            ("1 D", "1 min"),
            ("1 D", "15 mins"),
            ("1 D", "1 hour"),
            ("5 D", "1 day"),
        ]

        self.logger.info("Performance Tester initialized")

    def run_scenario_test(
        self,
        scenario: TestScenario,
        strategy: BatchStrategy,
        enable_rate_limiting: bool = True,
    ) -> PerformanceMetrics:
        """
        Run a specific test scenario

        Args:
            scenario: Test scenario to run
            strategy: Batch strategy to use
            enable_rate_limiting: Whether to use rate limiting

        Returns:
            Performance metrics
        """
        self.logger.info(
            f"Running test: {scenario.value} with {strategy.value} strategy"
        )
        self.logger.info(
            f"Rate limiting: {'enabled' if enable_rate_limiting else 'disabled'}"
        )

        # Setup test environment
        rate_limiter = IBRateLimiter() if enable_rate_limiting else None
        if rate_limiter:
            rate_limiter.start_processing()

        batch_optimizer = BatchOptimizer(rate_limiter) if rate_limiter else None

        start_time = time.time()
        initial_stats = rate_limiter.get_stats() if rate_limiter else {}

        try:
            # Configure test based on scenario
            batch_id = self._create_test_batch(scenario, batch_optimizer)

            if batch_optimizer:
                # Execute batch with optimizer
                results = batch_optimizer.execute_batch(batch_id, strategy)
                successful_requests = results["completed"]
                failed_requests = results["failed"]
                total_requests = results["total_requests"]
            else:
                # Simulate direct execution (no rate limiting/batching)
                results = self._simulate_direct_execution(scenario)
                successful_requests = results["successful"]
                failed_requests = results["failed"]
                total_requests = results["total"]

        except Exception as e:
            self.logger.error(f"Test execution failed: {e}")
            successful_requests = 0
            failed_requests = 0
            total_requests = 0

        finally:
            if rate_limiter:
                rate_limiter.stop_processing()

        # Calculate metrics
        end_time = time.time()
        total_time = end_time - start_time

        final_stats = rate_limiter.get_stats() if rate_limiter else {}
        rate_limit_hits = final_stats.get(
            "rate_limited_requests", 0
        ) - initial_stats.get("rate_limited_requests", 0)
        retry_count = final_stats.get("retried_requests", 0) - initial_stats.get(
            "retried_requests", 0
        )

        metrics = PerformanceMetrics(
            scenario=scenario.value,
            strategy=strategy.value,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_time_seconds=total_time,
            average_request_time=total_time / max(total_requests, 1),
            requests_per_minute=(successful_requests / total_time) * 60
            if total_time > 0
            else 0,
            rate_limit_hits=rate_limit_hits,
            retry_count=retry_count,
            success_rate_percentage=(successful_requests / max(total_requests, 1))
            * 100,
        )

        self.test_results.append(metrics)
        self.logger.info(
            f"Test completed: {successful_requests}/{total_requests} successful in {total_time:.1f}s"
        )

        return metrics

    def _create_test_batch(
        self, scenario: TestScenario, batch_optimizer: BatchOptimizer
    ) -> str:
        """Create test batch based on scenario"""

        if scenario == TestScenario.SMALL_BATCH:
            # 5 requests: 5 symbols, 1 timeframe
            return batch_optimizer.create_multi_symbol_batch(
                symbols=self.test_symbols[:5],
                duration="1 D",
                bar_size="1 min",
                batch_name="small_batch_test",
            )

        elif scenario == TestScenario.MEDIUM_BATCH:
            # 20 requests: 5 symbols, 4 timeframes
            return batch_optimizer.create_comprehensive_batch(
                symbols=self.test_symbols[:5],
                timeframes=self.test_timeframes,
                batch_name="medium_batch_test",
            )

        elif scenario == TestScenario.LARGE_BATCH:
            # 32 requests: 8 symbols, 4 timeframes
            return batch_optimizer.create_comprehensive_batch(
                symbols=self.test_symbols,
                timeframes=self.test_timeframes,
                batch_name="large_batch_test",
            )

        elif scenario == TestScenario.MULTI_SYMBOL:
            # 8 symbols, same timeframe
            return batch_optimizer.create_multi_symbol_batch(
                symbols=self.test_symbols,
                duration="1 D",
                bar_size="1 min",
                batch_name="multi_symbol_test",
            )

        elif scenario == TestScenario.MULTI_TIMEFRAME:
            # 1 symbol, multiple timeframes
            return batch_optimizer.create_multi_timeframe_batch(
                symbol="MSTR",
                timeframes=self.test_timeframes,
                batch_name="multi_timeframe_test",
            )

        else:  # COMPREHENSIVE
            # All symbols, all timeframes
            return batch_optimizer.create_comprehensive_batch(
                symbols=self.test_symbols,
                timeframes=self.test_timeframes,
                batch_name="comprehensive_test",
            )

    def _simulate_direct_execution(self, scenario: TestScenario) -> Dict[str, int]:
        """Simulate direct execution without rate limiting for comparison"""

        # Determine number of requests based on scenario
        if scenario == TestScenario.SMALL_BATCH:
            total = 5
        elif scenario == TestScenario.MEDIUM_BATCH:
            total = 20
        elif scenario == TestScenario.LARGE_BATCH:
            total = 32
        elif scenario == TestScenario.MULTI_SYMBOL:
            total = 8
        elif scenario == TestScenario.MULTI_TIMEFRAME:
            total = 4
        else:  # COMPREHENSIVE
            total = 32

        # Simulate execution time (shorter without rate limiting)
        simulated_time_per_request = 0.1  # Much faster without rate limiting
        time.sleep(total * simulated_time_per_request)

        # Assume high success rate without rate limiting
        successful = int(total * 0.95)  # 95% success rate
        failed = total - successful

        return {"total": total, "successful": successful, "failed": failed}

    def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """
        Run comprehensive test suite with different configurations

        Returns:
            Complete test results and analysis
        """
        self.logger.info("Starting comprehensive performance test suite")

        # Test configurations
        test_configs = [
            # Small batches
            (TestScenario.SMALL_BATCH, BatchStrategy.SEQUENTIAL, True),
            (TestScenario.SMALL_BATCH, BatchStrategy.PARALLEL_SYMBOL, True),
            # Medium batches
            (TestScenario.MEDIUM_BATCH, BatchStrategy.SEQUENTIAL, True),
            (TestScenario.MEDIUM_BATCH, BatchStrategy.PARALLEL_TIMEFRAME, True),
            (TestScenario.MEDIUM_BATCH, BatchStrategy.MIXED_PARALLEL, True),
            # Large batches
            (TestScenario.LARGE_BATCH, BatchStrategy.PARALLEL_TIMEFRAME, True),
            (TestScenario.LARGE_BATCH, BatchStrategy.MIXED_PARALLEL, True),
            # Specialized scenarios
            (TestScenario.MULTI_SYMBOL, BatchStrategy.PARALLEL_SYMBOL, True),
            (TestScenario.MULTI_TIMEFRAME, BatchStrategy.PARALLEL_TIMEFRAME, True),
            # Comparison without rate limiting
            (TestScenario.MEDIUM_BATCH, BatchStrategy.SEQUENTIAL, False),
        ]

        total_tests = len(test_configs)
        completed_tests = 0

        for scenario, strategy, rate_limiting in test_configs:
            completed_tests += 1
            self.logger.info(f"Progress: {completed_tests}/{total_tests} tests")

            try:
                self.run_scenario_test(scenario, strategy, rate_limiting)
                # Brief pause between tests
                time.sleep(2)
            except Exception as e:
                self.logger.error(
                    f"Test failed: {scenario.value} + {strategy.value} - {e}"
                )

        # Analyze results
        analysis = self._analyze_results()

        self.logger.info("Comprehensive test suite completed")
        return analysis

    def _analyze_results(self) -> Dict[str, Any]:
        """Analyze test results and provide insights"""

        if not self.test_results:
            return {"error": "No test results available"}

        # Overall statistics
        total_tests = len(self.test_results)
        avg_success_rate = statistics.mean(
            [r.success_rate_percentage for r in self.test_results]
        )
        avg_requests_per_minute = statistics.mean(
            [r.requests_per_minute for r in self.test_results]
        )

        # Best performing configurations
        best_by_speed = max(self.test_results, key=lambda r: r.requests_per_minute)
        best_by_success = max(
            self.test_results, key=lambda r: r.success_rate_percentage
        )

        # Rate limiting impact analysis
        rate_limited_tests = [
            r
            for r in self.test_results
            if "rate_limiting" not in r.strategy or r.rate_limit_hits > 0
        ]
        non_rate_limited_tests = [
            r for r in self.test_results if r.rate_limit_hits == 0
        ]

        # Strategy comparison
        strategy_performance = {}
        for result in self.test_results:
            strategy = result.strategy
            if strategy not in strategy_performance:
                strategy_performance[strategy] = []
            strategy_performance[strategy].append(result)

        strategy_summary = {}
        for strategy, results in strategy_performance.items():
            strategy_summary[strategy] = {
                "avg_success_rate": statistics.mean(
                    [r.success_rate_percentage for r in results]
                ),
                "avg_requests_per_minute": statistics.mean(
                    [r.requests_per_minute for r in results]
                ),
                "avg_rate_limit_hits": statistics.mean(
                    [r.rate_limit_hits for r in results]
                ),
                "tests_count": len(results),
            }

        analysis = {
            "summary": {
                "total_tests": total_tests,
                "average_success_rate": avg_success_rate,
                "average_requests_per_minute": avg_requests_per_minute,
            },
            "best_performers": {
                "fastest": {
                    "scenario": best_by_speed.scenario,
                    "strategy": best_by_speed.strategy,
                    "requests_per_minute": best_by_speed.requests_per_minute,
                },
                "most_reliable": {
                    "scenario": best_by_success.scenario,
                    "strategy": best_by_success.strategy,
                    "success_rate": best_by_success.success_rate_percentage,
                },
            },
            "strategy_comparison": strategy_summary,
            "rate_limiting_impact": {
                "tests_with_rate_limiting": len(rate_limited_tests),
                "tests_without_rate_limiting": len(non_rate_limited_tests),
                "avg_rate_limit_hits": statistics.mean(
                    [r.rate_limit_hits for r in rate_limited_tests]
                )
                if rate_limited_tests
                else 0,
            },
            "detailed_results": [
                {
                    "scenario": r.scenario,
                    "strategy": r.strategy,
                    "success_rate": r.success_rate_percentage,
                    "requests_per_minute": r.requests_per_minute,
                    "total_time": r.total_time_seconds,
                    "rate_limit_hits": r.rate_limit_hits,
                }
                for r in self.test_results
            ],
        }

        return analysis

    def generate_performance_report(self, analysis: Dict[str, Any]) -> str:
        """Generate human-readable performance report"""

        report = []
        report.append("=" * 80)
        report.append("PERFORMANCE TEST REPORT")
        report.append("=" * 80)

        # Summary
        summary = analysis["summary"]
        report.append(f"\nOVERALL RESULTS:")
        report.append(f"  Tests conducted: {summary['total_tests']}")
        report.append(f"  Average success rate: {summary['average_success_rate']:.1f}%")
        report.append(
            f"  Average requests per minute: {summary['average_requests_per_minute']:.1f}"
        )

        # Best performers
        fastest = analysis["best_performers"]["fastest"]
        most_reliable = analysis["best_performers"]["most_reliable"]

        report.append(f"\nBEST PERFORMERS:")
        report.append(f"  Fastest configuration:")
        report.append(f"    Scenario: {fastest['scenario']}")
        report.append(f"    Strategy: {fastest['strategy']}")
        report.append(
            f"    Speed: {fastest['requests_per_minute']:.1f} requests/minute"
        )

        report.append(f"  Most reliable configuration:")
        report.append(f"    Scenario: {most_reliable['scenario']}")
        report.append(f"    Strategy: {most_reliable['strategy']}")
        report.append(f"    Success rate: {most_reliable['success_rate']:.1f}%")

        # Strategy comparison
        report.append(f"\nSTRATEGY COMPARISON:")
        for strategy, stats in analysis["strategy_comparison"].items():
            report.append(f"  {strategy}:")
            report.append(f"    Success rate: {stats['avg_success_rate']:.1f}%")
            report.append(f"    Requests/min: {stats['avg_requests_per_minute']:.1f}")
            report.append(f"    Rate limit hits: {stats['avg_rate_limit_hits']:.1f}")
            report.append(f"    Tests: {stats['tests_count']}")

        # Recommendations
        report.append(f"\nRECOMMendations:")

        # Find best overall strategy
        best_strategy = max(
            analysis["strategy_comparison"].items(),
            key=lambda x: x[1]["avg_success_rate"]
            + x[1]["avg_requests_per_minute"] / 10,
        )

        report.append(f"  1. Recommended strategy: {best_strategy[0]}")
        report.append(f"     - Balanced performance and reliability")

        if analysis["rate_limiting_impact"]["avg_rate_limit_hits"] > 0:
            report.append(f"  2. Rate limiting is working effectively")
            report.append(
                f"     - Average {analysis['rate_limiting_impact']['avg_rate_limit_hits']:.1f} rate limit hits per test"
            )
            report.append(f"     - Helps prevent API overload")

        report.append(f"  3. For large-scale downloads:")
        report.append(f"     - Use MIXED_PARALLEL strategy for best balance")
        report.append(f"     - Enable rate limiting to avoid API limits")
        report.append(
            f"     - Consider breaking very large requests into smaller batches"
        )

        report.append("=" * 80)

        return "\n".join(report)

    def save_results_to_csv(self, filename: str = None):
        """Save test results to CSV file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_test_results_{timestamp}.csv"

        # Convert results to DataFrame
        data = []
        for result in self.test_results:
            data.append(
                {
                    "scenario": result.scenario,
                    "strategy": result.strategy,
                    "total_requests": result.total_requests,
                    "successful_requests": result.successful_requests,
                    "failed_requests": result.failed_requests,
                    "total_time_seconds": result.total_time_seconds,
                    "average_request_time": result.average_request_time,
                    "requests_per_minute": result.requests_per_minute,
                    "rate_limit_hits": result.rate_limit_hits,
                    "retry_count": result.retry_count,
                    "success_rate_percentage": result.success_rate_percentage,
                }
            )

        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        self.logger.info(f"Results saved to {filename}")
        return filename


def main():
    """Demo of performance testing"""
    print("=" * 80)
    print("Performance Testing Demo")
    print("=" * 80)

    tester = PerformanceTester()

    # Run a few quick tests
    print("Running quick performance tests...")

    # Test 1: Small batch sequential
    result1 = tester.run_scenario_test(
        TestScenario.SMALL_BATCH, BatchStrategy.SEQUENTIAL, enable_rate_limiting=True
    )
    print(
        f"Test 1 - Small Sequential: {result1.success_rate_percentage:.1f}% success, "
        f"{result1.requests_per_minute:.1f} req/min"
    )

    # Test 2: Small batch parallel
    result2 = tester.run_scenario_test(
        TestScenario.SMALL_BATCH,
        BatchStrategy.PARALLEL_SYMBOL,
        enable_rate_limiting=True,
    )
    print(
        f"Test 2 - Small Parallel: {result2.success_rate_percentage:.1f}% success, "
        f"{result2.requests_per_minute:.1f} req/min"
    )

    # Analysis
    analysis = tester._analyze_results()
    report = tester.generate_performance_report(analysis)
    print("\n" + report)

    # Save results
    csv_file = tester.save_results_to_csv()
    print(f"\nResults saved to: {csv_file}")


if __name__ == "__main__":
    main()
