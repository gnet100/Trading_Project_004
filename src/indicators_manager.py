#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic Indicators Manager - Trading Project 004
Flexible system for adding, removing, and calculating indicators

Features:
- Add/remove indicators dynamically via database migrations
- 7 categories: Price, Volume, Momentum, Volatility, Trend, Price+Volume, Correlation
- Starting indicators: Bollinger Bands, Volume SMA, ADX
- TA-Lib integration for calculations
- Batch calculation for performance
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from decimal import Decimal
import json
import logging

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

# Technical Analysis Library
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logging.warning("TA-Lib not available. Some indicators will use simplified calculations.")

from enhanced_dna_models import (
    EnhancedHistoricalData, IndicatorTemplate,
    TimeFrame, IndicatorCategory,
    create_enhanced_engine, Base
)

class IndicatorsManager:
    """
    Dynamic indicators management system

    Handles:
    - Adding/removing indicator columns
    - Calculating indicator values
    - Managing indicator templates
    - Batch processing for performance
    """

    def __init__(self, database_url: str = "sqlite:///enhanced_trading_project.db"):
        self.engine = create_enhanced_engine(database_url)
        self.logger = logging.getLogger(__name__)

        # Initialize default indicators if needed
        self._ensure_default_indicators()

    def _ensure_default_indicators(self):
        """Ensure default indicators exist in database"""
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=self.engine)

        with SessionLocal() as db:
            existing = db.query(IndicatorTemplate).count()
            if existing == 0:
                # Add default indicators
                defaults = self._get_default_indicators()
                for indicator in defaults:
                    db.add(indicator)
                db.commit()
                self.logger.info(f"Added {len(defaults)} default indicators")

    def _get_default_indicators(self) -> List[IndicatorTemplate]:
        """Get default indicator templates for Phase 1"""
        return [
            # Bollinger Bands (Volatility)
            IndicatorTemplate(
                name="Bollinger Bands Upper",
                category=IndicatorCategory.VOLATILITY,
                description="Bollinger Bands upper band (20-period, 2 std dev)",
                column_name="bollinger_upper",
                data_type="DECIMAL(12,6)",
                parameters='{"period": 20, "std_dev": 2.0}',
                is_active=True
            ),
            IndicatorTemplate(
                name="Bollinger Bands Middle",
                category=IndicatorCategory.PRICE,
                description="Bollinger Bands middle line (SMA 20)",
                column_name="bollinger_middle",
                data_type="DECIMAL(12,6)",
                parameters='{"period": 20}',
                is_active=True
            ),
            IndicatorTemplate(
                name="Bollinger Bands Lower",
                category=IndicatorCategory.VOLATILITY,
                description="Bollinger Bands lower band (20-period, 2 std dev)",
                column_name="bollinger_lower",
                data_type="DECIMAL(12,6)",
                parameters='{"period": 20, "std_dev": 2.0}',
                is_active=True
            ),
            IndicatorTemplate(
                name="Bollinger Width",
                category=IndicatorCategory.VOLATILITY,
                description="Bollinger Bands width percentage",
                column_name="bollinger_width",
                data_type="FLOAT",
                parameters='{"period": 20, "std_dev": 2.0}',
                is_active=True
            ),

            # Volume Indicators
            IndicatorTemplate(
                name="Volume SMA 20",
                category=IndicatorCategory.VOLUME,
                description="20-period Simple Moving Average of Volume",
                column_name="volume_sma_20",
                data_type="FLOAT",
                parameters='{"period": 20}',
                is_active=True
            ),
            IndicatorTemplate(
                name="Volume Ratio",
                category=IndicatorCategory.VOLUME,
                description="Current volume vs 20-period average",
                column_name="volume_ratio",
                data_type="FLOAT",
                parameters='{"period": 20}',
                is_active=True
            ),

            # ADX (Trend)
            IndicatorTemplate(
                name="ADX 14",
                category=IndicatorCategory.TREND,
                description="Average Directional Index (14-period)",
                column_name="adx_14",
                data_type="FLOAT",
                parameters='{"period": 14}',
                is_active=True,
                supports_1min=False,  # ADX not meaningful for 1min
                supports_5min=True
            ),
            IndicatorTemplate(
                name="ADX Plus DI",
                category=IndicatorCategory.TREND,
                description="Positive Directional Indicator",
                column_name="adx_plus_di",
                data_type="FLOAT",
                parameters='{"period": 14}',
                is_active=True,
                supports_1min=False,
                supports_5min=True
            ),
            IndicatorTemplate(
                name="ADX Minus DI",
                category=IndicatorCategory.TREND,
                description="Negative Directional Indicator",
                column_name="adx_minus_di",
                data_type="FLOAT",
                parameters='{"period": 14}',
                is_active=True,
                supports_1min=False,
                supports_5min=True
            ),

            # Additional Price/Momentum Indicators (placeholder for expansion)
            IndicatorTemplate(
                name="RSI 14",
                category=IndicatorCategory.MOMENTUM,
                description="Relative Strength Index (14-period)",
                column_name="rsi_14",
                data_type="FLOAT",
                parameters='{"period": 14}',
                is_active=False,  # Not calculated yet
                supports_1min=False
            ),
            IndicatorTemplate(
                name="MACD Line",
                category=IndicatorCategory.MOMENTUM,
                description="MACD Line (12,26,9)",
                column_name="macd_line",
                data_type="FLOAT",
                parameters='{"fast": 12, "slow": 26, "signal": 9}',
                is_active=False,  # Not calculated yet
                supports_1min=False
            ),
        ]

    def get_available_indicators(self, category: Optional[str] = None,
                               timeframe: Optional[TimeFrame] = None,
                               active_only: bool = True) -> List[IndicatorTemplate]:
        """
        Get available indicators with optional filtering

        Args:
            category: Filter by indicator category
            timeframe: Filter by supported timeframe
            active_only: Return only active indicators

        Returns:
            List of IndicatorTemplate objects
        """
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=self.engine)

        with SessionLocal() as db:
            query = db.query(IndicatorTemplate)

            if active_only:
                query = query.filter(IndicatorTemplate.is_active == True)

            if category:
                try:
                    cat_enum = IndicatorCategory(category.lower())
                    query = query.filter(IndicatorTemplate.category == cat_enum)
                except ValueError:
                    raise ValueError(f"Invalid category: {category}")

            # Timeframe filtering
            if timeframe:
                timeframe_column = f"supports_{timeframe.value.replace('min', '').replace('hour', 'hour')}"
                if timeframe == TimeFrame.MIN_1:
                    query = query.filter(IndicatorTemplate.supports_1min == True)
                elif timeframe == TimeFrame.MIN_5:
                    query = query.filter(IndicatorTemplate.supports_5min == True)
                elif timeframe == TimeFrame.MIN_15:
                    query = query.filter(IndicatorTemplate.supports_15min == True)
                elif timeframe == TimeFrame.HOUR_1:
                    query = query.filter(IndicatorTemplate.supports_1hour == True)
                elif timeframe == TimeFrame.HOUR_4:
                    query = query.filter(IndicatorTemplate.supports_4hour == True)
                elif timeframe == TimeFrame.DAILY:
                    query = query.filter(IndicatorTemplate.supports_daily == True)

            return query.all()

    def calculate_indicators(self, symbol: str, timeframe: TimeFrame,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           indicators: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculate indicators for given symbol and timeframe

        Args:
            symbol: Stock symbol
            timeframe: Time frame to calculate for
            start_date: Start date for calculation
            end_date: End date for calculation
            indicators: List of specific indicators to calculate (None = all active)

        Returns:
            Dictionary with calculation results and statistics
        """
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=self.engine)

        with SessionLocal() as db:
            # Get data for calculation
            query = db.query(EnhancedHistoricalData).filter(
                EnhancedHistoricalData.symbol == symbol,
                EnhancedHistoricalData.timeframe == timeframe
            )

            if start_date:
                query = query.filter(EnhancedHistoricalData.timestamp >= start_date)
            if end_date:
                query = query.filter(EnhancedHistoricalData.timestamp <= end_date)

            data = query.order_by(EnhancedHistoricalData.timestamp).all()

            if len(data) < 50:  # Need minimum data for meaningful calculations
                raise ValueError(f"Insufficient data: {len(data)} bars. Need at least 50.")

            # Convert to DataFrame for easier calculation
            df = pd.DataFrame([{
                'timestamp': record.timestamp,
                'open': float(record.open_price),
                'high': float(record.high_price),
                'low': float(record.low_price),
                'close': float(record.close_price),
                'volume': record.volume,
                'id': record.id
            } for record in data])

            # Get indicators to calculate
            if indicators is None:
                indicator_templates = self.get_available_indicators(timeframe=timeframe)
                indicators = [t.column_name for t in indicator_templates]
            else:
                # Validate requested indicators
                available = {t.column_name for t in self.get_available_indicators(timeframe=timeframe)}
                indicators = [i for i in indicators if i in available]

            # Calculate each indicator
            results = {
                'symbol': symbol,
                'timeframe': timeframe.value,
                'data_points': len(df),
                'calculated_indicators': [],
                'updated_records': 0,
                'errors': []
            }

            for indicator_name in indicators:
                try:
                    values = self._calculate_single_indicator(df, indicator_name)
                    if values is not None:
                        # Update database
                        updated_count = self._update_indicator_values(db, data, indicator_name, values)
                        results['calculated_indicators'].append(indicator_name)
                        results['updated_records'] += updated_count

                        self.logger.info(f"Calculated {indicator_name}: {updated_count} records updated")
                    else:
                        results['errors'].append(f"Failed to calculate {indicator_name}")

                except Exception as e:
                    error_msg = f"Error calculating {indicator_name}: {str(e)}"
                    results['errors'].append(error_msg)
                    self.logger.error(error_msg)

            db.commit()
            return results

    def _calculate_single_indicator(self, df: pd.DataFrame, indicator_name: str) -> Optional[np.ndarray]:
        """
        Calculate a single indicator

        Args:
            df: DataFrame with OHLCV data
            indicator_name: Name of indicator column to calculate

        Returns:
            Array of calculated values or None if calculation failed
        """
        try:
            # Bollinger Bands
            if indicator_name.startswith('bollinger'):
                return self._calculate_bollinger_bands(df, indicator_name)

            # Volume indicators
            elif indicator_name.startswith('volume'):
                return self._calculate_volume_indicators(df, indicator_name)

            # ADX indicators
            elif indicator_name.startswith('adx'):
                return self._calculate_adx_indicators(df, indicator_name)

            # RSI
            elif indicator_name == 'rsi_14':
                return self._calculate_rsi(df, 14)

            # MACD
            elif indicator_name.startswith('macd'):
                return self._calculate_macd_indicators(df, indicator_name)

            else:
                self.logger.warning(f"Unknown indicator: {indicator_name}")
                return None

        except Exception as e:
            self.logger.error(f"Calculation error for {indicator_name}: {e}")
            return None

    def _calculate_bollinger_bands(self, df: pd.DataFrame, indicator_name: str) -> Optional[np.ndarray]:
        """Calculate Bollinger Bands components"""
        period = 20
        std_dev = 2.0

        # Simple Moving Average (middle line)
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()

        if indicator_name == 'bollinger_upper':
            return sma + (std * std_dev)
        elif indicator_name == 'bollinger_middle':
            return sma
        elif indicator_name == 'bollinger_lower':
            return sma - (std * std_dev)
        elif indicator_name == 'bollinger_width':
            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)
            return ((upper - lower) / sma) * 100  # Width as percentage

        return None

    def _calculate_volume_indicators(self, df: pd.DataFrame, indicator_name: str) -> Optional[np.ndarray]:
        """Calculate volume-based indicators"""
        if indicator_name == 'volume_sma_20':
            return df['volume'].rolling(window=20).mean()

        elif indicator_name == 'volume_ratio':
            volume_avg = df['volume'].rolling(window=20).mean()
            return df['volume'] / volume_avg

        return None

    def _calculate_adx_indicators(self, df: pd.DataFrame, indicator_name: str) -> Optional[np.ndarray]:
        """Calculate ADX and Directional Indicators"""
        if not TALIB_AVAILABLE:
            # Simplified ADX calculation without TA-Lib
            return self._calculate_adx_simple(df, indicator_name)

        try:
            high = df['high'].values.astype(float)
            low = df['low'].values.astype(float)
            close = df['close'].values.astype(float)

            if indicator_name == 'adx_14':
                return talib.ADX(high, low, close, timeperiod=14)
            elif indicator_name == 'adx_plus_di':
                return talib.PLUS_DI(high, low, close, timeperiod=14)
            elif indicator_name == 'adx_minus_di':
                return talib.MINUS_DI(high, low, close, timeperiod=14)

        except Exception as e:
            self.logger.error(f"TA-Lib ADX calculation error: {e}")
            return self._calculate_adx_simple(df, indicator_name)

        return None

    def _calculate_adx_simple(self, df: pd.DataFrame, indicator_name: str) -> Optional[np.ndarray]:
        """Simplified ADX calculation for when TA-Lib is not available"""
        # This is a simplified version - full ADX calculation is complex
        # For production, TA-Lib installation is recommended

        if indicator_name == 'adx_14':
            # Simplified trend strength based on price movement
            price_change = df['close'].pct_change().abs()
            trend_strength = price_change.rolling(window=14).mean() * 100
            return np.clip(trend_strength, 0, 100)  # Clamp to 0-100 range

        # For DI indicators, return placeholder values
        elif indicator_name in ['adx_plus_di', 'adx_minus_di']:
            return np.full(len(df), 25.0)  # Neutral DI value

        return None

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[np.ndarray]:
        """Calculate RSI (Relative Strength Index)"""
        if TALIB_AVAILABLE:
            try:
                return talib.RSI(df['close'].values.astype(float), timeperiod=period)
            except Exception:
                pass

        # Manual RSI calculation
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.values

    def _calculate_macd_indicators(self, df: pd.DataFrame, indicator_name: str) -> Optional[np.ndarray]:
        """Calculate MACD components"""
        if TALIB_AVAILABLE:
            try:
                macd, signal, histogram = talib.MACD(df['close'].values.astype(float),
                                                  fastperiod=12, slowperiod=26, signalperiod=9)
                if indicator_name == 'macd_line':
                    return macd
                elif indicator_name == 'macd_signal':
                    return signal
                elif indicator_name == 'macd_histogram':
                    return histogram
            except Exception:
                pass

        # Manual MACD calculation
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        macd_line = ema_12 - ema_26

        if indicator_name == 'macd_line':
            return macd_line.values
        elif indicator_name == 'macd_signal':
            return macd_line.ewm(span=9).mean().values

        return None

    def _update_indicator_values(self, db: Session, data: List[EnhancedHistoricalData],
                               indicator_name: str, values: np.ndarray) -> int:
        """
        Update indicator values in database

        Args:
            db: Database session
            data: List of data records
            indicator_name: Column name to update
            values: Array of calculated values

        Returns:
            Number of records updated
        """
        updated_count = 0

        for i, record in enumerate(data):
            if i < len(values) and not np.isnan(values[i]):
                # Update the specific indicator column
                setattr(record, indicator_name, float(values[i]))
                updated_count += 1

        return updated_count

    def add_new_indicator(self, name: str, category: IndicatorCategory,
                         description: str, column_name: str,
                         data_type: str = "FLOAT",
                         parameters: Dict[str, Any] = None,
                         timeframe_support: Dict[str, bool] = None) -> bool:
        """
        Add a new indicator template and create database column

        Args:
            name: Human-readable indicator name
            category: Indicator category
            description: Description of what the indicator measures
            column_name: Database column name (must be unique)
            data_type: SQL data type (FLOAT, DECIMAL, etc.)
            parameters: Parameters for calculation
            timeframe_support: Which timeframes support this indicator

        Returns:
            True if successful, False otherwise
        """
        try:
            from sqlalchemy.orm import sessionmaker
            SessionLocal = sessionmaker(bind=self.engine)

            # Default timeframe support
            if timeframe_support is None:
                timeframe_support = {
                    'supports_1min': True,
                    'supports_5min': True,
                    'supports_15min': True,
                    'supports_1hour': True,
                    'supports_4hour': True,
                    'supports_daily': True
                }

            with SessionLocal() as db:
                # Check if column name already exists
                existing = db.query(IndicatorTemplate).filter(
                    IndicatorTemplate.column_name == column_name
                ).first()

                if existing:
                    raise ValueError(f"Indicator column '{column_name}' already exists")

                # Create indicator template
                template = IndicatorTemplate(
                    name=name,
                    category=category,
                    description=description,
                    column_name=column_name,
                    data_type=data_type,
                    parameters=json.dumps(parameters) if parameters else None,
                    is_active=True,
                    **timeframe_support
                )

                db.add(template)
                db.commit()

                # Add database column (would require Alembic migration in production)
                self._add_column_to_table(column_name, data_type)

                self.logger.info(f"Added new indicator: {name} ({column_name})")
                return True

        except Exception as e:
            self.logger.error(f"Error adding indicator {name}: {e}")
            return False

    def _add_column_to_table(self, column_name: str, data_type: str):
        """
        Add column to enhanced_historical_data table
        Note: In production, this should be done via Alembic migrations
        """
        try:
            with self.engine.connect() as conn:
                # SQLite syntax for adding column
                sql = f"ALTER TABLE enhanced_historical_data ADD COLUMN {column_name} {data_type}"
                conn.execute(text(sql))
                conn.commit()

        except Exception as e:
            # Column might already exist
            self.logger.warning(f"Column addition warning for {column_name}: {e}")

    def remove_indicator(self, column_name: str) -> bool:
        """
        Deactivate an indicator (set is_active = False)
        Note: Does not drop the database column for data preservation
        """
        try:
            from sqlalchemy.orm import sessionmaker
            SessionLocal = sessionmaker(bind=self.engine)

            with SessionLocal() as db:
                indicator = db.query(IndicatorTemplate).filter(
                    IndicatorTemplate.column_name == column_name
                ).first()

                if not indicator:
                    raise ValueError(f"Indicator '{column_name}' not found")

                indicator.is_active = False
                db.commit()

                self.logger.info(f"Deactivated indicator: {indicator.name} ({column_name})")
                return True

        except Exception as e:
            self.logger.error(f"Error removing indicator {column_name}: {e}")
            return False

    def get_indicator_statistics(self, symbol: str, timeframe: TimeFrame) -> Dict[str, Any]:
        """Get statistics about calculated indicators for a symbol/timeframe"""
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=self.engine)

        with SessionLocal() as db:
            # Get available indicators
            indicators = self.get_available_indicators(timeframe=timeframe)

            # Sample recent data to check calculation coverage
            recent_data = db.query(EnhancedHistoricalData).filter(
                EnhancedHistoricalData.symbol == symbol,
                EnhancedHistoricalData.timeframe == timeframe
            ).order_by(EnhancedHistoricalData.timestamp.desc()).limit(100).all()

            if not recent_data:
                return {"error": f"No data found for {symbol} {timeframe.value}"}

            stats = {
                "symbol": symbol,
                "timeframe": timeframe.value,
                "total_indicators": len(indicators),
                "recent_data_points": len(recent_data),
                "indicator_coverage": {}
            }

            # Check coverage for each indicator
            for indicator in indicators:
                column_name = indicator.column_name
                non_null_count = sum(1 for record in recent_data
                                   if getattr(record, column_name, None) is not None)
                coverage_pct = (non_null_count / len(recent_data)) * 100

                stats["indicator_coverage"][column_name] = {
                    "name": indicator.name,
                    "coverage_percent": round(coverage_pct, 1),
                    "calculated_points": non_null_count
                }

            return stats


if __name__ == "__main__":
    # Test the indicators manager
    print("Testing Indicators Manager...")

    manager = IndicatorsManager()

    # Get available indicators
    indicators = manager.get_available_indicators()
    print(f"Available indicators: {len(indicators)}")

    for indicator in indicators:
        print(f"  - {indicator.name} ({indicator.category.value})")

    print("Indicators Manager initialized successfully!")