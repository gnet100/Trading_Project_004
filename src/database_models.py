#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Models - Trading Project 004
SQLAlchemy models for DNA Database system

Based on DATABASE_DESIGN.md specifications:
- HistoricalData: Main OHLCV + metadata table
- Base model with timestamps and validation
- Support for data quality scoring and trading simulation
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.sql import func

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


class HistoricalData(BaseModel):
    """
    Main historical data table - DNA Database core

    Stores minute-by-minute OHLCV data with:
    - Trading simulation data (LONG strategy: SL=$2.8, TP=$3.2)
    - Data quality metrics (99.95%+ target)
    - Trading hours classification
    - Future support for indicators
    """

    __tablename__ = 'historical_data'

    # Core OHLCV Data
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    open_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)

    # Data Quality & Metadata
    data_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_valid_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trading_hours: Mapped[str] = mapped_column(String(20), nullable=False)  # warmup, trading, aftermarket
    source: Mapped[str] = mapped_column(String(50), nullable=False, default='IB')

    # Trading Simulation Fields (LONG Strategy)
    simulation_entry_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    simulation_stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)  # $2.8 below entry
    simulation_take_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)  # $3.2 above entry
    simulation_shares: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=50)
    simulation_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    simulation_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Research & Analysis Fields
    market_phase: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # opening, mid_day, closing
    volatility_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Future Indicators Support (Phase 2+)
    indicators_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string for flexibility

    # Additional Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<HistoricalData(symbol='{self.symbol}', "
            f"timestamp='{self.timestamp}', "
            f"close={self.close_price}, "
            f"quality={self.data_quality_score})>"
        )

    @property
    def price_range(self) -> Optional[Decimal]:
        """Calculate high-low price range"""
        if self.high_price and self.low_price:
            return self.high_price - self.low_price
        return None

    @property
    def is_trading_hours(self) -> bool:
        """Check if data is from main trading hours (09:45-16:00)"""
        return self.trading_hours == 'trading'

    @property
    def simulation_result(self) -> Optional[str]:
        """Get simulation result status"""
        if not self.simulation_executed:
            return None
        if self.simulation_pnl:
            return 'profit' if self.simulation_pnl > 0 else 'loss'
        return 'breakeven'

    def calculate_simulation_targets(self):
        """Calculate simulation stop loss and take profit levels"""
        if self.simulation_entry_price:
            self.simulation_stop_loss = self.simulation_entry_price - Decimal('2.8')
            self.simulation_take_profit = self.simulation_entry_price + Decimal('3.2')

    def validate_data_quality(self) -> float:
        """
        Validate data quality based on multiple factors
        Returns quality score (0.0 to 1.0)
        """
        score = 1.0

        # Check for missing OHLCV values
        if not all([self.open_price, self.high_price, self.low_price,
                   self.close_price, self.volume]):
            score -= 0.5

        # Check for logical price relationships
        if (self.high_price < self.low_price or
            self.high_price < max(self.open_price, self.close_price) or
            self.low_price > min(self.open_price, self.close_price)):
            score -= 0.3

        # Check for zero volume
        if self.volume == 0:
            score -= 0.2

        self.data_quality_score = max(0.0, score)
        self.is_valid_data = score >= 0.95  # 95% quality threshold

        return self.data_quality_score


# Event listeners for automatic field updates
@event.listens_for(HistoricalData, 'before_insert')
def calculate_simulation_on_insert(mapper, connection, target):
    """Calculate simulation targets before inserting"""
    target.calculate_simulation_targets()
    target.validate_data_quality()


@event.listens_for(HistoricalData, 'before_update')
def calculate_simulation_on_update(mapper, connection, target):
    """Calculate simulation targets before updating"""
    target.calculate_simulation_targets()
    target.validate_data_quality()


# Database utility functions
def create_database_engine(database_url: str = "sqlite:///trading_project.db"):
    """
    Create SQLAlchemy engine

    Args:
        database_url: Database connection string
                     Default: SQLite file in project root

    Returns:
        SQLAlchemy Engine instance
    """
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
        pool_recycle=300,
    )
    return engine


def create_database_session(engine):
    """
    Create database session

    Args:
        engine: SQLAlchemy Engine instance

    Returns:
        SQLAlchemy Session class
    """
    Session = sessionmaker(bind=engine)
    return Session()


def create_all_tables(engine):
    """
    Create all database tables

    Args:
        engine: SQLAlchemy Engine instance
    """
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    # Test the models
    print("Testing Database Models...")

    # Create in-memory database for testing
    engine = create_database_engine("sqlite:///:memory:")
    create_all_tables(engine)
    session = create_database_session(engine)

    # Create test record
    test_data = HistoricalData(
        symbol="AAPL",
        timestamp=datetime(2025, 9, 13, 10, 30),
        open_price=Decimal('150.00'),
        high_price=Decimal('152.50'),
        low_price=Decimal('149.75'),
        close_price=Decimal('151.25'),
        volume=1000,
        trading_hours='trading',
        simulation_entry_price=Decimal('151.00')
    )

    session.add(test_data)
    session.commit()

    # Test queries
    result = session.query(HistoricalData).first()
    print(f"Test record created: {result}")
    print(f"   Quality Score: {result.data_quality_score}")
    print(f"   Simulation SL: ${result.simulation_stop_loss}")
    print(f"   Simulation TP: ${result.simulation_take_profit}")

    session.close()
    print("Database Models test completed successfully!")