#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Tester - Trading Project 004
Tests database performance with large datasets (3M+ records)
"""

import os
import sys
import time
import statistics
from datetime import datetime, timedelta
from random import random, randint, choice
from typing import Dict, List, Any

# Add src to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_storage_service import DataStorageService
from database_manager import DatabaseManager


class PerformanceTester:
    """Database performance tester for Trading Project 004"""

    def __init__(self, database_url: str = None):
        """Initialize Performance Tester"""
        self.storage_service = DataStorageService(database_url)
        self.db_manager = DatabaseManager(database_url)

        # Test configuration
        self.test_symbols = ['AAPL', 'MSTR', 'TSLA', 'NVDA', 'GOOGL', 'MSFT']
        self.test_timeframes = ['1min', '15min', '1hour', '4hour', 'daily']

        # Performance tracking
        self.performance_results = {
            'bulk_insert': {},
            'query_performance': {}
        }

    def run_complete_performance_test(
        self,
        record_counts: List[int] = None,
        include_quality_validation: bool = True
    ) -> Dict[str, Any]:
        """Run comprehensive performance test suite"""
        if record_counts is None:
            record_counts = [10000, 100000, 1000000, 3000000]  # 10K, 100K, 1M, 3M

        print("🚀 Starting Performance Test Suite")
        print("=" * 60)
        print(f"📊 Test Record Counts: {[f'{count:,}' for count in record_counts]}")
        print(f"🔧 Quality Validation: {'Enabled' if include_quality_validation else 'Disabled'}")
        print("=" * 60)

        test_start = datetime.now()

        try:
            # Test 1: Bulk Insert Performance
            print("\n🎯 Test 1: Bulk Insert Performance")
            self._test_bulk_insert_performance(record_counts, include_quality_validation)

            # Test 2: Query Performance
            print("\n🎯 Test 2: Query Performance")
            self._test_query_performance()

            # Generate comprehensive report
            test_end = datetime.now()
            execution_time = (test_end - test_start).total_seconds()

            return {
                'status': 'completed',
                'execution_time': execution_time,
                'results': self.performance_results,
                'summary': self._generate_performance_summary(),
                'recommendations': self._generate_recommendations()
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'execution_time': (datetime.now() - test_start).total_seconds()
            }

    def _test_bulk_insert_performance(
        self,
        record_counts: List[int],
        include_validation: bool
    ) -> None:
        """Test bulk insert performance with various record counts"""
        for count in record_counts:
            print(f"\n  📦 Testing bulk insert with {count:,} records...")

            # Generate test data
            print(f"    🎲 Generating {count:,} mock records...")
            start_time = time.time()
            test_data = self._generate_mock_data(count)
            data_generation_time = time.time() - start_time

            # Test bulk insert
            print(f"    💾 Inserting {count:,} records...")
            insert_start = time.time()

            result = self.storage_service.bulk_insert_ib_data(
                data_records=test_data,
                validate_quality=include_validation,
                min_quality_score=95.0 if include_validation else 0.0
            )

            insert_time = time.time() - insert_start

            # Calculate performance metrics
            records_per_second = count / insert_time if insert_time > 0 else 0

            self.performance_results['bulk_insert'][f'{count:,}_records'] = {
                'record_count': count,
                'data_generation_time': data_generation_time,
                'insert_time': insert_time,
                'records_per_second': records_per_second,
                'inserted_count': result.get('inserted', 0),
                'rejected_count': result.get('rejected', 0),
                'validation_enabled': include_validation
            }

            print(f"    ✅ Completed: {result.get('inserted', 0):,} inserted, {result.get('rejected', 0):,} rejected")
            print(f"    ⚡ Performance: {records_per_second:,.0f} records/sec")

            # Clean up for next test
            self._cleanup_test_data()

    def _test_query_performance(self) -> None:
        """Test query performance with various filters"""
        # Insert some test data for querying
        test_data = self._generate_mock_data(100000)  # 100K records
        self.storage_service.bulk_insert_ib_data(test_data, validate_quality=False)

        query_tests = [
            {
                'name': 'symbol_filter',
                'params': {'symbol': 'AAPL'},
                'description': 'Query by symbol'
            },
            {
                'name': 'date_range',
                'params': {
                    'start_date': datetime.now() - timedelta(days=30),
                    'end_date': datetime.now() - timedelta(days=1)
                },
                'description': 'Query by date range (30 days)'
            },
            {
                'name': 'trading_hours_only',
                'params': {'trading_hours_only': True},
                'description': 'Query trading hours only'
            },
            {
                'name': 'combined_filters',
                'params': {
                    'symbol': 'MSTR',
                    'trading_hours_only': True,
                    'limit': 10000
                },
                'description': 'Combined filters query'
            }
        ]

        for test in query_tests:
            print(f"\n  🔍 Testing: {test['description']}")

            start_time = time.time()
            results = self.storage_service.query_historical_data(**test['params'])
            query_time = time.time() - start_time

            self.performance_results['query_performance'][test['name']] = {
                'description': test['description'],
                'query_time': query_time,
                'results_count': len(results),
                'records_per_second': len(results) / query_time if query_time > 0 else 0
            }

            print(f"    ✅ Found {len(results):,} records in {query_time:.3f}s")
            print(f"    ⚡ Speed: {len(results) / query_time if query_time > 0 else 0:,.0f} records/sec")

        # Cleanup
        self._cleanup_test_data()

    def _generate_mock_data(self, count: int) -> List[Dict[str, Any]]:
        """Generate mock historical data for testing"""
        mock_data = []
        base_time = datetime.now() - timedelta(days=365)

        for i in range(count):
            # Create realistic OHLCV data
            base_price = 100 + random() * 400  # Price between $100-500
            volatility = 0.02 + random() * 0.08  # 2-10% volatility

            open_price = base_price
            close_price = open_price * (1 + (random() - 0.5) * volatility)
            high_price = max(open_price, close_price) * (1 + random() * volatility * 0.5)
            low_price = min(open_price, close_price) * (1 - random() * volatility * 0.5)

            volume = randint(10000, 1000000)

            record = {
                'symbol': choice(self.test_symbols),
                'timestamp': base_time + timedelta(minutes=i),
                'timeframe': choice(self.test_timeframes),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume,
                'data_source': 'MOCK_TEST'
            }

            mock_data.append(record)

        return mock_data

    def _cleanup_test_data(self) -> None:
        """Clean up test data from database"""
        try:
            # Delete all mock test data
            with self.db_manager.session_scope() as session:
                from database_models import HistoricalData
                deleted = session.query(HistoricalData).filter(
                    HistoricalData.source == 'MOCK_TEST'
                ).delete()
                session.commit()
                print(f"    🧹 Cleaned up {deleted:,} test records")
        except Exception as e:
            print(f"    ⚠️ Cleanup warning: {str(e)}")

    def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate performance test summary"""
        return {
            'bulk_insert_summary': self._summarize_bulk_insert(),
            'query_summary': self._summarize_query_performance()
        }

    def _summarize_bulk_insert(self) -> Dict[str, Any]:
        """Summarize bulk insert performance"""
        bulk_results = self.performance_results.get('bulk_insert', {})
        if not bulk_results:
            return {}

        speeds = [result['records_per_second'] for result in bulk_results.values()]
        return {
            'max_speed_rps': max(speeds) if speeds else 0,
            'avg_speed_rps': statistics.mean(speeds) if speeds else 0,
            'total_records_tested': sum(result['record_count'] for result in bulk_results.values())
        }

    def _summarize_query_performance(self) -> Dict[str, Any]:
        """Summarize query performance"""
        query_results = self.performance_results.get('query_performance', {})
        if not query_results:
            return {}

        times = [result['query_time'] for result in query_results.values()]
        return {
            'fastest_query_time': min(times) if times else 0,
            'slowest_query_time': max(times) if times else 0,
            'avg_query_time': statistics.mean(times) if times else 0
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate performance recommendations based on test results"""
        recommendations = []

        # Analyze bulk insert performance
        bulk_results = self.performance_results.get('bulk_insert', {})
        if bulk_results:
            speeds = [result['records_per_second'] for result in bulk_results.values()]
            avg_speed = statistics.mean(speeds) if speeds else 0

            if avg_speed < 1000:
                recommendations.append("Consider increasing batch size for bulk inserts")
            elif avg_speed > 10000:
                recommendations.append("Excellent bulk insert performance - configuration is optimal")

        if not recommendations:
            recommendations.append("All performance metrics are within acceptable ranges")

        return recommendations


# Example usage
if __name__ == "__main__":
    tester = PerformanceTester()
    print("🎯 Performance Tester initialized successfully!")

    # Run small test (commented out for safety)
    # result = tester.run_complete_performance_test(
    #     record_counts=[1000, 10000],  # Small test
    #     include_quality_validation=True
    # )
    # print(f"Test completed: {result}")