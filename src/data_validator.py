"""
Trading Project 004 - Data Validator
Comprehensive validation and quality control for historical market data
"""

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from config_manager import get_config
from logging_setup import get_logger, setup_logging


class ValidationSeverity(Enum):
    """Validation issue severity levels"""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ValidationIssue:
    """Data validation issue"""

    severity: ValidationSeverity
    category: str
    message: str
    bar_index: Optional[int] = None
    value: Optional[Any] = None
    expected: Optional[Any] = None


@dataclass
class ValidationReport:
    """Complete validation report"""

    symbol: str
    total_bars: int
    issues: List[ValidationIssue]
    passed_checks: int
    failed_checks: int
    quality_score: float
    recommendations: List[str]

    def has_errors(self) -> bool:
        """Check if report contains errors or critical issues"""
        return any(
            issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
            for issue in self.issues
        )

    def has_warnings(self) -> bool:
        """Check if report contains warnings"""
        return any(
            issue.severity == ValidationSeverity.WARNING for issue in self.issues
        )


class DataValidator:
    """Comprehensive data validator for market data"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()

        # Get validation settings from config
        self.price_min = self.config.get("data_processing.validation.price_min", 0.01)
        self.price_max = self.config.get(
            "data_processing.validation.price_max", 100000.00
        )
        self.volume_min = self.config.get("data_processing.validation.volume_min", 0)
        self.volume_max = self.config.get(
            "data_processing.validation.volume_max", 1000000000
        )

        self.logger.info("Data Validator initialized")
        self.logger.info(f"Price range: ${self.price_min} - ${self.price_max}")
        self.logger.info(f"Volume range: {self.volume_min} - {self.volume_max}")

    def validate_data(
        self, data: List[Dict[str, Any]], symbol: str
    ) -> ValidationReport:
        """
        Comprehensive validation of historical data

        Args:
            data: List of historical bars
            symbol: Stock symbol

        Returns:
            Validation report with all issues found
        """
        if not data:
            return ValidationReport(
                symbol=symbol,
                total_bars=0,
                issues=[
                    ValidationIssue(
                        ValidationSeverity.CRITICAL,
                        "Data Missing",
                        "No data provided for validation",
                    )
                ],
                passed_checks=0,
                failed_checks=1,
                quality_score=0.0,
                recommendations=["Retry data download"],
            )

        self.logger.info(f"Starting validation for {symbol} - {len(data)} bars")
        issues = []
        total_checks = 0

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(data)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)

        # 1. Basic Data Structure Validation
        issues.extend(self._validate_structure(df))
        total_checks += 5

        # 2. Time Series Validation
        issues.extend(self._validate_timestamps(df))
        total_checks += 4

        # 3. OHLCV Logic Validation
        issues.extend(self._validate_ohlcv_logic(df))
        total_checks += 6

        # 4. Price Range Validation
        issues.extend(self._validate_price_ranges(df))
        total_checks += 3

        # 5. Volume Validation
        issues.extend(self._validate_volume(df))
        total_checks += 3

        # 6. Outlier Detection
        issues.extend(self._detect_price_outliers(df))
        total_checks += 2

        # 7. Missing Data Detection
        issues.extend(self._detect_missing_data(df))
        total_checks += 2

        # 8. Market Hours Validation
        issues.extend(self._validate_market_hours(df))
        total_checks += 1

        # Calculate metrics
        failed_checks = len(
            [
                i
                for i in issues
                if i.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
            ]
        )
        passed_checks = total_checks - len(issues)
        quality_score = (
            max(0.0, (passed_checks / total_checks) * 100) if total_checks > 0 else 0.0
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(issues, df)

        report = ValidationReport(
            symbol=symbol,
            total_bars=len(data),
            issues=issues,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            quality_score=quality_score,
            recommendations=recommendations,
        )

        self.logger.info(f"Validation complete for {symbol}")
        self.logger.info(f"Quality Score: {quality_score:.1f}%")
        self.logger.info(f"Issues found: {len(issues)} ({failed_checks} errors)")

        return report

    def _validate_structure(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate basic data structure"""
        issues = []
        required_columns = ["datetime", "open", "high", "low", "close", "volume"]

        # Check required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.CRITICAL,
                    "Structure",
                    f"Missing required columns: {missing_columns}",
                )
            )

        # Check for null values
        for col in required_columns:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                if null_count > 0:
                    issues.append(
                        ValidationIssue(
                            ValidationSeverity.ERROR,
                            "Data Quality",
                            f"Found {null_count} null values in column '{col}'",
                        )
                    )

        return issues

    def _validate_timestamps(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate timestamp consistency"""
        issues = []

        if "datetime" not in df.columns or len(df) == 0:
            return issues

        # Check for duplicate timestamps
        duplicates = df["datetime"].duplicated().sum()
        if duplicates > 0:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Time Series",
                    f"Found {duplicates} duplicate timestamps",
                )
            )

        # Check time ordering
        if not df["datetime"].is_monotonic_increasing:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Time Series",
                    "Timestamps are not in chronological order",
                )
            )

        # Check for time gaps (for minute data)
        if len(df) > 1:
            time_diffs = df["datetime"].diff().dropna()
            # Expected diff for 1-minute data
            expected_diff = pd.Timedelta(minutes=1)
            large_gaps = time_diffs[
                time_diffs > expected_diff * 5
            ]  # More than 5 minutes

            if len(large_gaps) > 0:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.WARNING,
                        "Time Series",
                        f"Found {len(large_gaps)} large time gaps (>5 minutes)",
                    )
                )

        return issues

    def _validate_ohlcv_logic(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate OHLC price logic"""
        issues = []

        required_cols = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            return issues

        for idx, row in df.iterrows():
            # High should be >= Open, Low, Close
            if not (
                row["high"] >= row["open"]
                and row["high"] >= row["low"]
                and row["high"] >= row["close"]
            ):
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        "OHLC Logic",
                        f"High price logic violated at bar {idx}",
                        bar_index=idx,
                        value=f"H:{row['high']}, O:{row['open']}, L:{row['low']}, C:{row['close']}",
                    )
                )

            # Low should be <= Open, High, Close
            if not (
                row["low"] <= row["open"]
                and row["low"] <= row["high"]
                and row["low"] <= row["close"]
            ):
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        "OHLC Logic",
                        f"Low price logic violated at bar {idx}",
                        bar_index=idx,
                        value=f"H:{row['high']}, O:{row['open']}, L:{row['low']}, C:{row['close']}",
                    )
                )

        return issues

    def _validate_price_ranges(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate price ranges"""
        issues = []
        price_cols = ["open", "high", "low", "close"]

        for col in price_cols:
            if col not in df.columns:
                continue

            # Check for prices below minimum
            below_min = df[df[col] < self.price_min]
            if len(below_min) > 0:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.ERROR,
                        "Price Range",
                        f"Found {len(below_min)} {col} prices below minimum ${self.price_min}",
                    )
                )

            # Check for prices above maximum
            above_max = df[df[col] > self.price_max]
            if len(above_max) > 0:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.WARNING,
                        "Price Range",
                        f"Found {len(above_max)} {col} prices above ${self.price_max}",
                    )
                )

        return issues

    def _validate_volume(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate volume data"""
        issues = []

        if "volume" not in df.columns:
            return issues

        # Check for negative volumes
        negative_vol = df[df["volume"] < 0]
        if len(negative_vol) > 0:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Volume",
                    f"Found {len(negative_vol)} bars with negative volume",
                )
            )

        # Check for zero volumes (warning only)
        zero_vol = df[df["volume"] == 0]
        if len(zero_vol) > 0:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    "Volume",
                    f"Found {len(zero_vol)} bars with zero volume",
                )
            )

        # Check for extremely high volumes
        high_vol = df[df["volume"] > self.volume_max]
        if len(high_vol) > 0:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.WARNING,
                    "Volume",
                    f"Found {len(high_vol)} bars with unusually high volume",
                )
            )

        return issues

    def _detect_price_outliers(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Detect price outliers and sudden jumps"""
        issues = []

        if "close" not in df.columns or len(df) < 2:
            return issues

        # Calculate price changes
        df["price_change_pct"] = df["close"].pct_change() * 100

        # Detect large price jumps (>20% in one bar for stocks)
        large_jumps = df[abs(df["price_change_pct"]) > 20]
        if len(large_jumps) > 0:
            for idx, row in large_jumps.iterrows():
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.WARNING,
                        "Price Outlier",
                        f"Large price jump detected: {row['price_change_pct']:.1f}% at bar {idx}",
                        bar_index=idx,
                        value=f"{row['price_change_pct']:.1f}%",
                    )
                )

        # Statistical outlier detection using IQR method
        if len(df) > 10:
            Q1 = df["close"].quantile(0.25)
            Q3 = df["close"].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            outliers = df[(df["close"] < lower_bound) | (df["close"] > upper_bound)]
            if len(outliers) > 0:
                issues.append(
                    ValidationIssue(
                        ValidationSeverity.INFO,
                        "Statistical Outlier",
                        f"Found {len(outliers)} statistical price outliers using IQR method",
                    )
                )

        return issues

    def _detect_missing_data(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Detect missing data gaps"""
        issues = []

        if "datetime" not in df.columns or len(df) < 2:
            return issues

        # For minute data, check for missing minutes during market hours
        time_diffs = df["datetime"].diff().dropna()
        expected_diff = pd.Timedelta(minutes=1)

        # Count gaps longer than expected
        gaps = time_diffs[time_diffs > expected_diff]
        if len(gaps) > 0:
            total_missing_minutes = (gaps - expected_diff).sum().total_seconds() / 60
            issues.append(
                ValidationIssue(
                    ValidationSeverity.INFO,
                    "Missing Data",
                    f"Estimated {total_missing_minutes:.0f} missing minutes in dataset",
                )
            )

        return issues

    def _validate_market_hours(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate data falls within market hours"""
        issues = []

        if "datetime" not in df.columns or len(df) == 0:
            return issues

        # Check for data outside typical market hours (9:30-16:00 ET)
        # Note: This is a simplified check - real implementation should consider holidays, etc.
        df["hour"] = df["datetime"].dt.hour
        df["minute"] = df["datetime"].dt.minute

        # Market opens at 9:30 (14:30 UTC) and closes at 16:00 (21:00 UTC) - approximate
        outside_hours = df[
            (df["hour"] < 9)
            | (df["hour"] > 16)
            | ((df["hour"] == 9) & (df["minute"] < 30))
        ]

        if len(outside_hours) > 0:
            issues.append(
                ValidationIssue(
                    ValidationSeverity.INFO,
                    "Market Hours",
                    f"Found {len(outside_hours)} bars outside typical market hours",
                )
            )

        return issues

    def _generate_recommendations(
        self, issues: List[ValidationIssue], df: pd.DataFrame
    ) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []

        # Count issues by category
        error_count = len([i for i in issues if i.severity == ValidationSeverity.ERROR])
        warning_count = len(
            [i for i in issues if i.severity == ValidationSeverity.WARNING]
        )

        if error_count > 0:
            recommendations.append(
                "Critical data quality issues detected - review before using for analysis"
            )

        if warning_count > 0:
            recommendations.append(
                "Data quality warnings present - consider data cleaning"
            )

        # Specific recommendations
        if any("OHLC Logic" in issue.category for issue in issues):
            recommendations.append("Fix OHLC logic errors - data may be corrupted")

        if any("Time Series" in issue.category for issue in issues):
            recommendations.append(
                "Review timestamp issues - may affect time-based analysis"
            )

        if any("Price Outlier" in issue.category for issue in issues):
            recommendations.append("Consider outlier removal or investigation")

        if any("Missing Data" in issue.category for issue in issues):
            recommendations.append("Consider data interpolation for missing values")

        if len(issues) == 0:
            recommendations.append("Data quality is excellent - ready for analysis")

        return recommendations

    def print_report(self, report: ValidationReport) -> None:
        """Print formatted validation report"""
        print("=" * 80)
        print(f"DATA VALIDATION REPORT - {report.symbol}")
        print("=" * 80)
        print(f"Total Bars: {report.total_bars}")
        print(f"Quality Score: {report.quality_score:.1f}%")
        print(f"Passed Checks: {report.passed_checks}")
        print(f"Failed Checks: {report.failed_checks}")
        print()

        if report.issues:
            print("ISSUES DETECTED:")
            print("-" * 40)
            for issue in report.issues:
                severity_icon = {
                    "INFO": "[i]",
                    "WARNING": "[!]",
                    "ERROR": "[X]",
                    "CRITICAL": "[!!]",
                }
                print(
                    f"{severity_icon.get(issue.severity.value, '•')} [{issue.severity.value}] {issue.category}: {issue.message}"
                )
                if issue.bar_index is not None:
                    print(f"   Bar: {issue.bar_index}, Value: {issue.value}")
            print()

        if report.recommendations:
            print("RECOMMENDATIONS:")
            print("-" * 40)
            for rec in report.recommendations:
                print(f"  {rec}")

        print("=" * 80)


def main():
    """Demo function for data validator"""
    setup_logging()
    logger = get_logger(__name__)

    # Test with sample data (you can replace this with actual data)
    sample_data = [
        {
            "symbol": "TEST",
            "datetime": "2025-09-13 16:30:00",
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 1000,
        },
        {
            "symbol": "TEST",
            "datetime": "2025-09-13 16:31:00",
            "open": 101.0,
            "high": 101.0,  # This will create an OHLC logic error
            "low": 102.0,  # Low > High - error!
            "close": 101.5,
            "volume": 1500,
        },
    ]

    validator = DataValidator()
    report = validator.validate_data(sample_data, "TEST")
    validator.print_report(report)


if __name__ == "__main__":
    main()
