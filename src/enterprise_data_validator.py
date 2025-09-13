"""
Trading Project 004 - Enterprise Data Validator
Advanced multi-layer validation system for 99.95%+ data integrity
Treats market data as "DNA של המניה" with enterprise-level reliability
"""

import asyncio
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from statistics import median, stdev
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))
from data_validator import DataValidator, ValidationReport, ValidationSeverity
from logging_setup import get_logger


class ValidationLayer(Enum):
    """Validation layers for enterprise data integrity"""

    PRE_DOWNLOAD = "PRE_DOWNLOAD"
    MULTI_SOURCE = "MULTI_SOURCE"
    MATHEMATICAL = "MATHEMATICAL"
    CRYPTOGRAPHIC = "CRYPTOGRAPHIC"
    CONTINUOUS = "CONTINUOUS"
    CONSENSUS = "CONSENSUS"


@dataclass
class ConsensusMetrics:
    """Metrics for multi-source consensus validation"""

    ib_data: float
    yahoo_data: float
    consensus_value: float
    deviation_percentage: float
    confidence_score: float
    data_point: str
    timestamp: str


@dataclass
class DataDNA:
    """Cryptographic DNA fingerprint of market data"""

    symbol: str
    timeframe: str
    data_hash: str
    chain_hash: str
    validation_timestamp: datetime
    quality_score: float
    consensus_metrics: List[ConsensusMetrics] = field(default_factory=list)
    integrity_verified: bool = False


class EnterpriseDataValidator:
    """
    Enterprise-level data validation system
    Target: 99.95%+ data integrity for statistical research
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.base_validator = DataValidator()
        self.min_quality_threshold = 99.95  # Enterprise minimum
        self.consensus_tolerance = 0.05  # 5% tolerance for multi-source agreement
        self.chain_of_trust = []  # Blockchain-inspired integrity chain

        self.logger.info("Enterprise Data Validator initialized")
        self.logger.info(f"Quality threshold: {self.min_quality_threshold}%")
        self.logger.info(f"Consensus tolerance: {self.consensus_tolerance * 100}%")

    async def validate_with_consensus(
        self, ib_data: List[Dict[str, Any]], symbol: str
    ) -> Tuple[ValidationReport, DataDNA]:
        """
        Layer 1 & 2: Multi-Source Cross-Validation with Consensus Analysis

        Args:
            ib_data: Interactive Brokers data
            symbol: Stock symbol

        Returns:
            Validation report and data DNA fingerprint
        """
        self.logger.info(f"Starting enterprise validation for {symbol}")

        # Layer 1: Base validation
        base_report = self.base_validator.validate_data(ib_data, symbol)

        if base_report.quality_score < 95.0:
            self.logger.error(f"Base validation failed: {base_report.quality_score}%")
            return base_report, None

        # Layer 2: Multi-source validation
        try:
            yahoo_data = await self._fetch_yahoo_data(symbol, len(ib_data))
            consensus_metrics = await self._calculate_consensus(
                ib_data, yahoo_data, symbol
            )

            # Create data DNA
            data_dna = self._create_data_dna(ib_data, symbol, consensus_metrics)

            # Calculate enhanced quality score
            enhanced_score = self._calculate_enhanced_quality(
                base_report.quality_score, consensus_metrics
            )

            # Update validation report
            enhanced_report = self._create_enhanced_report(
                base_report, enhanced_score, consensus_metrics
            )

            self.logger.info(f"Enterprise validation complete: {enhanced_score:.2f}%")

            if enhanced_score >= self.min_quality_threshold:
                data_dna.integrity_verified = True
                self._add_to_chain_of_trust(data_dna)
                self.logger.info(f"✅ Data integrity verified: {enhanced_score:.2f}%")
            else:
                self.logger.error(f"❌ Data integrity failed: {enhanced_score:.2f}%")

            return enhanced_report, data_dna

        except Exception as e:
            self.logger.error(f"Enterprise validation error: {e}")
            return base_report, None

    async def _fetch_yahoo_data(
        self, symbol: str, expected_bars: int
    ) -> Optional[pd.DataFrame]:
        """Fetch comparison data from Yahoo Finance"""
        try:
            self.logger.info(f"Fetching Yahoo Finance data for {symbol}")

            # Get last trading day data
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(
                days=5
            )  # Get more data to ensure coverage

            # Fetch 1-minute data
            yahoo_df = ticker.history(start=start_date, end=end_date, interval="1m")

            if yahoo_df.empty:
                self.logger.warning(f"No Yahoo data received for {symbol}")
                return None

            # Clean and prepare data
            yahoo_df = yahoo_df.dropna()
            yahoo_df.reset_index(inplace=True)

            self.logger.info(f"Yahoo Finance: {len(yahoo_df)} bars received")
            return yahoo_df

        except Exception as e:
            self.logger.error(f"Yahoo Finance fetch error: {e}")
            return None

    async def _calculate_consensus(
        self,
        ib_data: List[Dict[str, Any]],
        yahoo_data: Optional[pd.DataFrame],
        symbol: str,
    ) -> List[ConsensusMetrics]:
        """Calculate consensus metrics between data sources"""
        consensus_metrics = []

        if not yahoo_data or yahoo_data.empty:
            self.logger.warning("No Yahoo data for consensus calculation")
            return consensus_metrics

        try:
            # Convert IB data to DataFrame for comparison
            ib_df = pd.DataFrame(ib_data)
            ib_df["datetime"] = pd.to_datetime(ib_df["datetime"])

            # Align time frames (match closest times within 1 minute)
            for _, ib_row in ib_df.iterrows():
                ib_time = ib_row["datetime"]

                # Find closest Yahoo time
                time_diffs = abs(yahoo_data["Datetime"] - ib_time)
                closest_idx = time_diffs.idxmin()

                if time_diffs.iloc[closest_idx] <= pd.Timedelta(minutes=2):
                    yahoo_row = yahoo_data.iloc[closest_idx]

                    # Compare OHLC values
                    comparisons = [
                        ("open", ib_row["open"], yahoo_row["Open"]),
                        ("high", ib_row["high"], yahoo_row["High"]),
                        ("low", ib_row["low"], yahoo_row["Low"]),
                        ("close", ib_row["close"], yahoo_row["Close"]),
                    ]

                    for data_point, ib_val, yahoo_val in comparisons:
                        if pd.notna(ib_val) and pd.notna(yahoo_val) and yahoo_val > 0:
                            deviation = abs(ib_val - yahoo_val) / yahoo_val
                            consensus_val = (ib_val + yahoo_val) / 2
                            confidence = max(
                                0, 1 - (deviation / self.consensus_tolerance)
                            )

                            metrics = ConsensusMetrics(
                                ib_data=float(ib_val),
                                yahoo_data=float(yahoo_val),
                                consensus_value=float(consensus_val),
                                deviation_percentage=float(deviation * 100),
                                confidence_score=float(confidence),
                                data_point=data_point,
                                timestamp=ib_time.isoformat(),
                            )
                            consensus_metrics.append(metrics)

            self.logger.info(f"Calculated {len(consensus_metrics)} consensus metrics")
            return consensus_metrics

        except Exception as e:
            self.logger.error(f"Consensus calculation error: {e}")
            return []

    def _calculate_enhanced_quality(
        self, base_score: float, consensus_metrics: List[ConsensusMetrics]
    ) -> float:
        """Calculate enhanced quality score with consensus weighting"""
        if not consensus_metrics:
            return base_score * 0.8  # Penalize lack of consensus data

        # Calculate average confidence from consensus
        confidence_scores = [m.confidence_score for m in consensus_metrics]
        avg_confidence = sum(confidence_scores) / len(confidence_scores)

        # Calculate deviation penalty
        deviations = [m.deviation_percentage for m in consensus_metrics]
        avg_deviation = sum(deviations) / len(deviations)
        deviation_penalty = min(avg_deviation / 5.0, 10.0)  # Max 10% penalty

        # Enhanced score calculation
        consensus_bonus = avg_confidence * 10  # Up to 10% bonus for good consensus
        enhanced_score = base_score + consensus_bonus - deviation_penalty

        # Ensure we don't exceed 100%
        enhanced_score = min(enhanced_score, 100.0)

        self.logger.info(
            f"Quality enhancement: base={base_score:.1f}%, "
            f"consensus_bonus={consensus_bonus:.1f}%, "
            f"deviation_penalty={deviation_penalty:.1f}%, "
            f"final={enhanced_score:.1f}%"
        )

        return enhanced_score

    def _create_data_dna(
        self,
        data: List[Dict[str, Any]],
        symbol: str,
        consensus_metrics: List[ConsensusMetrics],
    ) -> DataDNA:
        """Create cryptographic DNA fingerprint for data"""
        try:
            # Create data hash
            data_str = json.dumps(data, sort_keys=True, default=str)
            data_hash = hashlib.sha256(data_str.encode()).hexdigest()

            # Create chain hash (links to previous data)
            if self.chain_of_trust:
                prev_hash = self.chain_of_trust[-1].chain_hash
                chain_input = f"{data_hash}{prev_hash}{time.time()}"
            else:
                chain_input = f"{data_hash}{time.time()}"

            chain_hash = hashlib.sha256(chain_input.encode()).hexdigest()

            # Determine timeframe from data
            timeframe = "1min" if data else "unknown"
            if data and len(data) > 1:
                first_time = pd.to_datetime(data[0]["datetime"])
                second_time = pd.to_datetime(data[1]["datetime"])
                diff = (second_time - first_time).total_seconds() / 60
                timeframe = f"{int(diff)}min"

            dna = DataDNA(
                symbol=symbol,
                timeframe=timeframe,
                data_hash=data_hash,
                chain_hash=chain_hash,
                validation_timestamp=datetime.now(),
                quality_score=0.0,  # Will be set later
                consensus_metrics=consensus_metrics,
                integrity_verified=False,
            )

            self.logger.info(f"Data DNA created: {symbol} - {data_hash[:16]}...")
            return dna

        except Exception as e:
            self.logger.error(f"Data DNA creation error: {e}")
            raise

    def _add_to_chain_of_trust(self, data_dna: DataDNA):
        """Add validated data to blockchain-inspired chain of trust"""
        self.chain_of_trust.append(data_dna)

        # Keep only last 1000 entries to prevent memory issues
        if len(self.chain_of_trust) > 1000:
            self.chain_of_trust = self.chain_of_trust[-1000:]

        self.logger.info(
            f"Added to chain of trust: {data_dna.symbol} - "
            f"Chain length: {len(self.chain_of_trust)}"
        )

    def _create_enhanced_report(
        self,
        base_report: ValidationReport,
        enhanced_score: float,
        consensus_metrics: List[ConsensusMetrics],
    ) -> ValidationReport:
        """Create enhanced validation report with consensus analysis"""
        enhanced_report = ValidationReport(
            symbol=base_report.symbol,
            total_records=base_report.total_records,
            quality_score=enhanced_score,
            validation_timestamp=datetime.now(),
        )

        # Copy base issues
        enhanced_report.issues = base_report.issues.copy()

        # Add consensus analysis issues
        if consensus_metrics:
            high_deviation_count = sum(
                1
                for m in consensus_metrics
                if m.deviation_percentage > self.consensus_tolerance * 100
            )

            if high_deviation_count > len(consensus_metrics) * 0.1:  # More than 10%
                from data_validator import ValidationIssue

                issue = ValidationIssue(
                    severity=ValidationSeverity.WARNING
                    if enhanced_score >= self.min_quality_threshold
                    else ValidationSeverity.ERROR,
                    category="CONSENSUS_VALIDATION",
                    message=f"High deviation in {high_deviation_count}/{len(consensus_metrics)} "
                    f"data points compared to Yahoo Finance",
                    affected_records=[],
                    details={
                        "avg_deviation": sum(
                            m.deviation_percentage for m in consensus_metrics
                        )
                        / len(consensus_metrics),
                        "max_deviation": max(
                            m.deviation_percentage for m in consensus_metrics
                        ),
                        "consensus_sources": ["Interactive Brokers", "Yahoo Finance"],
                    },
                )
                enhanced_report.issues.append(issue)

        return enhanced_report

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of enterprise validation system status"""
        return {
            "validator_type": "Enterprise Multi-Layer",
            "quality_threshold": f"{self.min_quality_threshold}%",
            "consensus_tolerance": f"{self.consensus_tolerance * 100}%",
            "chain_of_trust_length": len(self.chain_of_trust),
            "last_validation": self.chain_of_trust[-1].validation_timestamp.isoformat()
            if self.chain_of_trust
            else None,
            "validated_symbols": list(set(dna.symbol for dna in self.chain_of_trust)),
            "integrity_verified_count": sum(
                1 for dna in self.chain_of_trust if dna.integrity_verified
            ),
        }


async def main():
    """Demo of enterprise validation system"""
    from historical_data_downloader import HistoricalDataDownloader

    print("=" * 80)
    print("Enterprise Data Validator - MSTR Demo")
    print("Target: 99.95%+ Data Integrity")
    print("=" * 80)

    # Initialize enterprise validator
    validator = EnterpriseDataValidator()

    # Get sample data (you would integrate this with HistoricalDataDownloader)
    # For demo, create sample data structure
    sample_data = [
        {
            "symbol": "MSTR",
            "datetime": datetime.now() - timedelta(minutes=5),
            "open": 150.0,
            "high": 151.0,
            "low": 149.5,
            "close": 150.5,
            "volume": 10000,
        },
        {
            "symbol": "MSTR",
            "datetime": datetime.now() - timedelta(minutes=4),
            "open": 150.5,
            "high": 152.0,
            "low": 150.0,
            "close": 151.5,
            "volume": 12000,
        },
    ]

    # Run enterprise validation
    try:
        report, dna = await validator.validate_with_consensus(sample_data, "MSTR")

        print(f"\nValidation Results:")
        print(f"Quality Score: {report.quality_score:.2f}%")
        print(
            f"Enterprise Standard: {'✅ PASSED' if report.quality_score >= validator.min_quality_threshold else '❌ FAILED'}"
        )

        if dna:
            print(f"\nData DNA Fingerprint:")
            print(f"Symbol: {dna.symbol}")
            print(f"Data Hash: {dna.data_hash[:32]}...")
            print(f"Chain Hash: {dna.chain_hash[:32]}...")
            print(f"Integrity Verified: {'✅' if dna.integrity_verified else '❌'}")
            print(f"Consensus Metrics: {len(dna.consensus_metrics)} comparisons")

        # Show validation summary
        summary = validator.get_validation_summary()
        print(f"\nSystem Summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"Validation error: {e}")

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
