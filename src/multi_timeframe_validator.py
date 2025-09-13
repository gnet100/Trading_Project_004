"""
Trading Project 004 - Multi-Timeframe Data Validator
Enterprise validation system for 1min, 15min, 1hour, 4hour, daily data
Target: 99.95%+ data integrity for 2-year historical database
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytz

sys.path.insert(0, str(Path(__file__).parent))
from data_validator import ValidationIssue, ValidationReport, ValidationSeverity
from logging_setup import get_logger


class TimeFrame(Enum):
    """Supported timeframes"""

    MIN_1 = "1min"
    MIN_15 = "15min"
    HOUR_1 = "1hour"
    HOUR_4 = "4hour"
    DAILY = "daily"


class TradingSession(Enum):
    """Trading session types"""

    PRE_MARKET = "pre_market"  # 04:00-09:30
    REGULAR = "regular"  # 09:30-16:00
    AFTER_HOURS = "after_hours"  # 16:00-20:00
    CLOSED = "closed"  # 20:00-04:00, weekends


@dataclass
class TimeframeData:
    """Data structure for each timeframe"""

    timeframe: TimeFrame
    data: pd.DataFrame
    validation_report: Optional[ValidationReport] = None
    quality_score: float = 0.0
    records_count: int = 0


class MultiTimeframeValidator:
    """
    Enterprise multi-timeframe validation system
    Validates 1min, 15min, 1hour, 4hour, daily data with cross-timeframe consistency
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.est_tz = pytz.timezone("US/Eastern")

        # Trading session times (EST)
        self.session_times = {
            TradingSession.PRE_MARKET: (dt_time(4, 0), dt_time(9, 30)),
            TradingSession.REGULAR: (dt_time(9, 30), dt_time(16, 0)),
            TradingSession.AFTER_HOURS: (dt_time(16, 0), dt_time(20, 0)),
        }

        # Price movement tolerances by session
        self.movement_tolerances = {
            TradingSession.REGULAR: 0.20,  # 20% max in regular hours
            TradingSession.PRE_MARKET: 0.30,  # 30% max in pre-market
            TradingSession.AFTER_HOURS: 0.30,  # 30% max in after hours
            TradingSession.CLOSED: 1.0,  # No limit during closed hours (gaps)
        }

        self.min_quality_threshold = 99.95
        self.logger.info("Multi-Timeframe Validator initialized")

    def validate_timeframe_data(
        self, data: List[Dict[str, Any]], timeframe: TimeFrame, symbol: str
    ) -> TimeframeData:
        """
        Validate data for specific timeframe

        Args:
            data: Raw OHLCV data
            timeframe: Target timeframe
            symbol: Stock symbol

        Returns:
            TimeframeData with validation results
        """
        self.logger.info(f"Validating {timeframe.value} data for {symbol}")

        # Convert to DataFrame
        df = pd.DataFrame(data)
        if df.empty:
            self.logger.error(f"No data provided for {timeframe.value}")
            return TimeframeData(timeframe=timeframe, data=df, records_count=0)

        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)

        # Initialize validation report
        validation_report = ValidationReport(
            symbol=symbol,
            total_bars=len(df),
            issues=[],
            passed_checks=0,
            failed_checks=0,
            quality_score=0.0,
            recommendations=[],
        )

        # Run validation checks
        issues = []

        # Check 1: Basic OHLC Logic
        issues.extend(self._validate_ohlc_logic(df, symbol))

        # Check 2: Time Series Validation
        issues.extend(self._validate_time_series(df, timeframe, symbol))

        # Check 3: Price Movement Reasonability
        issues.extend(self._validate_price_movements(df, timeframe, symbol))

        # Check 4: Volume Correlation
        issues.extend(self._validate_volume_correlation(df, symbol))

        # Calculate quality score
        quality_score = self._calculate_quality_score(len(df), issues)

        # Update validation report
        validation_report.issues = issues
        validation_report.quality_score = quality_score

        timeframe_data = TimeframeData(
            timeframe=timeframe,
            data=df,
            validation_report=validation_report,
            quality_score=quality_score,
            records_count=len(df),
        )

        self.logger.info(
            f"{timeframe.value} validation complete: {quality_score:.2f}% "
            f"({len(issues)} issues)"
        )

        return timeframe_data

    def _validate_ohlc_logic(
        self, df: pd.DataFrame, symbol: str
    ) -> List[ValidationIssue]:
        """Basic OHLC logic validation"""
        issues = []

        # Check: Low <= Open <= High
        invalid_open = (df["open"] < df["low"]) | (df["open"] > df["high"])
        if invalid_open.any():
            invalid_indices = df[invalid_open].index.tolist()
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="OHLC_LOGIC",
                    message=f"Open price outside Low-High range in {len(invalid_indices)} records",
                    bar_index=invalid_indices[0] if invalid_indices else None,
                )
            )

        # Check: Low <= Close <= High
        invalid_close = (df["close"] < df["low"]) | (df["close"] > df["high"])
        if invalid_close.any():
            invalid_indices = df[invalid_close].index.tolist()
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="OHLC_LOGIC",
                    message=f"Close price outside Low-High range in {len(invalid_indices)} records",
                    bar_index=invalid_indices[0] if invalid_indices else None,
                )
            )

        # Check: Positive prices
        negative_prices = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
        if negative_prices.any():
            invalid_indices = df[negative_prices].index.tolist()
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.CRITICAL,
                    category="OHLC_LOGIC",
                    message=f"Non-positive prices in {len(invalid_indices)} records",
                    bar_index=invalid_indices[0] if invalid_indices else None,
                )
            )

        # Check: Negative volume
        negative_volume = df["volume"] < 0
        if negative_volume.any():
            invalid_indices = df[negative_volume].index.tolist()
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="OHLC_LOGIC",
                    message=f"Negative volume in {len(invalid_indices)} records",
                    bar_index=invalid_indices[0] if invalid_indices else None,
                )
            )

        return issues

    def _validate_time_series(
        self, df: pd.DataFrame, timeframe: TimeFrame, symbol: str
    ) -> List[ValidationIssue]:
        """Time series continuity validation"""
        issues = []

        if len(df) < 2:
            return issues

        # Expected time delta based on timeframe
        expected_deltas = {
            TimeFrame.MIN_1: timedelta(minutes=1),
            TimeFrame.MIN_15: timedelta(minutes=15),
            TimeFrame.HOUR_1: timedelta(hours=1),
            TimeFrame.HOUR_4: timedelta(hours=4),
            TimeFrame.DAILY: timedelta(days=1),
        }

        expected_delta = expected_deltas[timeframe]

        # Check for duplicates
        duplicates = df["datetime"].duplicated()
        if duplicates.any():
            duplicate_indices = df[duplicates].index.tolist()
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="TIME_SERIES",
                    message=f"Duplicate timestamps in {len(duplicate_indices)} records",
                    bar_index=duplicate_indices[0] if duplicate_indices else None,
                )
            )

        # Check time sequence
        time_diffs = df["datetime"].diff().dropna()

        # For intraday timeframes, allow for trading session gaps
        if timeframe in [TimeFrame.MIN_1, TimeFrame.MIN_15, TimeFrame.HOUR_1]:
            # Allow overnight gaps (up to 18 hours)
            max_allowed_gap = timedelta(hours=18)
            unusual_gaps = time_diffs[time_diffs > max_allowed_gap]

            if len(unusual_gaps) > 0:
                gap_indices = unusual_gaps.index.tolist()
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="TIME_SERIES",
                        message=f"Unusual time gaps (>18h) in {len(gap_indices)} locations",
                        bar_index=gap_indices[0] if gap_indices else None,
                    )
                )

        return issues

    def _validate_price_movements(
        self, df: pd.DataFrame, timeframe: TimeFrame, symbol: str
    ) -> List[ValidationIssue]:
        """Price movement reasonability with trading session awareness"""
        issues = []

        if len(df) < 2:
            return issues

        # Calculate price changes
        df["prev_close"] = df["close"].shift(1)
        df["price_change_pct"] = abs(
            (df["close"] - df["prev_close"]) / df["prev_close"]
        )

        # Determine trading session for each record
        df["session"] = df["datetime"].apply(self._get_trading_session)

        # Check price movements by session
        for session in TradingSession:
            session_data = df[df["session"] == session]
            if session_data.empty:
                continue

            tolerance = self.movement_tolerances[session]

            if session == TradingSession.CLOSED:
                continue  # Skip validation during closed hours

            excessive_moves = session_data[session_data["price_change_pct"] > tolerance]

            if len(excessive_moves) > 0:
                severity = (
                    ValidationSeverity.WARNING
                    if len(excessive_moves) < 5
                    else ValidationSeverity.ERROR
                )
                issues.append(
                    ValidationIssue(
                        severity=severity,
                        category="PRICE_MOVEMENT",
                        message=f"Excessive price movements (>{tolerance*100}%) in {session.value}: "
                        f"{len(excessive_moves)} occurrences",
                        bar_index=excessive_moves.index.tolist()[0]
                        if len(excessive_moves) > 0
                        else None,
                    )
                )

        return issues

    def _validate_volume_correlation(
        self, df: pd.DataFrame, symbol: str
    ) -> List[ValidationIssue]:
        """Volume correlation validation"""
        issues = []

        # Check for zero volume with price changes
        df["price_changed"] = df["open"] != df["close"]
        zero_volume_with_change = df[(df["volume"] == 0) & df["price_changed"]]

        if len(zero_volume_with_change) > 0:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="VOLUME_CORRELATION",
                    message=f"Zero volume with price changes in {len(zero_volume_with_change)} records",
                    bar_index=zero_volume_with_change.index.tolist()[0]
                    if len(zero_volume_with_change) > 0
                    else None,
                )
            )

        return issues

    def _get_trading_session(self, timestamp: pd.Timestamp) -> TradingSession:
        """Determine trading session for given timestamp"""
        # Convert to EST
        if timestamp.tz is None:
            est_time = self.est_tz.localize(timestamp)
        else:
            est_time = timestamp.astimezone(self.est_tz)

        # Check if weekend
        if est_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return TradingSession.CLOSED

        time_only = est_time.time()

        # Check each session
        if (
            self.session_times[TradingSession.PRE_MARKET][0]
            <= time_only
            < self.session_times[TradingSession.PRE_MARKET][1]
        ):
            return TradingSession.PRE_MARKET
        elif (
            self.session_times[TradingSession.REGULAR][0]
            <= time_only
            < self.session_times[TradingSession.REGULAR][1]
        ):
            return TradingSession.REGULAR
        elif (
            self.session_times[TradingSession.AFTER_HOURS][0]
            <= time_only
            < self.session_times[TradingSession.AFTER_HOURS][1]
        ):
            return TradingSession.AFTER_HOURS
        else:
            return TradingSession.CLOSED

    def _calculate_quality_score(
        self, total_records: int, issues: List[ValidationIssue]
    ) -> float:
        """Calculate quality score based on issues"""
        if total_records == 0:
            return 0.0

        penalty_weights = {
            ValidationSeverity.CRITICAL: 50,
            ValidationSeverity.ERROR: 10,
            ValidationSeverity.WARNING: 2,
        }

        total_penalty = 0
        for issue in issues:
            # Assume each issue affects 1 record if bar_index is set
            records_affected = 1 if issue.bar_index is not None else 0
            penalty = penalty_weights[issue.severity] * (
                records_affected / total_records
            )
            total_penalty += penalty

        # Cap penalty at 100 to avoid negative scores
        total_penalty = min(total_penalty, 100)
        quality_score = max(0, 100 - total_penalty)

        return quality_score

    def validate_cross_timeframe_consistency(
        self, timeframe_data_dict: Dict[TimeFrame, TimeframeData]
    ) -> List[ValidationIssue]:
        """
        Validate consistency across different timeframes
        Check that aggregated data matches between timeframes
        """
        self.logger.info("Starting cross-timeframe validation")
        issues = []

        # Define aggregation relationships
        aggregation_pairs = [
            (TimeFrame.MIN_1, TimeFrame.MIN_15),
            (TimeFrame.MIN_15, TimeFrame.HOUR_1),
            (TimeFrame.HOUR_1, TimeFrame.HOUR_4),
            (TimeFrame.HOUR_4, TimeFrame.DAILY),
        ]

        for source_tf, target_tf in aggregation_pairs:
            if (
                source_tf not in timeframe_data_dict
                or target_tf not in timeframe_data_dict
            ):
                continue

            source_data = timeframe_data_dict[source_tf]
            target_data = timeframe_data_dict[target_tf]

            if source_data.data.empty or target_data.data.empty:
                continue

            # TODO: Implement aggregation consistency check
            # This would involve:
            # 1. Group source data by target timeframe periods
            # 2. Calculate OHLCV for each period
            # 3. Compare with target timeframe data
            # 4. Identify discrepancies

            self.logger.info(
                f"Cross-validation: {source_tf.value} -> {target_tf.value} (placeholder)"
            )

        return issues

    def get_validation_summary(
        self, timeframe_data_dict: Dict[TimeFrame, TimeframeData]
    ) -> Dict[str, Any]:
        """Get comprehensive validation summary"""
        summary = {
            "validation_timestamp": datetime.now().isoformat(),
            "target_quality_threshold": f"{self.min_quality_threshold}%",
            "timeframes": {},
        }

        total_records = 0
        total_issues = 0
        min_quality = 100.0

        for timeframe, data in timeframe_data_dict.items():
            tf_summary = {
                "records_count": data.records_count,
                "quality_score": f"{data.quality_score:.2f}%",
                "issues_count": len(data.validation_report.issues)
                if data.validation_report
                else 0,
                "passes_threshold": data.quality_score >= self.min_quality_threshold,
            }

            summary["timeframes"][timeframe.value] = tf_summary
            total_records += data.records_count
            total_issues += tf_summary["issues_count"]
            min_quality = min(min_quality, data.quality_score)

        summary["overall"] = {
            "total_records": total_records,
            "total_issues": total_issues,
            "minimum_quality_score": f"{min_quality:.2f}%",
            "all_pass_threshold": min_quality >= self.min_quality_threshold,
        }

        return summary


def main():
    """Demo of multi-timeframe validation"""
    print("=" * 80)
    print("Multi-Timeframe Data Validator - Demo")
    print("Target: 99.95%+ Data Integrity Across All Timeframes")
    print("=" * 80)

    validator = MultiTimeframeValidator()

    # Sample data for demonstration
    base_time = datetime(2024, 1, 15, 9, 30)  # Monday 9:30 AM
    sample_data = []

    for i in range(10):
        sample_data.append(
            {
                "symbol": "MSTR",
                "datetime": base_time + timedelta(minutes=i),
                "open": 150.0 + i * 0.1,
                "high": 151.0 + i * 0.1,
                "low": 149.5 + i * 0.1,
                "close": 150.5 + i * 0.1,
                "volume": 1000 + i * 100,
            }
        )

    # Test validation for 1-minute data
    result = validator.validate_timeframe_data(sample_data, TimeFrame.MIN_1, "MSTR")

    print(f"\n1-Minute Data Validation:")
    print(f"Records: {result.records_count}")
    print(f"Quality Score: {result.quality_score:.2f}%")
    print(
        f"Issues: {len(result.validation_report.issues) if result.validation_report else 0}"
    )

    if result.validation_report and result.validation_report.issues:
        for issue in result.validation_report.issues:
            print(f"  [{issue.severity.value}] {issue.category}: {issue.message}")

    print("=" * 80)


if __name__ == "__main__":
    main()
