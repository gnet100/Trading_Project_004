#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Storage Service - Trading Project 004
High-level service for managing historical data storage and retrieval

Features:
- Bulk insert operations for IB data integration
- Advanced querying with filtering and date ranges
- Data quality validation and scoring
- Missing minutes detection and reporting
- Trading hours classification
- Performance optimization for large datasets
"""

import os
import sys
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union, Any

# Add src to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_manager import DatabaseManager
from database_models import HistoricalData


class DataStorageService:
    """
    High-level service for data storage operations

    Provides abstracted interface for:
    - Bulk data operations
    - Quality validation before storage
    - Advanced querying and filtering
    - Trading hours classification
    - Data integrity monitoring
    """

    def __init__(self, database_url: str = None):
        """
        Initialize Data Storage Service

        Args:
            database_url: Database connection string (optional)
        """
        self.db_manager = DatabaseManager(database_url)

        # Trading hours configuration (US Eastern Time)
        self.trading_hours = {
            'pre_market_start': '04:00:00',
            'regular_start': '09:30:00',
            'regular_end': '16:00:00',
            'after_hours_end': '20:00:00'
        }

        # Data quality thresholds
        self.quality_thresholds = {
            'excellent': 99.95,
            'good': 95.0,
            'acceptable': 90.0,
            'poor': 80.0
        }

    def bulk_insert_ib_data(
        self,
        data_records: List[Dict[str, Any]],
        validate_quality: bool = True,
        min_quality_score: float = 95.0
    ) -> Dict[str, Any]:
        """
        Insert bulk IB historical data with validation

        Args:
            data_records: List of dictionaries containing OHLCV data
            validate_quality: Whether to validate data quality before insert
            min_quality_score: Minimum quality score to accept (0-100)

        Returns:
            Dictionary with insert results and statistics
        """
        results = {
            'total_records': len(data_records),
            'inserted': 0,
            'rejected': 0,
            'validation_errors': [],
            'quality_stats': {}
        }

        if not data_records:
            results['status'] = 'no_data'
            return results

        # Prepare records for database insertion
        validated_records = []

        for i, record in enumerate(data_records):
            try:
                # Convert and validate record format
                db_record = self._prepare_record_for_storage(record)

                # Validate data quality if requested
                if validate_quality:
                    quality_score = self._calculate_quality_score(db_record)
                    db_record['data_quality_score'] = quality_score

                    if quality_score < min_quality_score:
                        results['rejected'] += 1
                        results['validation_errors'].append({
                            'record_index': i,
                            'reason': f'Quality score {quality_score:.2f} below threshold {min_quality_score}',
                            'symbol': record.get('symbol'),
                            'timestamp': record.get('timestamp')
                        })
                        continue

                # Classify trading hours
                db_record['trading_hours'] = self._classify_trading_hours(
                    db_record['timestamp']
                )

                validated_records.append(db_record)

            except Exception as e:
                results['rejected'] += 1
                results['validation_errors'].append({
                    'record_index': i,
                    'reason': str(e),
                    'symbol': record.get('symbol'),
                    'timestamp': record.get('timestamp')
                })

        # Bulk insert validated records
        if validated_records:
            try:
                insert_result = self.db_manager.bulk_insert_historical_data(validated_records)
                results['inserted'] = insert_result.get('inserted_count', 0)
                results['status'] = 'success'

                # Calculate quality statistics
                if validate_quality:
                    quality_scores = [r.get('data_quality_score', 0) for r in validated_records]
                    results['quality_stats'] = {
                        'avg_quality': sum(quality_scores) / len(quality_scores),
                        'min_quality': min(quality_scores),
                        'max_quality': max(quality_scores),
                        'excellent_count': sum(1 for q in quality_scores if q >= self.quality_thresholds['excellent']),
                        'good_count': sum(1 for q in quality_scores if q >= self.quality_thresholds['good'])
                    }

            except Exception as e:
                results['status'] = 'database_error'
                results['error'] = str(e)
        else:
            results['status'] = 'no_valid_records'

        return results

    def query_historical_data(
        self,
        symbol: str = None,
        start_date: Union[str, date, datetime] = None,
        end_date: Union[str, date, datetime] = None,
        timeframe: str = None,
        trading_hours_only: bool = False,
        min_quality_score: float = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """
        Query historical data with advanced filtering

        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'MSTR')
            start_date: Start date for query range
            end_date: End date for query range
            timeframe: Specific timeframe ('1min', '15min', etc.)
            trading_hours_only: Only return regular trading hours data
            min_quality_score: Minimum data quality score
            limit: Maximum number of records to return

        Returns:
            List of historical data records as dictionaries
        """
        query_params = {}

        if symbol:
            query_params['symbol'] = symbol
        if start_date:
            query_params['start_date'] = self._parse_date(start_date)
        if end_date:
            query_params['end_date'] = self._parse_date(end_date)
        if timeframe:
            query_params['timeframe'] = timeframe
        if trading_hours_only:
            query_params['trading_hours_only'] = True
        if min_quality_score:
            query_params['min_quality_score'] = min_quality_score
        if limit:
            query_params['limit'] = limit

        return self.db_manager.get_historical_data(**query_params)

    def detect_missing_minutes(
        self,
        symbol: str,
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime],
        timeframe: str = '1min'
    ) -> Dict[str, Any]:
        """
        Detect missing minutes in historical data

        Args:
            symbol: Stock symbol to check
            start_date: Start date for analysis
            end_date: End date for analysis
            timeframe: Timeframe to analyze (default: '1min')

        Returns:
            Dictionary with missing minutes analysis
        """
        # Get existing data for the period
        existing_data = self.query_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            trading_hours_only=True
        )

        if not existing_data:
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'total_expected': 0,
                'total_found': 0,
                'missing_count': 0,
                'missing_periods': [],
                'completeness_percentage': 0.0
            }

        # Generate expected timestamps for trading hours
        expected_timestamps = self._generate_trading_timestamps(
            self._parse_date(start_date),
            self._parse_date(end_date),
            timeframe
        )

        # Find missing timestamps
        existing_timestamps = {
            self._parse_date(record['timestamp']) for record in existing_data
        }

        missing_timestamps = expected_timestamps - existing_timestamps

        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'period_start': start_date,
            'period_end': end_date,
            'total_expected': len(expected_timestamps),
            'total_found': len(existing_timestamps),
            'missing_count': len(missing_timestamps),
            'missing_periods': sorted(list(missing_timestamps)),
            'completeness_percentage': (len(existing_timestamps) / len(expected_timestamps)) * 100 if expected_timestamps else 100.0
        }

    def get_data_quality_report(
        self,
        symbol: str = None,
        start_date: Union[str, date, datetime] = None,
        end_date: Union[str, date, datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive data quality report

        Args:
            symbol: Stock symbol (optional, for all symbols if None)
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            Dictionary with quality statistics and analysis
        """
        data = self.query_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )

        if not data:
            return {'status': 'no_data', 'records_analyzed': 0}

        quality_scores = [record.get('data_quality_score', 0) for record in data]

        return {
            'status': 'success',
            'records_analyzed': len(data),
            'quality_distribution': {
                'excellent': sum(1 for q in quality_scores if q >= self.quality_thresholds['excellent']),
                'good': sum(1 for q in quality_scores if self.quality_thresholds['good'] <= q < self.quality_thresholds['excellent']),
                'acceptable': sum(1 for q in quality_scores if self.quality_thresholds['acceptable'] <= q < self.quality_thresholds['good']),
                'poor': sum(1 for q in quality_scores if q < self.quality_thresholds['acceptable'])
            },
            'quality_stats': {
                'average': sum(quality_scores) / len(quality_scores),
                'minimum': min(quality_scores),
                'maximum': max(quality_scores),
                'median': sorted(quality_scores)[len(quality_scores) // 2]
            },
            'period_analyzed': {
                'start_date': min(record['timestamp'] for record in data),
                'end_date': max(record['timestamp'] for record in data)
            }
        }

    # Helper methods

    def _prepare_record_for_storage(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert IB data record to database format"""
        required_fields = ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume']

        for field in required_fields:
            if field not in record:
                raise ValueError(f"Missing required field: {field}")

        return {
            'symbol': str(record['symbol']).upper(),
            'timestamp': self._parse_date(record['timestamp']),
            'timeframe': record.get('timeframe', '1min'),
            'open': Decimal(str(record['open'])),
            'high': Decimal(str(record['high'])),
            'low': Decimal(str(record['low'])),
            'close': Decimal(str(record['close'])),
            'volume': int(record['volume']),
            'data_source': record.get('data_source', 'IB'),
            'data_quality_score': record.get('data_quality_score', 0.0)
        }

    def _calculate_quality_score(self, record: Dict[str, Any]) -> float:
        """Calculate data quality score for a record"""
        score = 100.0

        # OHLC validation
        open_price = float(record['open'])
        high_price = float(record['high'])
        low_price = float(record['low'])
        close_price = float(record['close'])

        if high_price < max(open_price, close_price):
            score -= 20.0  # High should be >= max(open, close)
        if low_price > min(open_price, close_price):
            score -= 20.0  # Low should be <= min(open, close)

        # Volume validation
        volume = record['volume']
        if volume < 0:
            score -= 15.0
        if volume == 0:
            score -= 5.0  # Zero volume possible but suspicious

        # Price reasonableness (basic sanity check)
        prices = [open_price, high_price, low_price, close_price]
        if any(p <= 0 for p in prices):
            score -= 30.0  # Negative or zero prices are invalid

        return max(0.0, score)

    def _classify_trading_hours(self, timestamp: datetime) -> str:
        """Classify timestamp into trading session"""
        time_str = timestamp.strftime('%H:%M:%S')

        if time_str < self.trading_hours['regular_start']:
            if time_str >= self.trading_hours['pre_market_start']:
                return 'pre_market'
            else:
                return 'closed'
        elif time_str < self.trading_hours['regular_end']:
            return 'regular'
        elif time_str < self.trading_hours['after_hours_end']:
            return 'after_hours'
        else:
            return 'closed'

    def _parse_date(self, date_input: Union[str, date, datetime]) -> datetime:
        """Parse various date formats to datetime"""
        if isinstance(date_input, datetime):
            return date_input
        elif isinstance(date_input, date):
            return datetime.combine(date_input, datetime.min.time())
        elif isinstance(date_input, str):
            # Try common date formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    return datetime.strptime(date_input, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unable to parse date: {date_input}")
        else:
            raise ValueError(f"Unsupported date type: {type(date_input)}")

    def _generate_trading_timestamps(
        self,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> set:
        """Generate expected trading timestamps for a period"""
        timestamps = set()

        # For simplicity, generate 1-minute intervals during regular trading hours
        # This would need to be enhanced for other timeframes
        if timeframe != '1min':
            return timestamps  # Simplified for now

        current_date = start_date.date()
        end_date_only = end_date.date()

        while current_date <= end_date_only:
            # Skip weekends (basic implementation)
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                # Generate timestamps for regular trading hours
                start_time = datetime.combine(current_date, datetime.strptime('09:30:00', '%H:%M:%S').time())
                end_time = datetime.combine(current_date, datetime.strptime('16:00:00', '%H:%M:%S').time())

                current_time = start_time
                while current_time < end_time:
                    timestamps.add(current_time)
                    current_time += timedelta(minutes=1)

            current_date += timedelta(days=1)

        return timestamps


# Example usage and testing
if __name__ == "__main__":
    # Initialize service
    storage_service = DataStorageService()

    print("Data Storage Service initialized successfully!")
    print(f"Quality thresholds: {storage_service.quality_thresholds}")
    print(f"Trading hours config: {storage_service.trading_hours}")