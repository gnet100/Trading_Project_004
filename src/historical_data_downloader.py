"""
Trading Project 004 - Historical Data Downloader
Downloads historical market data from Interactive Brokers and saves to local storage
"""

import asyncio
import csv
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from config_manager import get_config
from data_validator import DataValidator, ValidationReport
from enterprise_data_validator import DataDNA, EnterpriseDataValidator
from ib_connector import HistoricalBar, IBConnector
from logging_setup import get_logger, setup_logging
from multi_timeframe_validator import MultiTimeframeValidator, TimeFrame, TimeframeData
from rate_limiter import IBRateLimiter, Priority, RequestType


class HistoricalDataDownloader:
    """Downloads and manages historical market data from IB"""

    def __init__(
        self,
        enable_validation: bool = True,
        multi_timeframe_validation: bool = True,
        enable_rate_limiting: bool = True,
    ):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self.ib_connector = None
        self.data_path = Path(self.config.get("paths.data.raw", "data/raw/"))
        self.processed_path = Path(
            self.config.get("paths.data.processed", "data/processed/")
        )

        # Create directories if they don't exist
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)

        # Initialize rate limiter
        self.enable_rate_limiting = enable_rate_limiting
        if self.enable_rate_limiting:
            self.rate_limiter = IBRateLimiter()
            self.rate_limiter.start_processing()
            self.logger.info("Rate limiting enabled - optimized for IB API limits")
        else:
            self.rate_limiter = None
            self.logger.warning("Rate limiting disabled - may hit IB API limits")

        # Initialize data validators
        self.enable_validation = enable_validation
        self.multi_timeframe_validation = multi_timeframe_validation

        if self.multi_timeframe_validation:
            self.multi_tf_validator = MultiTimeframeValidator()
            self.validator = None  # Multi-timeframe validator includes all validation
            self.logger.info("Multi-timeframe validation enabled (99.95%+ target)")
            self.logger.info("Supported timeframes: 1min, 15min, 1hour, 4hour, daily")
        elif self.enable_validation:
            self.validator = DataValidator()
            self.multi_tf_validator = None
            self.logger.info("Standard data validation enabled")
        else:
            self.validator = None
            self.multi_tf_validator = None
            self.logger.warning("Data validation disabled")

        # Supported timeframes mapping
        self.timeframes = {
            "1 min": TimeFrame.MIN_1,
            "15 mins": TimeFrame.MIN_15,
            "1 hour": TimeFrame.HOUR_1,
            "4 hours": TimeFrame.HOUR_4,
            "1 day": TimeFrame.DAILY,
        }

        self.logger.info(f"Historical Data Downloader initialized")
        self.logger.info(f"Raw data path: {self.data_path}")
        self.logger.info(f"Processed data path: {self.processed_path}")

    def connect_to_ib(self) -> bool:
        """Connect to Interactive Brokers"""
        try:
            self.ib_connector = IBConnector()
            if self.ib_connector.connect_to_ib():
                self.logger.info("Connected to IB successfully")
                return True
            else:
                self.logger.error("Failed to connect to IB")
                return False
        except Exception as e:
            self.logger.error(f"Error connecting to IB: {e}")
            return False

    def disconnect_from_ib(self):
        """Disconnect from Interactive Brokers"""
        if self.ib_connector:
            self.ib_connector.disconnect_from_ib()
            self.logger.info("Disconnected from IB")

        # Stop rate limiter processing
        if self.enable_rate_limiting and self.rate_limiter:
            self.rate_limiter.stop_processing()
            self.logger.info("Stopped rate limiter processing")

    def _rate_limited_historical_request(
        self,
        symbol: str,
        duration: str,
        bar_size: str,
        exchange: str,
        priority: Priority = Priority.NORMAL,
    ):
        """
        Rate-limited wrapper for historical data requests

        Args:
            symbol: Stock symbol
            duration: Duration string
            bar_size: Bar size string
            exchange: Exchange
            priority: Request priority

        Returns:
            Request ID from IB connector
        """

        def make_request():
            return self.ib_connector.request_historical_data(
                symbol=symbol, duration=duration, bar_size=bar_size, exchange=exchange
            )

        if self.enable_rate_limiting and self.rate_limiter:
            # Add to rate-limited queue
            request_id = self.rate_limiter.add_request(
                make_request, RequestType.HISTORICAL_DATA, priority
            )
            self.logger.info(
                f"Added rate-limited request for {symbol} {bar_size} to queue"
            )
            return request_id
        else:
            # Direct call (no rate limiting)
            return make_request()

    def download_historical_data(
        self,
        symbol: str,
        duration: str = "1 D",
        bar_size: str = "1 min",
        what_to_show: str = "TRADES",
        exchange: str = "SMART",
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Download historical data for a symbol

        Args:
            symbol: Stock symbol (e.g., 'MSTR')
            duration: How far back to go (e.g., '1 D', '5 D', '1 W', '1 M')
            bar_size: Bar size (e.g., '1 min', '5 mins', '1 hour', '1 day')
            what_to_show: What data to show ('TRADES', 'MIDPOINT', 'BID', 'ASK')
            exchange: Exchange to use (default: 'SMART')

        Returns:
            List of historical bars or None if failed
        """
        if not self.ib_connector:
            self.logger.error("Not connected to IB")
            return None

        try:
            self.logger.info(f"Requesting historical data for {symbol}")
            self.logger.info(f"Duration: {duration}, Bar size: {bar_size}")

            # Request historical data
            req_id = self.ib_connector.request_historical_data(
                symbol=symbol, duration=duration, bar_size=bar_size, exchange=exchange
            )

            if req_id < 0:
                self.logger.error(f"Failed to request historical data for {symbol}")
                return None

            # Wait for data to arrive
            self.logger.info("Waiting for historical data...")
            time.sleep(10)  # Give IB time to send data

            # Get historical data from connector
            historical_data = getattr(self.ib_connector, "historical_data", {})

            if req_id not in historical_data or not historical_data[req_id]:
                self.logger.warning(f"No historical data received for {symbol}")
                return None

            bars = historical_data[req_id]
            self.logger.info(f"Received {len(bars)} bars for {symbol}")

            # Convert to dictionary format
            data = []
            for bar in bars:
                data.append(
                    {
                        "symbol": symbol,
                        "datetime": bar.datetime,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                        "bar_size": bar_size,
                        "exchange": exchange,
                    }
                )

            # Validate data if validation is enabled
            if self.enable_validation and self.validator and data:
                self.logger.info(f"Validating downloaded data for {symbol}...")
                validation_report = self.validator.validate_data(data, symbol)

                # Log validation results
                self.logger.info(
                    f"Data quality score: {validation_report.quality_score:.1f}%"
                )

                if validation_report.has_errors():
                    self.logger.error(
                        f"Critical data quality issues detected for {symbol}"
                    )
                    for issue in validation_report.issues:
                        if issue.severity.value in ["ERROR", "CRITICAL"]:
                            self.logger.error(
                                f"[{issue.severity.value}] {issue.category}: {issue.message}"
                            )

                elif validation_report.has_warnings():
                    self.logger.warning(f"Data quality warnings for {symbol}")
                    for issue in validation_report.issues:
                        if issue.severity.value == "WARNING":
                            self.logger.warning(
                                f"[{issue.severity.value}] {issue.category}: {issue.message}"
                            )

                else:
                    self.logger.info(f"Data quality validation passed for {symbol}")

                # Log validation summary (validation report not stored with data for export)
                # This prevents issues with CSV/JSON/Parquet serialization
                self.logger.info(
                    f"Validation report available - Quality Score: {validation_report.quality_score:.1f}%"
                )

            return data

        except Exception as e:
            self.logger.error(f"Error downloading historical data for {symbol}: {e}")
            return None

    def save_to_csv(
        self, data: List[Dict[str, Any]], symbol: str, bar_size: str
    ) -> str:
        """
        Save historical data to CSV file

        Args:
            data: Historical data
            symbol: Stock symbol
            bar_size: Bar size used

        Returns:
            Path to saved file
        """
        if not data:
            raise ValueError("No data to save")

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{symbol}_{bar_size.replace(' ', '_')}_{timestamp}.csv"
        filepath = self.data_path / filename

        try:
            # Write to CSV
            with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "symbol",
                    "datetime",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "bar_size",
                    "exchange",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for row in data:
                    writer.writerow(row)

            self.logger.info(f"Data saved to CSV: {filepath}")
            self.logger.info(f"File size: {filepath.stat().st_size} bytes")
            return str(filepath)

        except Exception as e:
            self.logger.error(f"Error saving to CSV: {e}")
            raise

    def save_to_json(
        self, data: List[Dict[str, Any]], symbol: str, bar_size: str
    ) -> str:
        """
        Save historical data to JSON file

        Args:
            data: Historical data
            symbol: Stock symbol
            bar_size: Bar size used

        Returns:
            Path to saved file
        """
        if not data:
            raise ValueError("No data to save")

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{symbol}_{bar_size.replace(' ', '_')}_{timestamp}.json"
        filepath = self.data_path / filename

        try:
            # Convert datetime objects to strings for JSON serialization
            json_data = []
            for row in data:
                json_row = row.copy()
                if isinstance(json_row["datetime"], datetime):
                    json_row["datetime"] = json_row["datetime"].isoformat()
                json_data.append(json_row)

            # Write to JSON
            with open(filepath, "w", encoding="utf-8") as jsonfile:
                json.dump(json_data, jsonfile, indent=2, ensure_ascii=False)

            self.logger.info(f"Data saved to JSON: {filepath}")
            self.logger.info(f"File size: {filepath.stat().st_size} bytes")
            return str(filepath)

        except Exception as e:
            self.logger.error(f"Error saving to JSON: {e}")
            raise

    def save_to_parquet(
        self, data: List[Dict[str, Any]], symbol: str, bar_size: str
    ) -> str:
        """
        Save historical data to Parquet file (efficient for large datasets)

        Args:
            data: Historical data
            symbol: Stock symbol
            bar_size: Bar size used

        Returns:
            Path to saved file
        """
        if not data:
            raise ValueError("No data to save")

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{symbol}_{bar_size.replace(' ', '_')}_{timestamp}.parquet"
        filepath = self.processed_path / filename

        try:
            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Ensure datetime column is properly typed
            df["datetime"] = pd.to_datetime(df["datetime"])

            # Save to Parquet
            df.to_parquet(filepath, index=False)

            self.logger.info(f"Data saved to Parquet: {filepath}")
            self.logger.info(f"File size: {filepath.stat().st_size} bytes")
            self.logger.info(f"DataFrame shape: {df.shape}")
            return str(filepath)

        except Exception as e:
            self.logger.error(f"Error saving to Parquet: {e}")
            raise

    def download_and_save(
        self,
        symbol: str,
        duration: str = "1 D",
        bar_size: str = "1 min",
        save_formats: List[str] = ["csv", "json", "parquet"],
    ) -> Dict[str, str]:
        """
        Download historical data and save in multiple formats

        Args:
            symbol: Stock symbol
            duration: Duration to download
            bar_size: Bar size
            save_formats: List of formats to save ('csv', 'json', 'parquet')

        Returns:
            Dictionary with format as key and filepath as value
        """
        saved_files = {}

        try:
            # Download data
            self.logger.info(f"Starting download for {symbol}")
            data = self.download_historical_data(symbol, duration, bar_size)

            if not data:
                self.logger.error(f"No data downloaded for {symbol}")
                return saved_files

            self.logger.info(f"Downloaded {len(data)} bars for {symbol}")

            # Save in requested formats
            for format_type in save_formats:
                try:
                    if format_type.lower() == "csv":
                        filepath = self.save_to_csv(data, symbol, bar_size)
                        saved_files["csv"] = filepath
                    elif format_type.lower() == "json":
                        filepath = self.save_to_json(data, symbol, bar_size)
                        saved_files["json"] = filepath
                    elif format_type.lower() == "parquet":
                        filepath = self.save_to_parquet(data, symbol, bar_size)
                        saved_files["parquet"] = filepath
                    else:
                        self.logger.warning(f"Unknown format: {format_type}")

                except Exception as e:
                    self.logger.error(f"Error saving in {format_type} format: {e}")

            return saved_files

        except Exception as e:
            self.logger.error(f"Error in download_and_save for {symbol}: {e}")
            return saved_files

    def download_multi_timeframe_database(
        self, symbol: str, duration: str = "2 Y"
    ) -> Dict[str, Any]:
        """
        Download complete 2-year database for all timeframes with enterprise validation
        Creates separate files: MSTR_1min, MSTR_15min, MSTR_1hour, MSTR_4hour, MSTR_daily

        Args:
            symbol: Stock symbol (e.g., 'MSTR')
            duration: Duration to download (default: '2 Y' for 2 years)

        Returns:
            Dictionary with download results and validation summary
        """
        self.logger.info(f"=" * 60)
        self.logger.info(f"Starting Multi-Timeframe Database Creation: {symbol}")
        self.logger.info(f"Duration: {duration}")
        self.logger.info(f"Target: 99.95%+ Data Integrity")
        self.logger.info(f"=" * 60)

        # Define timeframes to download
        ib_timeframes = {
            "1 min": TimeFrame.MIN_1,
            "15 mins": TimeFrame.MIN_15,
            "1 hour": TimeFrame.HOUR_1,
            "4 hours": TimeFrame.HOUR_4,
            "1 day": TimeFrame.DAILY,
        }

        results = {
            "symbol": symbol,
            "duration": duration,
            "timeframes": {},
            "validation_summary": {},
            "overall_success": False,
        }

        timeframe_data = {}

        try:
            # Download data for each timeframe
            for ib_bar_size, timeframe_enum in ib_timeframes.items():
                self.logger.info(f"\nDownloading {timeframe_enum.value} data...")

                # Download raw data from IB
                raw_data = self.download_historical_data(
                    symbol=symbol,
                    duration=duration,
                    bar_size=ib_bar_size,
                    what_to_show="TRADES",
                    exchange="SMART",
                )

                if not raw_data:
                    self.logger.error(f"Failed to download {timeframe_enum.value} data")
                    results["timeframes"][timeframe_enum.value] = {
                        "status": "FAILED",
                        "error": "No data received from IB",
                    }
                    continue

                # Validate data if multi-timeframe validation is enabled
                if self.multi_timeframe_validation and self.multi_tf_validator:
                    validated_data = self.multi_tf_validator.validate_timeframe_data(
                        raw_data, timeframe_enum, symbol
                    )
                    timeframe_data[timeframe_enum] = validated_data

                    quality_score = validated_data.quality_score
                    issues_count = (
                        len(validated_data.validation_report.issues)
                        if validated_data.validation_report
                        else 0
                    )

                    self.logger.info(
                        f"{timeframe_enum.value} validation: {quality_score:.2f}% "
                        f"({issues_count} issues)"
                    )
                else:
                    # No validation - just store raw data
                    df = pd.DataFrame(raw_data)
                    timeframe_data[timeframe_enum] = TimeframeData(
                        timeframe=timeframe_enum,
                        data=df,
                        quality_score=100.0,  # Assume perfect if no validation
                        records_count=len(df),
                    )
                    quality_score = 100.0
                    issues_count = 0

                # Save to separate files for this timeframe
                try:
                    # Save as Parquet (most efficient for analysis)
                    parquet_file = self._save_timeframe_parquet(
                        raw_data, symbol, timeframe_enum
                    )

                    # Save as CSV for backup/human-readable
                    csv_file = self._save_timeframe_csv(
                        raw_data, symbol, timeframe_enum
                    )

                    results["timeframes"][timeframe_enum.value] = {
                        "status": "SUCCESS",
                        "records_count": len(raw_data),
                        "quality_score": f"{quality_score:.2f}%",
                        "issues_count": issues_count,
                        "files": {"parquet": parquet_file, "csv": csv_file},
                    }

                    self.logger.info(
                        f"✅ {timeframe_enum.value}: {len(raw_data)} records, "
                        f"{quality_score:.2f}% quality"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Failed to save {timeframe_enum.value} data: {e}"
                    )
                    results["timeframes"][timeframe_enum.value] = {
                        "status": "SAVE_FAILED",
                        "error": str(e),
                    }

            # Generate comprehensive validation summary
            if (
                self.multi_timeframe_validation
                and self.multi_tf_validator
                and timeframe_data
            ):
                validation_summary = self.multi_tf_validator.get_validation_summary(
                    timeframe_data
                )
                results["validation_summary"] = validation_summary

                # Check if all timeframes pass quality threshold
                all_pass = validation_summary["overall"]["all_pass_threshold"]
                results["overall_success"] = all_pass

                self.logger.info(f"\n" + "=" * 60)
                self.logger.info(f"VALIDATION SUMMARY")
                self.logger.info(f"=" * 60)
                self.logger.info(
                    f"Total Records: {validation_summary['overall']['total_records']:,}"
                )
                self.logger.info(
                    f"Total Issues: {validation_summary['overall']['total_issues']}"
                )
                self.logger.info(
                    f"Minimum Quality: {validation_summary['overall']['minimum_quality_score']}"
                )
                self.logger.info(
                    f"Enterprise Standard: {'✅ PASSED' if all_pass else '❌ FAILED'}"
                )

                for tf_name, tf_data in validation_summary["timeframes"].items():
                    status = "✅" if tf_data["passes_threshold"] else "❌"
                    self.logger.info(
                        f"  {tf_name:>8}: {tf_data['quality_score']} {status}"
                    )

            else:
                # No validation summary available
                success_count = sum(
                    1
                    for tf_result in results["timeframes"].values()
                    if tf_result.get("status") == "SUCCESS"
                )
                results["overall_success"] = success_count == len(ib_timeframes)

            return results

        except Exception as e:
            self.logger.error(f"Error in multi-timeframe download: {e}")
            results["error"] = str(e)
            return results

    def _save_timeframe_parquet(
        self, data: List[Dict[str, Any]], symbol: str, timeframe: TimeFrame
    ) -> str:
        """Save timeframe data as Parquet file"""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"{symbol}_{timeframe.value}_{timestamp}.parquet"
        filepath = self.processed_path / filename

        df = pd.DataFrame(data)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.to_parquet(filepath, index=False)

        self.logger.info(
            f"Parquet saved: {filepath} ({filepath.stat().st_size:,} bytes)"
        )
        return str(filepath)

    def _save_timeframe_csv(
        self, data: List[Dict[str, Any]], symbol: str, timeframe: TimeFrame
    ) -> str:
        """Save timeframe data as CSV file"""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        filename = f"{symbol}_{timeframe.value}_{timestamp}.csv"
        filepath = self.data_path / filename

        fieldnames = [
            "symbol",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "bar_size",
            "exchange",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                writer.writerow(row)

        self.logger.info(f"CSV saved: {filepath} ({filepath.stat().st_size:,} bytes)")
        return str(filepath)


def main():
    """Main function for multi-timeframe database creation"""
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)

    logger.info("Starting Multi-Timeframe Database Creation")

    # Create downloader with multi-timeframe validation
    downloader = HistoricalDataDownloader(multi_timeframe_validation=True)

    try:
        # Connect to IB
        if not downloader.connect_to_ib():
            logger.error("Failed to connect to IB")
            return False

        # Create complete 2-year MSTR database
        symbol = "MSTR"
        duration = "2 Y"  # 2 years of data

        logger.info(f"Creating {symbol} database: {duration} across all timeframes")

        # Download all timeframes with enterprise validation
        results = downloader.download_multi_timeframe_database(
            symbol=symbol, duration=duration
        )

        # Report comprehensive results
        if results["overall_success"]:
            logger.info("=" * 60)
            logger.info("DATABASE CREATION SUCCESSFUL!")
            logger.info("=" * 60)

            for tf_name, tf_result in results["timeframes"].items():
                if tf_result.get("status") == "SUCCESS":
                    logger.info(
                        f"{tf_name:>8}: {tf_result['records_count']:,} records, "
                        f"Quality: {tf_result['quality_score']}"
                    )
                    logger.info(f"         Parquet: {tf_result['files']['parquet']}")
                    logger.info(f"         CSV: {tf_result['files']['csv']}")
        else:
            logger.error("=" * 60)
            logger.error("DATABASE CREATION FAILED!")
            logger.error("=" * 60)

            for tf_name, tf_result in results["timeframes"].items():
                status = tf_result.get("status", "UNKNOWN")
                if status != "SUCCESS":
                    logger.error(f"{tf_name}: {status}")
                    if "error" in tf_result:
                        logger.error(f"  Error: {tf_result['error']}")

        # Display validation summary if available
        if "validation_summary" in results and results["validation_summary"]:
            logger.info("\nValidation Summary:")
            vs = results["validation_summary"]
            logger.info(f"Target Quality Threshold: {vs['target_quality_threshold']}")
            logger.info(
                f"Minimum Quality Achieved: {vs['overall']['minimum_quality_score']}"
            )
            logger.info(
                f"Enterprise Standard: {'PASSED' if vs['overall']['all_pass_threshold'] else 'FAILED'}"
            )

        return results["overall_success"]

    except Exception as e:
        logger.error(f"Error in main: {e}")
        return False

    finally:
        # Always disconnect
        downloader.disconnect_from_ib()


if __name__ == "__main__":
    print("=" * 60)
    print("Historical Data Downloader - MSTR Demo")
    print("=" * 60)

    success = main()

    print("=" * 60)
    if success:
        print("Historical data download completed successfully!")
    else:
        print("Historical data download failed!")
    print("=" * 60)
