#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced DNA Database Models - Trading Project 004
Extended models for 6 timeframes + dynamic indicators support

Key Features:
- 6 timeframes: 1min, 5min, 15min, 1h, 4h, daily
- Dynamic indicator columns (add/remove via migrations)
- Enhanced DNA research framework
- Support for 2 symbols × 2 years data
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, Numeric, String, Text,
    create_engine, event, Enum as SQLEnum, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
import json


class TimeFrame(Enum):
    """Supported timeframes for DNA analysis"""
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    HOUR_1 = "1hour"
    HOUR_4 = "4hour"
    DAILY = "daily"


class TradingSession(Enum):
    """Trading session phases for DNA research"""
    WARMUP = "warmup"        # 09:30-09:45
    TRADING = "trading"      # 09:45-16:00
    AFTER_MARKET = "after_market"  # 16:00-20:00
    CLOSED = "closed"


class IndicatorCategory(Enum):
    """7 categories of indicators for research"""
    PRICE = "price"
    VOLUME = "volume"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    TREND = "trend"
    PRICE_VOLUME = "price_volume"
    CORRELATION = "correlation"


# Base class for all models
class Base(DeclarativeBase):
    pass


class BaseModel(Base):
    """Base model with common fields for all tables"""
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """Convert model instance to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class EnhancedHistoricalData(BaseModel):
    """
    Enhanced DNA Database - Core table for all timeframes

    Features:
    - Support for 6 timeframes in single table
    - Dynamic indicator columns (via migrations)
    - DNA research simulation per minute
    - 2 symbols × 2 years capacity
    """

    __tablename__ = 'enhanced_historical_data'

    # Core identifiers
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timeframe: Mapped[TimeFrame] = mapped_column(SQLEnum(TimeFrame), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # OHLCV Data
    open_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Data Quality & Session
    data_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    trading_session: Mapped[TradingSession] = mapped_column(SQLEnum(TradingSession), nullable=False)
    is_trading_hours: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)

    # DNA Research - Trade Simulation (LONG only)
    dna_entry_signal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dna_entry_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    dna_stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)  # -$2.8
    dna_take_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)  # +$3.2
    dna_exit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    dna_shares: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    dna_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    dna_trade_result: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # WIN/LOSS/BREAKEVEN
    dna_bars_held: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # === DYNAMIC INDICATOR COLUMNS (Phase 1) ===
    # Price Indicators
    bollinger_upper: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    bollinger_middle: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    bollinger_lower: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    bollinger_width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Volume Indicators
    volume_sma_20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Current vs Average

    # Trend/Momentum Indicators
    adx_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    adx_plus_di: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    adx_minus_di: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    source: Mapped[str] = mapped_column(String(50), nullable=False, default='IB')
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Future expansion placeholder (JSON for flexibility)
    custom_indicators: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Composite indexes for performance
    __table_args__ = (
        Index('idx_symbol_timeframe_timestamp', 'symbol', 'timeframe', 'timestamp'),
        Index('idx_trading_hours_quality', 'is_trading_hours', 'data_quality_score'),
        Index('idx_dna_signals', 'dna_entry_signal', 'dna_trade_result'),
        Index('idx_research_query', 'symbol', 'timeframe', 'trading_session'),
    )

    def __repr__(self):
        return (
            f"<EnhancedHistoricalData("
            f"symbol='{self.symbol}', "
            f"timeframe='{self.timeframe.value}', "
            f"timestamp='{self.timestamp}', "
            f"close={self.close_price})>"
        )

    @hybrid_property
    def price_range(self) -> Optional[Decimal]:
        """High-Low price range"""
        if self.high_price and self.low_price:
            return self.high_price - self.low_price
        return None

    @hybrid_property
    def is_main_session(self) -> bool:
        """Check if main trading session (09:45-16:00)"""
        return self.trading_session == TradingSession.TRADING

    @property
    def custom_indicators_dict(self) -> Dict[str, Any]:
        """Parse custom indicators JSON"""
        if self.custom_indicators:
            try:
                return json.loads(self.custom_indicators)
            except json.JSONDecodeError:
                return {}
        return {}

    @custom_indicators_dict.setter
    def custom_indicators_dict(self, value: Dict[str, Any]):
        """Set custom indicators as JSON"""
        self.custom_indicators = json.dumps(value) if value else None

    def calculate_dna_targets(self):
        """Calculate DNA trading simulation targets"""
        if self.dna_entry_price:
            self.dna_stop_loss = self.dna_entry_price - Decimal('2.8')
            self.dna_take_profit = self.dna_entry_price + Decimal('3.2')

    def execute_dna_trade(self, exit_price: Decimal, exit_reason: str):
        """Execute DNA trade simulation"""
        if self.dna_entry_price and self.dna_shares:
            self.dna_exit_price = exit_price
            pnl = (exit_price - self.dna_entry_price) * self.dna_shares
            self.dna_pnl = pnl

            if pnl > 0:
                self.dna_trade_result = "WIN"
            elif pnl < 0:
                self.dna_trade_result = "LOSS"
            else:
                self.dna_trade_result = "BREAKEVEN"

    def validate_data_quality(self) -> float:
        """
        Enhanced data quality validation
        Returns: Quality score (0.0 to 100.0)
        """
        score = 100.0

        # Basic OHLCV validation
        if not all([self.open_price, self.high_price, self.low_price, self.close_price]):
            score -= 50.0

        # Price logic validation
        if (self.high_price < self.low_price or
            self.high_price < max(self.open_price, self.close_price) or
            self.low_price > min(self.open_price, self.close_price)):
            score -= 30.0

        # Volume validation (only for 1min data)
        if self.timeframe == TimeFrame.MIN_1 and self.volume == 0:
            score -= 10.0

        # Extreme price movements (>20% in 1 minute)
        if self.timeframe == TimeFrame.MIN_1:
            price_change = abs((self.close_price - self.open_price) / self.open_price)
            if price_change > 0.2:  # 20%
                score -= 5.0

        self.data_quality_score = max(0.0, score)
        return self.data_quality_score


class IndicatorTemplate(BaseModel):
    """
    Template for managing dynamic indicators
    Tracks which indicators are available for each timeframe
    """
    __tablename__ = 'indicator_templates'

    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    category: Mapped[IndicatorCategory] = mapped_column(SQLEnum(IndicatorCategory), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    column_name: Mapped[str] = mapped_column(String(50), nullable=False)  # Database column
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # DECIMAL, FLOAT, etc.
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON config
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Which timeframes support this indicator
    supports_1min: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_5min: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_15min: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_1hour: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_4hour: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_daily: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<IndicatorTemplate(name='{self.name}', category='{self.category.value}')>"

    @property
    def supported_timeframes(self) -> List[TimeFrame]:
        """Get list of supported timeframes"""
        timeframes = []
        if self.supports_1min: timeframes.append(TimeFrame.MIN_1)
        if self.supports_5min: timeframes.append(TimeFrame.MIN_5)
        if self.supports_15min: timeframes.append(TimeFrame.MIN_15)
        if self.supports_1hour: timeframes.append(TimeFrame.HOUR_1)
        if self.supports_4hour: timeframes.append(TimeFrame.HOUR_4)
        if self.supports_daily: timeframes.append(TimeFrame.DAILY)
        return timeframes


# Event listeners
@event.listens_for(EnhancedHistoricalData, 'before_insert')
def calculate_dna_on_insert(mapper, connection, target):
    """Calculate DNA targets and validate quality before insert"""
    if target.dna_entry_signal and target.dna_entry_price:
        target.calculate_dna_targets()
    target.validate_data_quality()


@event.listens_for(EnhancedHistoricalData, 'before_update')
def calculate_dna_on_update(mapper, connection, target):
    """Calculate DNA targets and validate quality before update"""
    if target.dna_entry_signal and target.dna_entry_price:
        target.calculate_dna_targets()
    target.validate_data_quality()


# Database utility functions
def create_enhanced_engine(database_url: str = "sqlite:///enhanced_trading_project.db"):
    """
    Create SQLAlchemy engine for enhanced DNA database

    Args:
        database_url: Database connection string
                     Default: Enhanced SQLite file

    Returns:
        SQLAlchemy Engine instance
    """
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
        pool_recycle=3600,  # 1 hour for longer research sessions
        connect_args={"timeout": 30} if "sqlite" in database_url else {}
    )
    return engine


def create_default_indicators():
    """
    Create default indicator templates for Phase 1
    Returns list of IndicatorTemplate objects
    """
    indicators = [
        # Bollinger Bands
        IndicatorTemplate(
            name="Bollinger Bands Upper",
            category=IndicatorCategory.VOLATILITY,
            description="Bollinger Bands upper line (20-period, 2 std dev)",
            column_name="bollinger_upper",
            data_type="DECIMAL(12,6)",
            parameters='{"period": 20, "std_dev": 2}'
        ),
        IndicatorTemplate(
            name="Bollinger Bands Middle",
            category=IndicatorCategory.PRICE,
            description="Bollinger Bands middle line (SMA 20)",
            column_name="bollinger_middle",
            data_type="DECIMAL(12,6)",
            parameters='{"period": 20}'
        ),
        IndicatorTemplate(
            name="Bollinger Bands Lower",
            category=IndicatorCategory.VOLATILITY,
            description="Bollinger Bands lower line (20-period, 2 std dev)",
            column_name="bollinger_lower",
            data_type="DECIMAL(12,6)",
            parameters='{"period": 20, "std_dev": 2}'
        ),

        # Volume
        IndicatorTemplate(
            name="Volume SMA 20",
            category=IndicatorCategory.VOLUME,
            description="20-period Simple Moving Average of Volume",
            column_name="volume_sma_20",
            data_type="FLOAT",
            parameters='{"period": 20}'
        ),

        # ADX
        IndicatorTemplate(
            name="ADX 14",
            category=IndicatorCategory.TREND,
            description="Average Directional Index (14-period)",
            column_name="adx_14",
            data_type="FLOAT",
            parameters='{"period": 14}',
            supports_1min=False,  # ADX not meaningful for 1min
            supports_5min=True
        ),
    ]
    return indicators


if __name__ == "__main__":
    # Test enhanced models
    print("Testing Enhanced DNA Database Models...")

    # Create test database
    engine = create_enhanced_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Create indicator templates
    for template in create_default_indicators():
        session.add(template)

    # Create test data
    test_data = EnhancedHistoricalData(
        symbol="MSTR",
        timeframe=TimeFrame.MIN_1,
        timestamp=datetime(2025, 9, 14, 10, 30),
        open_price=Decimal('150.00'),
        high_price=Decimal('152.50'),
        low_price=Decimal('149.75'),
        close_price=Decimal('151.25'),
        volume=1000,
        trading_session=TradingSession.TRADING,
        is_trading_hours=True,
        dna_entry_signal=True,
        dna_entry_price=Decimal('150.50'),
        bollinger_upper=Decimal('155.00'),
        bollinger_middle=Decimal('150.00'),
        bollinger_lower=Decimal('145.00')
    )

    session.add(test_data)
    session.commit()

    # Test queries
    result = session.query(EnhancedHistoricalData).first()
    print(f"Test record created: {result}")
    print(f"   Quality Score: {result.data_quality_score}")
    print(f"   DNA Stop Loss: ${result.dna_stop_loss}")
    print(f"   DNA Take Profit: ${result.dna_take_profit}")
    print(f"   Bollinger Upper: ${result.bollinger_upper}")

    # Test indicator templates
    templates = session.query(IndicatorTemplate).all()
    print(f"Created {len(templates)} indicator templates")

    session.close()
    print("Enhanced DNA Database Models test completed successfully!")