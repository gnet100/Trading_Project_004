#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DNA Research Engine - Trading Project 004
Advanced simulation engine for DNA trading research

Key Features:
- Minute-by-minute trade simulation
- LONG strategy with fixed SL/TP (-$2.8 / +$3.2)
- Multi-timeframe signal generation
- Performance analytics and statistics
- Real-time trade execution simulation
"""

import sys
sys.path.append('src')

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json

from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_, or_, func, desc

from enhanced_dna_models import (
    create_enhanced_engine, EnhancedHistoricalData,
    TimeFrame, TradingSession
)


class TradeResult(Enum):
    """DNA Trade Results"""
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    ACTIVE = "ACTIVE"  # Trade still open


@dataclass
class DNATrade:
    """DNA Trade Simulation Record"""
    entry_timestamp: datetime
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    shares: int = 50
    exit_timestamp: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    exit_reason: Optional[str] = None
    pnl: Optional[Decimal] = None
    result: TradeResult = TradeResult.ACTIVE
    bars_held: int = 0
    max_profit: Decimal = Decimal('0')
    max_loss: Decimal = Decimal('0')


@dataclass
class DNAPerformance:
    """DNA Performance Statistics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    total_pnl: Decimal = Decimal('0')
    win_rate: float = 0.0
    avg_win: Decimal = Decimal('0')
    avg_loss: Decimal = Decimal('0')
    largest_win: Decimal = Decimal('0')
    largest_loss: Decimal = Decimal('0')
    avg_bars_held: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0


class DNAResearchEngine:
    """
    DNA Research Engine for Trading Simulation

    Simulates LONG-only strategy with fixed risk management:
    - Entry: Based on signal detection
    - Stop Loss: -$2.8 per trade
    - Take Profit: +$3.2 per trade
    - Position Size: 50 shares
    """

    def __init__(self, database_url: str = "sqlite:///enhanced_trading_project.db"):
        self.engine = create_enhanced_engine(database_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()

    def generate_entry_signals(self, symbol: str, timeframe: TimeFrame,
                              strategy: str = "bollinger_breakout") -> List[Dict]:
        """
        Generate DNA entry signals based on strategy

        Args:
            symbol: Stock symbol
            timeframe: Timeframe to analyze
            strategy: Signal strategy type

        Returns:
            List of signal timestamps with entry prices
        """
        print(f"Generating DNA signals for {symbol} on {timeframe.value}...")

        # Get historical data
        data = self.session.query(EnhancedHistoricalData).filter(
            and_(
                EnhancedHistoricalData.symbol == symbol,
                EnhancedHistoricalData.timeframe == timeframe,
                EnhancedHistoricalData.is_trading_hours == True
            )
        ).order_by(EnhancedHistoricalData.timestamp).all()

        signals = []

        if strategy == "bollinger_breakout":
            for i, record in enumerate(data):
                if i < 20:  # Need historical data for Bollinger calculation
                    continue

                # Simple Bollinger Bands breakout strategy
                if (record.bollinger_upper and record.bollinger_lower and
                    record.close_price > record.bollinger_upper):

                    # Generate entry signal
                    signal = {
                        'timestamp': record.timestamp,
                        'entry_price': record.close_price,
                        'signal_strength': 'HIGH',
                        'reason': 'Bollinger Upper Band Breakout'
                    }
                    signals.append(signal)

        elif strategy == "volume_breakout":
            # Calculate average volume for last 20 periods
            for i, record in enumerate(data):
                if i < 20:
                    continue

                recent_volumes = [d.volume for d in data[i-20:i]]
                avg_volume = sum(recent_volumes) / len(recent_volumes)

                # High volume + price increase
                if (record.volume > avg_volume * 2 and
                    record.close_price > record.open_price):

                    signal = {
                        'timestamp': record.timestamp,
                        'entry_price': record.close_price,
                        'signal_strength': 'MEDIUM',
                        'reason': 'Volume Breakout with Price Increase'
                    }
                    signals.append(signal)

        print(f"Generated {len(signals)} DNA entry signals")
        return signals

    def simulate_dna_trades(self, symbol: str, timeframe: TimeFrame,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> List[DNATrade]:
        """
        Simulate DNA trades for given symbol and timeframe

        Args:
            symbol: Stock symbol to simulate
            timeframe: Timeframe for simulation
            start_date: Start date for simulation
            end_date: End date for simulation

        Returns:
            List of completed DNA trades
        """
        print(f"Simulating DNA trades for {symbol} on {timeframe.value}...")

        # Get all data with entry signals
        query = self.session.query(EnhancedHistoricalData).filter(
            and_(
                EnhancedHistoricalData.symbol == symbol,
                EnhancedHistoricalData.timeframe == timeframe,
                EnhancedHistoricalData.dna_entry_signal == True
            )
        )

        if start_date:
            query = query.filter(EnhancedHistoricalData.timestamp >= start_date)
        if end_date:
            query = query.filter(EnhancedHistoricalData.timestamp <= end_date)

        entry_signals = query.order_by(EnhancedHistoricalData.timestamp).all()

        trades = []
        active_trade = None

        # Get all price data for exit simulation
        price_query = self.session.query(EnhancedHistoricalData).filter(
            and_(
                EnhancedHistoricalData.symbol == symbol,
                EnhancedHistoricalData.timeframe == timeframe
            )
        )

        if start_date:
            price_query = price_query.filter(EnhancedHistoricalData.timestamp >= start_date)
        if end_date:
            price_query = price_query.filter(EnhancedHistoricalData.timestamp <= end_date)

        all_price_data = price_query.order_by(EnhancedHistoricalData.timestamp).all()

        for entry_signal in entry_signals:
            # Skip if we have an active trade
            if active_trade and active_trade.result == TradeResult.ACTIVE:
                continue

            # Create new DNA trade
            entry_price = entry_signal.dna_entry_price or entry_signal.close_price

            trade = DNATrade(
                entry_timestamp=entry_signal.timestamp,
                entry_price=entry_price,
                stop_loss=entry_price - Decimal('2.8'),
                take_profit=entry_price + Decimal('3.2'),
                shares=50
            )

            # Find exit point by looking at subsequent price data
            entry_time = entry_signal.timestamp
            exit_found = False

            for price_bar in all_price_data:
                if price_bar.timestamp <= entry_time:
                    continue

                trade.bars_held += 1

                # Check for stop loss hit (using low price)
                if price_bar.low_price <= trade.stop_loss:
                    trade.exit_timestamp = price_bar.timestamp
                    trade.exit_price = trade.stop_loss
                    trade.exit_reason = "Stop Loss Hit"
                    trade.pnl = (trade.exit_price - trade.entry_price) * trade.shares
                    trade.result = TradeResult.LOSS
                    exit_found = True
                    break

                # Check for take profit hit (using high price)
                if price_bar.high_price >= trade.take_profit:
                    trade.exit_timestamp = price_bar.timestamp
                    trade.exit_price = trade.take_profit
                    trade.exit_reason = "Take Profit Hit"
                    trade.pnl = (trade.exit_price - trade.entry_price) * trade.shares
                    trade.result = TradeResult.WIN
                    exit_found = True
                    break

                # Track max profit/loss during trade
                current_profit = (price_bar.close_price - trade.entry_price) * trade.shares
                if current_profit > trade.max_profit:
                    trade.max_profit = current_profit
                if current_profit < trade.max_loss:
                    trade.max_loss = current_profit

                # Maximum holding period (prevent endless trades)
                if trade.bars_held > 100:  # Adjust based on timeframe
                    trade.exit_timestamp = price_bar.timestamp
                    trade.exit_price = price_bar.close_price
                    trade.exit_reason = "Max Holding Period"
                    trade.pnl = (trade.exit_price - trade.entry_price) * trade.shares

                    if trade.pnl > 0:
                        trade.result = TradeResult.WIN
                    elif trade.pnl < 0:
                        trade.result = TradeResult.LOSS
                    else:
                        trade.result = TradeResult.BREAKEVEN

                    exit_found = True
                    break

            # If no exit found, mark as active
            if not exit_found:
                trade.result = TradeResult.ACTIVE

            trades.append(trade)
            active_trade = trade

        print(f"Simulated {len(trades)} DNA trades")
        return trades

    def calculate_performance(self, trades: List[DNATrade]) -> DNAPerformance:
        """Calculate comprehensive performance statistics"""
        if not trades:
            return DNAPerformance()

        completed_trades = [t for t in trades if t.result != TradeResult.ACTIVE]

        if not completed_trades:
            return DNAPerformance()

        perf = DNAPerformance()
        perf.total_trades = len(completed_trades)

        winning_trades = [t for t in completed_trades if t.result == TradeResult.WIN]
        losing_trades = [t for t in completed_trades if t.result == TradeResult.LOSS]
        breakeven_trades = [t for t in completed_trades if t.result == TradeResult.BREAKEVEN]

        perf.winning_trades = len(winning_trades)
        perf.losing_trades = len(losing_trades)
        perf.breakeven_trades = len(breakeven_trades)

        # Calculate PnL statistics
        if completed_trades:
            perf.total_pnl = sum(t.pnl for t in completed_trades if t.pnl)
            perf.win_rate = perf.winning_trades / perf.total_trades * 100

            if winning_trades:
                perf.avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades)
                perf.largest_win = max(t.pnl for t in winning_trades)

            if losing_trades:
                perf.avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades)
                perf.largest_loss = min(t.pnl for t in losing_trades)

            # Profit factor
            gross_profit = sum(t.pnl for t in winning_trades if t.pnl > 0) or Decimal('1')
            gross_loss = abs(sum(t.pnl for t in losing_trades if t.pnl < 0)) or Decimal('1')
            perf.profit_factor = float(gross_profit / gross_loss)

            # Average bars held
            bars_held = [t.bars_held for t in completed_trades if t.bars_held > 0]
            if bars_held:
                perf.avg_bars_held = sum(bars_held) / len(bars_held)

        return perf

    def update_database_with_trades(self, symbol: str, timeframe: TimeFrame, trades: List[DNATrade]):
        """Update database records with DNA trade results"""
        print(f"Updating database with {len(trades)} DNA trades...")

        updated_count = 0
        for trade in trades:
            # Find the corresponding database record
            record = self.session.query(EnhancedHistoricalData).filter(
                and_(
                    EnhancedHistoricalData.symbol == symbol,
                    EnhancedHistoricalData.timeframe == timeframe,
                    EnhancedHistoricalData.timestamp == trade.entry_timestamp,
                    EnhancedHistoricalData.dna_entry_signal == True
                )
            ).first()

            if record:
                # Update DNA trade fields
                record.dna_entry_price = trade.entry_price
                record.dna_stop_loss = trade.stop_loss
                record.dna_take_profit = trade.take_profit
                record.dna_shares = trade.shares

                if trade.result != TradeResult.ACTIVE:
                    record.dna_exit_price = trade.exit_price
                    record.dna_pnl = trade.pnl
                    record.dna_trade_result = trade.result.value
                    record.dna_bars_held = trade.bars_held

                updated_count += 1

        try:
            self.session.commit()
            print(f"Successfully updated {updated_count} database records")
        except Exception as e:
            print(f"Error updating database: {e}")
            self.session.rollback()

    def run_comprehensive_dna_research(self, symbol: str, timeframe: TimeFrame) -> Dict:
        """Run complete DNA research analysis"""
        print(f"Running comprehensive DNA research for {symbol} on {timeframe.value}")
        print("=" * 60)

        # 1. Simulate trades
        trades = self.simulate_dna_trades(symbol, timeframe)

        # 2. Calculate performance
        performance = self.calculate_performance(trades)

        # 3. Update database
        self.update_database_with_trades(symbol, timeframe, trades)

        # 4. Generate report
        report = {
            'symbol': symbol,
            'timeframe': timeframe.value,
            'analysis_date': datetime.now().isoformat(),
            'total_signals': len(trades),
            'performance': {
                'total_trades': performance.total_trades,
                'winning_trades': performance.winning_trades,
                'losing_trades': performance.losing_trades,
                'win_rate': f"{performance.win_rate:.1f}%",
                'total_pnl': f"${float(performance.total_pnl):.2f}",
                'avg_win': f"${float(performance.avg_win):.2f}",
                'avg_loss': f"${float(performance.avg_loss):.2f}",
                'largest_win': f"${float(performance.largest_win):.2f}",
                'largest_loss': f"${float(performance.largest_loss):.2f}",
                'profit_factor': f"{performance.profit_factor:.2f}",
                'avg_bars_held': f"{performance.avg_bars_held:.1f}"
            },
            'sample_trades': []
        }

        # Add sample trades to report
        completed_trades = [t for t in trades if t.result != TradeResult.ACTIVE]
        sample_size = min(5, len(completed_trades))

        for trade in completed_trades[:sample_size]:
            sample_trade = {
                'entry_time': trade.entry_timestamp.isoformat(),
                'entry_price': f"${float(trade.entry_price):.2f}",
                'exit_time': trade.exit_timestamp.isoformat() if trade.exit_timestamp else None,
                'exit_price': f"${float(trade.exit_price):.2f}" if trade.exit_price else None,
                'pnl': f"${float(trade.pnl):.2f}" if trade.pnl else None,
                'result': trade.result.value,
                'bars_held': trade.bars_held,
                'exit_reason': trade.exit_reason
            }
            report['sample_trades'].append(sample_trade)

        return report


def run_dna_analysis():
    """Run DNA analysis for all available symbols and timeframes"""
    print("DNA Research Engine - Comprehensive Analysis")
    print("=" * 50)

    engine = DNAResearchEngine()

    # Available symbols and timeframes
    symbols = ['MSTR', 'NVDA']
    timeframes = [TimeFrame.MIN_1, TimeFrame.MIN_5, TimeFrame.MIN_15,
                  TimeFrame.HOUR_1, TimeFrame.HOUR_4, TimeFrame.DAILY]

    all_reports = []

    for symbol in symbols:
        for timeframe in timeframes:
            try:
                report = engine.run_comprehensive_dna_research(symbol, timeframe)
                all_reports.append(report)

                # Print summary
                perf = report['performance']
                print(f"\n{symbol} - {timeframe.value}:")
                print(f"  Trades: {perf['total_trades']} | Win Rate: {perf['win_rate']} | PnL: {perf['total_pnl']}")

            except Exception as e:
                print(f"Error analyzing {symbol} on {timeframe.value}: {e}")

    print("\nDNA Research Analysis Complete!")
    print(f"Generated {len(all_reports)} comprehensive reports")

    return all_reports


if __name__ == "__main__":
    # Run comprehensive DNA analysis
    reports = run_dna_analysis()

    # Save reports to file
    with open('dna_research_reports.json', 'w', encoding='utf-8') as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)

    print("\nReports saved to: dna_research_reports.json")
    print("FastAPI server endpoints updated with DNA analysis results")