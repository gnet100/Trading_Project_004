"""
Trading Project 004 - Enterprise Validation Demo
Demo script showing complete multi-timeframe database creation with validation
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from historical_data_downloader import HistoricalDataDownloader  # noqa: E402
from logging_setup import get_logger, setup_logging  # noqa: E402


def main():
    """Demo of enterprise multi-timeframe database creation"""
    print("=" * 80)
    print("ENTERPRISE VALIDATION DEMO")
    print("Multi-Timeframe Database Creation with 99.95%+ Data Integrity")
    print("=" * 80)
    print()
    print("This demo will:")
    print("1. Connect to Interactive Brokers")
    print("2. Download 1 day of MSTR data for demonstration")
    print("3. Create 5 separate files: 1min, 15min, 1hour, 4hour, daily")
    print("4. Validate each timeframe with enterprise-level checks")
    print("5. Generate comprehensive quality report")
    print()
    print("NOTE: For full 2-year database, change duration to '2 Y'")
    print("=" * 80)

    # Setup logging
    setup_logging()
    logger = get_logger(__name__)

    try:
        # Create downloader with enterprise validation
        downloader = HistoricalDataDownloader(multi_timeframe_validation=True)

        # Connect to IB
        logger.info("Connecting to Interactive Brokers...")
        if not downloader.connect_to_ib():
            print("FAILED: Could not connect to Interactive Brokers")
            print("Please ensure TWS is running and configured correctly")
            return False

        print("Connected to Interactive Brokers")
        print()

        # Create multi-timeframe database (demo with 1 day)
        symbol = "MSTR"
        duration = "1 D"  # Use "2 Y" for full database

        print(f"Creating {symbol} database...")
        print(f"Duration: {duration}")
        print(f"Timeframes: 1min, 15min, 1hour, 4hour, daily")
        print()

        results = downloader.download_multi_timeframe_database(
            symbol=symbol, duration=duration
        )

        # Display results
        print("=" * 80)
        print("RESULTS SUMMARY")
        print("=" * 80)

        if results["overall_success"]:
            print("DATABASE CREATION SUCCESSFUL!")
            print()

            total_records = 0
            for tf_name, tf_result in results["timeframes"].items():
                if tf_result.get("status") == "SUCCESS":
                    records = tf_result["records_count"]
                    quality = tf_result["quality_score"]
                    issues = tf_result["issues_count"]

                    print(f"[{tf_name.upper()}]")
                    print(f"   Records: {records:,}")
                    print(f"   Quality: {quality}")
                    print(f"   Issues: {issues}")
                    print("   Files:")
                    print(f"     Parquet: {tf_result['files']['parquet']}")
                    print(f"     CSV: {tf_result['files']['csv']}")
                    print()

                    total_records += records

            print(f"TOTAL RECORDS: {total_records:,}")

            # Validation summary
            if "validation_summary" in results:
                vs = results["validation_summary"]
                print(f"QUALITY TARGET: {vs['target_quality_threshold']}")
                print(f"MINIMUM QUALITY: {vs['overall']['minimum_quality_score']}")
                status = 'PASSED' if vs['overall']['all_pass_threshold'] else 'FAILED'
                print(f"ENTERPRISE STANDARD: {status}")

        else:
            print("DATABASE CREATION FAILED")
            print()
            for tf_name, tf_result in results["timeframes"].items():
                status = tf_result.get("status", "UNKNOWN")
                if status != "SUCCESS":
                    print(f"FAILED {tf_name}: {status}")
                    if "error" in tf_result:
                        print(f"   Error: {tf_result['error']}")

        print("=" * 80)
        return results["overall_success"]

    except Exception as e:
        logger.error(f"Demo error: {e}")
        print(f"Error: {e}")
        return False

    finally:
        try:
            downloader.disconnect_from_ib()
            print("Disconnected from Interactive Brokers")
        except Exception:
            pass


if __name__ == "__main__":
    success = main()
    if success:
        print("Demo completed successfully!")
        print()
        print("To create full 2-year database:")
        print("1. Edit demo_enterprise_validation.py")
        print("2. Change duration from '1 D' to '2 Y'")
        print("3. Run the script again")
    else:
        print("Demo failed!")

    print("\nPress Enter to exit...")
    input()
