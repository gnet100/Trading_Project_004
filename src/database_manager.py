#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Manager - Trading Project 004
Centralized database operations and connection management

Features:
- Connection pooling and management
- Bulk insert operations for IB data
- Query builder for research queries
- Data validation and quality scoring
- Transaction management
"""

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

from sqlalchemy import and_, create_engine, desc, func, or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

# Add src to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_models import Base, HistoricalData


class DatabaseManager:
    """
    Central database manager for Trading Project 004

    Handles:
    - Connection management with pooling
    - Bulk data operations
    - Query building for research
    - Data quality validation
    - Transaction management
    """

    def __init__(self, database_url: str = None):
        """
        Initialize Database Manager

        Args:
            database_url: Database connection string
                         Defaults to SQLite in project root
        """
        if database_url is None:
            # Default to SQLite file in project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            database_url = f"sqlite:///{os.path.join(project_root, 'trading_project.db')}"

        self.database_url = database_url
        self.engine = self._create_engine()
        self.Session = sessionmaker(bind=self.engine)

        # Initialize database tables if they don't exist
        self.create_tables()

    def _create_engine(self):
        """Create SQLAlchemy engine with proper configuration"""
        if "sqlite" in self.database_url:
            # SQLite specific configuration
            engine = create_engine(
                self.database_url,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,
                connect_args={"check_same_thread": False},
            )
        else:
            # PostgreSQL configuration (for future use)
            engine = create_engine(
                self.database_url,
                echo=False,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=300,
            )
        return engine

    def create_tables(self):
        """Create all database tables"""
        try:
            Base.metadata.create_all(self.engine)
            print("Database tables created successfully")
        except SQLAlchemyError as e:
            print(f"Error creating tables: {e}")
            raise

    @contextmanager
    def get_session(self):
        """
        Context manager for database sessions
        Automatically handles commit/rollback
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def bulk_insert_historical_data(
        self, data_records: List[Dict], batch_size: int = 1000
    ) -> Dict[str, Union[int, str]]:
        """
        Bulk insert historical data records

        Args:
            data_records: List of dictionaries with OHLCV data
            batch_size: Number of records per batch

        Returns:
            Dict with success count and any errors
        """
        total_inserted = 0
        errors = []

        try:
            with self.get_session() as session:
                for i in range(0, len(data_records), batch_size):
                    batch = data_records[i:i + batch_size]

                    # Convert dict records to HistoricalData objects
                    historical_objects = []
                    for record in batch:
                        try:
                            hist_data = HistoricalData(
                                symbol=record.get('symbol'),
                                timestamp=record.get('timestamp'),
                                open_price=Decimal(str(record.get('open', 0))),
                                high_price=Decimal(str(record.get('high', 0))),
                                low_price=Decimal(str(record.get('low', 0))),
                                close_price=Decimal(str(record.get('close', 0))),
                                volume=int(record.get('volume', 0)),
                                trading_hours=record.get('trading_hours', 'trading'),
                                source=record.get('source', 'IB')
                            )

                            # Set simulation entry price if provided
                            if 'simulation_entry_price' in record:
                                hist_data.simulation_entry_price = Decimal(
                                    str(record['simulation_entry_price'])
                                )

                            historical_objects.append(hist_data)

                        except (ValueError, TypeError) as e:
                            errors.append(f"Invalid record {record}: {e}")
                            continue

                    # Bulk insert batch
                    if historical_objects:
                        session.bulk_save_objects(historical_objects)
                        total_inserted += len(historical_objects)

                    print(f"Inserted batch {i//batch_size + 1}: {len(historical_objects)} records")

        except SQLAlchemyError as e:
            errors.append(f"Database error: {e}")

        return {
            "success": total_inserted,
            "errors": errors,
            "total_records": len(data_records)
        }

    def get_historical_data(
        self,
        symbol: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        trading_hours_only: bool = False,
        min_quality_score: float = 0.95,
        limit: int = None
    ) -> List[HistoricalData]:
        """
        Query historical data with various filters

        Args:
            symbol: Stock symbol (optional)
            start_date: Start date filter
            end_date: End date filter
            trading_hours_only: Only return trading hours data
            min_quality_score: Minimum data quality score
            limit: Maximum number of records

        Returns:
            List of HistoricalData objects
        """
        with self.get_session() as session:
            query = session.query(HistoricalData)

            # Apply filters
            if symbol:
                query = query.filter(HistoricalData.symbol == symbol)

            if start_date:
                query = query.filter(HistoricalData.timestamp >= start_date)

            if end_date:
                query = query.filter(HistoricalData.timestamp <= end_date)

            if trading_hours_only:
                query = query.filter(HistoricalData.trading_hours == 'trading')

            if min_quality_score:
                query = query.filter(HistoricalData.data_quality_score >= min_quality_score)

            # Order by timestamp
            query = query.order_by(HistoricalData.timestamp)

            if limit:
                query = query.limit(limit)

            return query.all()

    def get_data_quality_summary(self) -> Dict[str, Union[int, float]]:
        """
        Get summary of data quality across all records

        Returns:
            Dictionary with quality statistics
        """
        with self.get_session() as session:
            # Basic counts
            total_records = session.query(func.count(HistoricalData.id)).scalar()

            # Quality statistics
            avg_quality = session.query(
                func.avg(HistoricalData.data_quality_score)
            ).scalar() or 0

            high_quality_count = session.query(func.count(HistoricalData.id)).filter(
                HistoricalData.data_quality_score >= 0.95
            ).scalar()

            valid_data_count = session.query(func.count(HistoricalData.id)).filter(
                HistoricalData.is_valid_data == True
            ).scalar()

            # Trading hours breakdown
            trading_hours_count = session.query(func.count(HistoricalData.id)).filter(
                HistoricalData.trading_hours == 'trading'
            ).scalar()

            return {
                "total_records": total_records,
                "average_quality_score": round(float(avg_quality), 4),
                "high_quality_records": high_quality_count,
                "high_quality_percentage": round((high_quality_count / total_records * 100), 2) if total_records > 0 else 0,
                "valid_data_records": valid_data_count,
                "trading_hours_records": trading_hours_count,
                "trading_hours_percentage": round((trading_hours_count / total_records * 100), 2) if total_records > 0 else 0
            }

    def get_symbols_list(self) -> List[str]:
        """Get list of all symbols in database"""
        with self.get_session() as session:
            symbols = session.query(HistoricalData.symbol).distinct().all()
            return [symbol[0] for symbol in symbols]

    def get_date_range(self, symbol: str = None) -> Optional[Tuple[datetime, datetime]]:
        """
        Get date range for symbol or entire database

        Args:
            symbol: Optional symbol filter

        Returns:
            Tuple of (earliest_date, latest_date) or None
        """
        with self.get_session() as session:
            query = session.query(
                func.min(HistoricalData.timestamp),
                func.max(HistoricalData.timestamp)
            )

            if symbol:
                query = query.filter(HistoricalData.symbol == symbol)

            result = query.first()
            if result and result[0] and result[1]:
                return (result[0], result[1])
            return None

    def cleanup_invalid_data(self) -> int:
        """
        Remove records with very low quality scores

        Returns:
            Number of records deleted
        """
        with self.get_session() as session:
            deleted_count = session.query(HistoricalData).filter(
                HistoricalData.data_quality_score < 0.5
            ).delete()

            return deleted_count

    def execute_custom_query(self, query_string: str) -> List:
        """
        Execute custom SQL query

        Args:
            query_string: Raw SQL query

        Returns:
            Query results
        """
        with self.get_session() as session:
            result = session.execute(text(query_string))
            return result.fetchall()

    def get_database_info(self) -> Dict[str, Union[str, int]]:
        """Get basic database information"""
        with self.get_session() as session:
            # Get table names
            if "sqlite" in self.database_url:
                tables_result = session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
                table_names = [row[0] for row in tables_result]
            else:
                # PostgreSQL version for future
                table_names = ["historical_data"]  # Simplified for now

            # Get record count
            total_records = session.query(func.count(HistoricalData.id)).scalar()

            return {
                "database_url": self.database_url.split('/')[-1] if 'sqlite' in self.database_url else self.database_url,
                "tables": table_names,
                "total_records": total_records,
                "engine_info": str(self.engine.url)
            }


if __name__ == "__main__":
    # Test the Database Manager
    print("Testing Database Manager...")

    # Create manager instance
    db_manager = DatabaseManager()

    # Test database info
    info = db_manager.get_database_info()
    print(f"Database: {info['database_url']}")
    print(f"Tables: {info['tables']}")
    print(f"Total records: {info['total_records']}")

    # Test data quality summary
    quality_summary = db_manager.get_data_quality_summary()
    print(f"Data quality summary: {quality_summary}")

    # Test inserting sample data
    sample_data = [
        {
            'symbol': 'AAPL',
            'timestamp': datetime(2025, 9, 13, 10, 0),
            'open': 150.00,
            'high': 151.50,
            'low': 149.75,
            'close': 151.00,
            'volume': 1000,
            'trading_hours': 'trading',
            'simulation_entry_price': 150.50
        },
        {
            'symbol': 'AAPL',
            'timestamp': datetime(2025, 9, 13, 10, 1),
            'open': 151.00,
            'high': 152.00,
            'low': 150.50,
            'close': 151.75,
            'volume': 1200,
            'trading_hours': 'trading'
        }
    ]

    # Insert sample data
    result = db_manager.bulk_insert_historical_data(sample_data)
    print(f"Bulk insert result: {result}")

    # Test querying data
    data = db_manager.get_historical_data(symbol='AAPL', limit=5)
    print(f"Retrieved {len(data)} records")
    for record in data:
        print(f"  {record.timestamp}: {record.symbol} ${record.close_price}")

    print("Database Manager test completed successfully!")