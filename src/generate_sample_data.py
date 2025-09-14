#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Sample Data for DNA Research - Trading Project 004
Creates sample OHLCV data for all 6 timeframes to demonstrate the system
"""

import sys
sys.path.append('src')

from datetime import datetime, timedelta
from decimal import Decimal
import random
from sqlalchemy.orm import sessionmaker

from enhanced_dna_models import (
    create_enhanced_engine, Base,
    EnhancedHistoricalData, TimeFrame, TradingSession,
    IndicatorTemplate
)


def generate_ohlc_from_trend(base_price: float, volatility: float = 0.02) -> dict:
    """Generate realistic OHLC from a base price with controlled volatility"""
    # Create random but realistic price movements
    change_pct = random.uniform(-volatility, volatility)
    close = base_price * (1 + change_pct)

    # Generate high/low based on typical intraday ranges
    intraday_range = abs(change_pct) * 1.5 + random.uniform(0.005, 0.02)
    high = max(base_price, close) * (1 + intraday_range/2)
    low = min(base_price, close) * (1 - intraday_range/2)

    return {
        'open': Decimal(f'{base_price:.2f}'),
        'high': Decimal(f'{high:.2f}'),
        'low': Decimal(f'{low:.2f}'),
        'close': Decimal(f'{close:.2f}'),
        'volume': random.randint(1000, 50000)
    }


def generate_sample_data_for_symbol(session, symbol: str, start_date: datetime, days: int = 30):
    """Generate sample data for all 6 timeframes for one symbol"""
    print(f"Generating sample data for {symbol}...")

    # Starting price for the symbol
    base_prices = {'MSTR': 450.0, 'NVDA': 850.0}
    current_price = base_prices.get(symbol, 100.0)

    # Generate daily data first
    daily_data = []
    for day in range(days):
        date = start_date + timedelta(days=day)

        # Skip weekends
        if date.weekday() >= 5:
            continue

        ohlc = generate_ohlc_from_trend(current_price, 0.03)  # 3% daily volatility
        current_price = float(ohlc['close'])  # Update base for next day

        daily_record = EnhancedHistoricalData(
            symbol=symbol,
            timeframe=TimeFrame.DAILY,
            timestamp=date.replace(hour=16, minute=0, second=0),  # Market close
            open_price=ohlc['open'],
            high_price=ohlc['high'],
            low_price=ohlc['low'],
            close_price=ohlc['close'],
            volume=ohlc['volume'] * 100,  # Higher volume for daily
            trading_session=TradingSession.CLOSED,
            is_trading_hours=False,
            dna_entry_signal=random.choice([True, False, False, False]),  # 25% chance
            dna_shares=50
        )

        # Add some sample indicators
        if random.random() > 0.5:
            daily_record.bollinger_upper = ohlc['close'] * Decimal('1.05')
            daily_record.bollinger_middle = ohlc['close']
            daily_record.bollinger_lower = ohlc['close'] * Decimal('0.95')
            daily_record.volume_sma_20 = float(ohlc['volume'] * 90)  # SMA slightly lower
            daily_record.adx_14 = random.uniform(20, 60)

        daily_data.append(daily_record)

    # Add daily data to session
    for record in daily_data:
        session.add(record)

    print(f"  - Generated {len(daily_data)} daily records")

    # Generate intraday data for last 5 trading days only (to avoid too much data)
    recent_days = [d for d in daily_data[-7:] if d.timestamp.weekday() < 5][:5]

    for daily_record in recent_days:
        trading_date = daily_record.timestamp.date()
        daily_open = float(daily_record.open_price)
        daily_close = float(daily_record.close_price)

        # Generate 4-hour data (2 bars per trading day: 9:30-13:30, 13:30-17:30)
        for period in [0, 1]:
            hour_start = 9.5 + (period * 4)  # 9:30 or 13:30
            timestamp = datetime.combine(trading_date, datetime.min.time()) + timedelta(hours=hour_start)

            # Interpolate price between daily open/close
            if period == 0:
                base_price = daily_open
            else:
                base_price = (daily_open + daily_close) / 2

            ohlc = generate_ohlc_from_trend(base_price, 0.015)  # 1.5% volatility

            four_hour_record = EnhancedHistoricalData(
                symbol=symbol,
                timeframe=TimeFrame.HOUR_4,
                timestamp=timestamp,
                open_price=ohlc['open'],
                high_price=ohlc['high'],
                low_price=ohlc['low'],
                close_price=ohlc['close'],
                volume=ohlc['volume'] * 20,
                trading_session=TradingSession.TRADING,
                is_trading_hours=True,
                dna_entry_signal=random.choice([True, False, False]),  # 33% chance
                dna_shares=50
            )
            session.add(four_hour_record)

        # Generate 1-hour data (8 bars per trading day)
        for hour_offset in range(8):
            timestamp = datetime.combine(trading_date, datetime.min.time()) + timedelta(hours=9.5 + hour_offset)
            base_price = daily_open + ((daily_close - daily_open) * hour_offset / 8)

            ohlc = generate_ohlc_from_trend(base_price, 0.008)  # 0.8% volatility

            hour_record = EnhancedHistoricalData(
                symbol=symbol,
                timeframe=TimeFrame.HOUR_1,
                timestamp=timestamp,
                open_price=ohlc['open'],
                high_price=ohlc['high'],
                low_price=ohlc['low'],
                close_price=ohlc['close'],
                volume=ohlc['volume'] * 5,
                trading_session=TradingSession.TRADING,
                is_trading_hours=True,
                dna_entry_signal=random.choice([True, False, False, False]),  # 25% chance
                dna_shares=50
            )
            session.add(hour_record)

    # Generate higher frequency data only for last trading day
    if recent_days:
        last_trading_day = recent_days[-1].timestamp.date()

        # Generate 15-minute data (26 bars per trading day)
        for minute_offset in range(0, 390, 15):  # 6.5 hours * 60 / 15
            timestamp = datetime.combine(last_trading_day, datetime.min.time()) + timedelta(hours=9.5, minutes=minute_offset)
            base_price = daily_open + ((daily_close - daily_open) * minute_offset / 390)

            ohlc = generate_ohlc_from_trend(base_price, 0.004)  # 0.4% volatility

            fifteen_min_record = EnhancedHistoricalData(
                symbol=symbol,
                timeframe=TimeFrame.MIN_15,
                timestamp=timestamp,
                open_price=ohlc['open'],
                high_price=ohlc['high'],
                low_price=ohlc['low'],
                close_price=ohlc['close'],
                volume=ohlc['volume'] * 2,
                trading_session=TradingSession.TRADING,
                is_trading_hours=True,
                dna_entry_signal=random.choice([True, False, False, False, False]),  # 20% chance
                dna_shares=50
            )
            session.add(fifteen_min_record)

        # Generate 5-minute data (78 bars per trading day)
        for minute_offset in range(0, 390, 5):  # Every 5 minutes
            timestamp = datetime.combine(last_trading_day, datetime.min.time()) + timedelta(hours=9.5, minutes=minute_offset)
            base_price = daily_open + ((daily_close - daily_open) * minute_offset / 390)

            ohlc = generate_ohlc_from_trend(base_price, 0.002)  # 0.2% volatility

            five_min_record = EnhancedHistoricalData(
                symbol=symbol,
                timeframe=TimeFrame.MIN_5,
                timestamp=timestamp,
                open_price=ohlc['open'],
                high_price=ohlc['high'],
                low_price=ohlc['low'],
                close_price=ohlc['close'],
                volume=ohlc['volume'],
                trading_session=TradingSession.TRADING,
                is_trading_hours=True,
                dna_entry_signal=random.choice([True, False, False, False, False, False]),  # 16% chance
                dna_shares=50
            )
            session.add(five_min_record)

        # Generate 1-minute data (390 bars per trading day) - only for last 2 hours
        start_minute = 270  # Last 2 hours of trading (2:30 PM)
        for minute_offset in range(start_minute, 390):  # Every minute for last 2 hours
            timestamp = datetime.combine(last_trading_day, datetime.min.time()) + timedelta(hours=9.5, minutes=minute_offset)
            base_price = daily_open + ((daily_close - daily_open) * minute_offset / 390)

            ohlc = generate_ohlc_from_trend(base_price, 0.001)  # 0.1% volatility

            one_min_record = EnhancedHistoricalData(
                symbol=symbol,
                timeframe=TimeFrame.MIN_1,
                timestamp=timestamp,
                open_price=ohlc['open'],
                high_price=ohlc['high'],
                low_price=ohlc['low'],
                close_price=ohlc['close'],
                volume=random.randint(100, 2000),
                trading_session=TradingSession.TRADING,
                is_trading_hours=True,
                dna_entry_signal=random.choice([True] + [False] * 9),  # 10% chance for 1min
                dna_shares=50
            )

            # Add DNA entry price for signals
            if one_min_record.dna_entry_signal:
                one_min_record.dna_entry_price = ohlc['close']

            session.add(one_min_record)

        print(f"  - Generated intraday data for {symbol}")


def generate_all_sample_data():
    """Generate sample data for both symbols and all timeframes"""
    print("Generating sample data for DNA Research System...")

    # Create database and session
    engine = create_enhanced_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check if database has tables
        if not engine.dialect.has_table(engine.connect(), 'enhanced_historical_data'):
            print("Creating database tables...")
            Base.metadata.create_all(engine)

        # Clear existing data
        session.query(EnhancedHistoricalData).delete()
        session.commit()
        print("Cleared existing data")

        # Generate data for both symbols
        start_date = datetime(2025, 8, 15)  # Last 30 days
        symbols = ['MSTR', 'NVDA']

        for symbol in symbols:
            generate_sample_data_for_symbol(session, symbol, start_date, days=30)

        session.commit()

        # Show statistics
        print("\nSample Data Generation Complete!")
        print("=" * 50)

        for timeframe in TimeFrame:
            count = session.query(EnhancedHistoricalData).filter(
                EnhancedHistoricalData.timeframe == timeframe
            ).count()
            print(f"{timeframe.value:>10}: {count:>6} records")

        # Show DNA signals
        dna_signals = session.query(EnhancedHistoricalData).filter(
            EnhancedHistoricalData.dna_entry_signal == True
        ).count()
        print(f"\nDNA Entry Signals: {dna_signals} total")

        # Show by symbol
        print("\nBy Symbol:")
        for symbol in symbols:
            count = session.query(EnhancedHistoricalData).filter(
                EnhancedHistoricalData.symbol == symbol
            ).count()
            signals = session.query(EnhancedHistoricalData).filter(
                EnhancedHistoricalData.symbol == symbol,
                EnhancedHistoricalData.dna_entry_signal == True
            ).count()
            print(f"  {symbol}: {count} records, {signals} DNA signals")

        return True

    except Exception as e:
        print(f"Error generating sample data: {e}")
        session.rollback()
        return False

    finally:
        session.close()


if __name__ == "__main__":
    success = generate_all_sample_data()
    if success:
        print("\nSample data ready! You can now test the FastAPI server with real data.")
        print("Try: http://localhost:8000/data/MSTR/1min")
    else:
        print("\nFailed to generate sample data")