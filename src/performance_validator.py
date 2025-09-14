#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Validator - Trading Project 004
Comprehensive validation and testing framework for DNA Research System

Features:
- Database performance testing
- API endpoint validation
- Data integrity verification
- System stress testing
- Performance benchmarks
"""

import sys
sys.path.append('src')

import time
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
import requests

from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, and_

from enhanced_dna_models import (
    create_enhanced_engine, EnhancedHistoricalData,
    TimeFrame, IndicatorTemplate
)


class PerformanceValidator:
    """Comprehensive performance validation for DNA Research System"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.engine = create_enhanced_engine()
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.test_results = []

    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()

    def log_test_result(self, test_name: str, status: str, duration: float = 0.0, details: Dict = None):
        """Log test result with timestamp and details"""
        result = {
            'test_name': test_name,
            'status': status,  # PASS/FAIL/WARNING
            'duration_seconds': round(duration, 3),
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        self.test_results.append(result)

        status_symbol = "[OK]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[WARN]"
        print(f"{status_symbol} {test_name:<40} | {status:<7} | {duration:.3f}s")

        if details and (status == "FAIL" or status == "WARNING"):
            for key, value in details.items():
                print(f"    {key}: {value}")

    def test_database_connectivity(self) -> bool:
        """Test database connection and basic operations"""
        start_time = time.time()

        try:
            # Test basic query
            count = self.session.query(EnhancedHistoricalData).count()

            # Test index performance
            query_start = time.time()
            symbol_count = self.session.query(EnhancedHistoricalData).filter(
                EnhancedHistoricalData.symbol == 'MSTR'
            ).count()
            query_time = time.time() - query_start

            duration = time.time() - start_time

            details = {
                'total_records': count,
                'mstr_records': symbol_count,
                'indexed_query_time': f"{query_time:.3f}s"
            }

            self.log_test_result("Database Connectivity", "PASS", duration, details)
            return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("Database Connectivity", "FAIL", duration, {'error': str(e)})
            return False

    def test_data_integrity(self) -> bool:
        """Test data integrity and constraints"""
        start_time = time.time()
        issues = []

        try:
            # Test 1: OHLC validation
            invalid_ohlc = self.session.query(EnhancedHistoricalData).filter(
                (EnhancedHistoricalData.high_price < EnhancedHistoricalData.low_price) |
                (EnhancedHistoricalData.high_price < EnhancedHistoricalData.open_price) |
                (EnhancedHistoricalData.high_price < EnhancedHistoricalData.close_price) |
                (EnhancedHistoricalData.low_price > EnhancedHistoricalData.open_price) |
                (EnhancedHistoricalData.low_price > EnhancedHistoricalData.close_price)
            ).count()

            if invalid_ohlc > 0:
                issues.append(f"Invalid OHLC data: {invalid_ohlc} records")

            # Test 2: DNA trade consistency
            invalid_dna = self.session.query(EnhancedHistoricalData).filter(
                and_(
                    EnhancedHistoricalData.dna_entry_signal == True,
                    EnhancedHistoricalData.dna_entry_price.is_(None)
                )
            ).count()

            if invalid_dna > 0:
                issues.append(f"DNA signals without entry price: {invalid_dna} records")

            # Test 3: Timeframe distribution
            timeframe_counts = {}
            for timeframe in TimeFrame:
                count = self.session.query(EnhancedHistoricalData).filter(
                    EnhancedHistoricalData.timeframe == timeframe
                ).count()
                timeframe_counts[timeframe.value] = count

            duration = time.time() - start_time

            if issues:
                self.log_test_result("Data Integrity", "WARNING", duration,
                                   {'issues': issues, 'timeframe_distribution': timeframe_counts})
                return False
            else:
                self.log_test_result("Data Integrity", "PASS", duration,
                                   {'timeframe_distribution': timeframe_counts})
                return True

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("Data Integrity", "FAIL", duration, {'error': str(e)})
            return False

    def test_api_endpoints(self) -> bool:
        """Test all FastAPI endpoints"""
        start_time = time.time()
        all_passed = True

        endpoints_to_test = [
            ('/docs', 'GET', None),
            ('/data/MSTR/1min', 'GET', None),
            ('/data/NVDA/daily?trading_hours_only=false', 'GET', None),
            ('/indicators/available', 'GET', None),
            ('/analysis/dna/MSTR', 'GET', None),
            ('/statistics/performance', 'GET', None)
        ]

        results = {}

        for endpoint, method, payload in endpoints_to_test:
            url = f"{self.api_base_url}{endpoint}"
            endpoint_start = time.time()

            try:
                if method == 'GET':
                    response = requests.get(url, timeout=10)
                elif method == 'POST':
                    response = requests.post(url, json=payload, timeout=10)

                endpoint_duration = time.time() - endpoint_start

                if response.status_code == 200:
                    results[endpoint] = {
                        'status': 'PASS',
                        'response_time': f"{endpoint_duration:.3f}s",
                        'content_length': len(response.content)
                    }
                else:
                    results[endpoint] = {
                        'status': 'FAIL',
                        'status_code': response.status_code,
                        'response_time': f"{endpoint_duration:.3f}s"
                    }
                    all_passed = False

            except requests.exceptions.RequestException as e:
                results[endpoint] = {
                    'status': 'FAIL',
                    'error': str(e)[:100]  # Truncate long errors
                }
                all_passed = False

        duration = time.time() - start_time
        status = "PASS" if all_passed else "FAIL"

        self.log_test_result("API Endpoints", status, duration, {'endpoints': results})
        return all_passed

    def test_query_performance(self) -> bool:
        """Test database query performance benchmarks"""
        start_time = time.time()

        performance_tests = []

        try:
            # Test 1: Simple symbol filter
            query_start = time.time()
            symbol_data = self.session.query(EnhancedHistoricalData).filter(
                EnhancedHistoricalData.symbol == 'MSTR'
            ).limit(1000).all()
            query_time = time.time() - query_start
            performance_tests.append({
                'test': 'Symbol Filter (1000 records)',
                'duration': f"{query_time:.3f}s",
                'records': len(symbol_data),
                'status': 'PASS' if query_time < 1.0 else 'WARNING'
            })

            # Test 2: Complex multi-filter query
            query_start = time.time()
            complex_data = self.session.query(EnhancedHistoricalData).filter(
                and_(
                    EnhancedHistoricalData.symbol == 'NVDA',
                    EnhancedHistoricalData.timeframe == TimeFrame.MIN_5,
                    EnhancedHistoricalData.is_trading_hours == True,
                    EnhancedHistoricalData.dna_entry_signal == True
                )
            ).all()
            query_time = time.time() - query_start
            performance_tests.append({
                'test': 'Multi-Filter with DNA Signals',
                'duration': f"{query_time:.3f}s",
                'records': len(complex_data),
                'status': 'PASS' if query_time < 0.5 else 'WARNING'
            })

            # Test 3: Aggregation query
            query_start = time.time()
            stats = self.session.query(
                func.count(EnhancedHistoricalData.id),
                func.avg(EnhancedHistoricalData.volume),
                func.sum(EnhancedHistoricalData.dna_pnl)
            ).filter(
                EnhancedHistoricalData.symbol == 'MSTR'
            ).first()
            query_time = time.time() - query_start
            performance_tests.append({
                'test': 'Aggregation Query',
                'duration': f"{query_time:.3f}s",
                'result': f"Count: {stats[0]}, Avg Vol: {float(stats[1] or 0):.0f}, Total PnL: ${float(stats[2] or 0)}",
                'status': 'PASS' if query_time < 0.3 else 'WARNING'
            })

            duration = time.time() - start_time

            # Determine overall status
            failing_tests = [t for t in performance_tests if t['status'] == 'WARNING']
            status = "WARNING" if failing_tests else "PASS"

            self.log_test_result("Query Performance", status, duration, {'tests': performance_tests})
            return status == "PASS"

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("Query Performance", "FAIL", duration, {'error': str(e)})
            return False

    def test_dna_simulation_accuracy(self) -> bool:
        """Test DNA simulation calculations"""
        start_time = time.time()

        try:
            # Get sample DNA trades
            dna_trades = self.session.query(EnhancedHistoricalData).filter(
                and_(
                    EnhancedHistoricalData.dna_entry_signal == True,
                    EnhancedHistoricalData.dna_pnl.isnot(None)
                )
            ).limit(10).all()

            if not dna_trades:
                duration = time.time() - start_time
                self.log_test_result("DNA Simulation Accuracy", "WARNING", duration,
                                   {'message': 'No DNA trades found for validation'})
                return False

            validation_results = []
            calculation_errors = 0

            for trade in dna_trades:
                # Verify PnL calculation
                expected_pnl = (trade.dna_exit_price - trade.dna_entry_price) * trade.dna_shares
                actual_pnl = trade.dna_pnl

                if abs(float(expected_pnl - actual_pnl)) > 0.01:  # Allow 1 cent tolerance
                    calculation_errors += 1

                # Verify stop loss/take profit levels
                expected_sl = trade.dna_entry_price - Decimal('2.8')
                expected_tp = trade.dna_entry_price + Decimal('3.2')

                validation_results.append({
                    'timestamp': trade.timestamp.isoformat(),
                    'entry_price': f"${trade.dna_entry_price}",
                    'exit_price': f"${trade.dna_exit_price}",
                    'expected_pnl': f"${expected_pnl:.2f}",
                    'actual_pnl': f"${actual_pnl:.2f}",
                    'pnl_match': abs(float(expected_pnl - actual_pnl)) <= 0.01,
                    'sl_correct': abs(float(trade.dna_stop_loss - expected_sl)) <= 0.01,
                    'tp_correct': abs(float(trade.dna_take_profit - expected_tp)) <= 0.01
                })

            duration = time.time() - start_time

            status = "FAIL" if calculation_errors > 0 else "PASS"
            details = {
                'total_trades_tested': len(dna_trades),
                'calculation_errors': calculation_errors,
                'sample_validations': validation_results[:3]  # Show first 3 for brevity
            }

            self.log_test_result("DNA Simulation Accuracy", status, duration, details)
            return status == "PASS"

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("DNA Simulation Accuracy", "FAIL", duration, {'error': str(e)})
            return False

    def test_system_stress(self) -> bool:
        """Stress test the system with concurrent operations"""
        start_time = time.time()

        try:
            # Rapid-fire API requests
            api_test_results = []
            for i in range(20):
                request_start = time.time()
                try:
                    response = requests.get(f"{self.api_base_url}/statistics/performance", timeout=5)
                    request_time = time.time() - request_start
                    api_test_results.append({
                        'request': i + 1,
                        'status_code': response.status_code,
                        'response_time': request_time
                    })
                except Exception as e:
                    api_test_results.append({
                        'request': i + 1,
                        'error': str(e)[:50]
                    })

            # Database stress test
            db_operations = []
            for i in range(10):
                op_start = time.time()
                count = self.session.query(EnhancedHistoricalData).filter(
                    EnhancedHistoricalData.symbol == 'MSTR'
                ).count()
                op_time = time.time() - op_start
                db_operations.append(op_time)

            duration = time.time() - start_time

            # Analyze results
            successful_api_calls = len([r for r in api_test_results if 'status_code' in r and r['status_code'] == 200])
            avg_db_time = sum(db_operations) / len(db_operations)

            status = "PASS" if successful_api_calls >= 18 and avg_db_time < 0.5 else "WARNING"

            details = {
                'successful_api_calls': f"{successful_api_calls}/20",
                'average_db_query_time': f"{avg_db_time:.3f}s",
                'max_db_query_time': f"{max(db_operations):.3f}s"
            }

            self.log_test_result("System Stress Test", status, duration, details)
            return status == "PASS"

        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("System Stress Test", "FAIL", duration, {'error': str(e)})
            return False

    def generate_performance_report(self) -> Dict:
        """Generate comprehensive performance report"""
        print("\nGenerating Performance Report...")
        print("=" * 60)

        # Database statistics
        total_records = self.session.query(EnhancedHistoricalData).count()
        total_indicators = self.session.query(IndicatorTemplate).count()
        dna_signals = self.session.query(EnhancedHistoricalData).filter(
            EnhancedHistoricalData.dna_entry_signal == True
        ).count()

        # Performance summary
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t['status'] == 'PASS'])
        failed_tests = len([t for t in self.test_results if t['status'] == 'FAIL'])
        warning_tests = len([t for t in self.test_results if t['status'] == 'WARNING'])

        report = {
            'validation_summary': {
                'timestamp': datetime.now().isoformat(),
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'warnings': warning_tests,
                'success_rate': f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%"
            },
            'system_statistics': {
                'database_records': total_records,
                'indicator_templates': total_indicators,
                'dna_entry_signals': dna_signals,
                'symbols_tested': ['MSTR', 'NVDA'],
                'timeframes_active': len(TimeFrame),
                'api_endpoints': 6
            },
            'detailed_results': self.test_results
        }

        return report

    def run_full_validation(self) -> bool:
        """Run complete validation suite"""
        print("DNA Research System - Performance Validation")
        print("=" * 60)
        print("Running comprehensive validation tests...")
        print()

        all_tests_passed = True

        # Run all validation tests
        tests = [
            self.test_database_connectivity,
            self.test_data_integrity,
            self.test_api_endpoints,
            self.test_query_performance,
            self.test_dna_simulation_accuracy,
            self.test_system_stress
        ]

        for test_func in tests:
            try:
                result = test_func()
                if not result:
                    all_tests_passed = False
            except Exception as e:
                print(f"[FAIL] {test_func.__name__:<40} | FAIL    | Error: {e}")
                all_tests_passed = False

        return all_tests_passed


def main():
    """Run performance validation"""
    validator = PerformanceValidator()

    # Run validation
    success = validator.run_full_validation()

    # Generate report
    report = validator.generate_performance_report()

    # Save report
    with open('performance_validation_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    summary = report['validation_summary']
    stats = report['system_statistics']

    print(f"Tests Executed:     {summary['total_tests']}")
    print(f"Passed:            {summary['passed']} [OK]")
    print(f"Failed:            {summary['failed']} [FAIL]")
    print(f"Warnings:          {summary['warnings']} [WARN]")
    print(f"Success Rate:      {summary['success_rate']}")
    print()
    print(f"Database Records:  {stats['database_records']:,}")
    print(f"DNA Signals:       {stats['dna_entry_signals']}")
    print(f"Timeframes:        {stats['timeframes_active']}")
    print(f"API Status:        {'Online' if summary['failed'] == 0 else 'Issues Detected'}")

    print(f"\nDetailed report saved to: performance_validation_report.json")

    if success:
        print("\n[SUCCESS] All validations passed! System is ready for production use.")
    else:
        print("\n[WARNING] Some validations failed. Please review the detailed report.")

    return success


if __name__ == "__main__":
    main()