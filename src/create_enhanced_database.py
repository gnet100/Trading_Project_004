#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create Enhanced DNA Database - Trading Project 004
Initialize the enhanced database with all tables and default data
"""

from enhanced_dna_models import (
    create_enhanced_engine, Base,
    create_default_indicators,
    IndicatorTemplate, EnhancedHistoricalData
)
from sqlalchemy.orm import sessionmaker
import logging

def create_enhanced_database():
    """Create the enhanced DNA database with all tables"""
    print("Creating Enhanced DNA Database...")

    # Create engine and tables
    engine = create_enhanced_engine()
    Base.metadata.drop_all(engine)  # Clean slate
    Base.metadata.create_all(engine)

    print("Database tables created")

    # Create session and add default indicators
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Add default indicators
        default_indicators = create_default_indicators()
        for indicator in default_indicators:
            session.add(indicator)

        session.commit()
        print(f"Added {len(default_indicators)} default indicators")

        # Verify indicators were created
        count = session.query(IndicatorTemplate).count()
        print(f"Database now contains {count} indicator templates")

        # Show indicator categories
        indicators = session.query(IndicatorTemplate).all()
        categories = {}
        for ind in indicators:
            cat = ind.category.value
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        print("Indicator categories:")
        for cat, count in categories.items():
            print(f"  - {cat}: {count} indicators")

        return True

    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
        return False

    finally:
        session.close()

if __name__ == "__main__":
    success = create_enhanced_database()
    if success:
        print("\nEnhanced DNA Database created successfully!")
    else:
        print("\nFailed to create database")