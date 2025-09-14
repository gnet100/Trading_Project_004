#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DNA Research API - Trading Project 004
FastAPI server for local DNA database research and analysis

Features:
- localhost:8000 server (single-user, no auth)
- 5 core research endpoints
- Integration with enhanced DNA database
- Support for 6 timeframes and dynamic indicators
- Built for statistical analysis workflow
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal
import json

from fastapi import FastAPI, HTTPException, Depends, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_, or_, func

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_dna_models import (
    EnhancedHistoricalData, IndicatorTemplate,
    TimeFrame, TradingSession, IndicatorCategory,
    create_enhanced_engine, Base
)

# Initialize FastAPI app
app = FastAPI(
    title="DNA Research API",
    description="Trading Project 004 - DNA Database Research Interface",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI at localhost:8000/docs
    redoc_url="/redoc"  # ReDoc at localhost:8000/redoc
)

# CORS middleware for local dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = "sqlite:///enhanced_trading_project.db"
engine = create_enhanced_engine(DATABASE_URL)

# Create tables if they don't exist
Base.metadata.create_all(engine)

def get_db():
    """Database dependency"""
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# === PYDANTIC MODELS FOR API ===

from typing import Annotated
from pydantic import Field, ValidationError

# Simple string validation for timeframes
def validate_timeframe(v: str) -> str:
    valid_frames = [tf.value for tf in TimeFrame]
    if v not in valid_frames:
        raise ValueError(f'Invalid timeframe. Must be one of: {valid_frames}')
    return v

TimeFrameStr = Annotated[str, Field(description="Timeframe (1min, 5min, 15min, 1hour, 4hour, daily)")]


class OHLCVData(BaseModel):
    """OHLCV data response model"""
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    data_quality_score: float
    trading_session: str

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else None
        }


class OHLCVWithIndicators(OHLCVData):
    """OHLCV + Indicators response model"""
    bollinger_upper: Optional[float] = None
    bollinger_middle: Optional[float] = None
    bollinger_lower: Optional[float] = None
    volume_sma_20: Optional[float] = None
    adx_14: Optional[float] = None
    custom_indicators: Optional[Dict[str, Any]] = None


class DNAAnalysis(BaseModel):
    """DNA trade analysis response"""
    symbol: str
    timeframe: str
    total_signals: int
    profitable_trades: int
    losing_trades: int
    win_rate: float
    avg_profit: Optional[float]
    avg_loss: Optional[float]
    total_pnl: Optional[float]
    avg_bars_held: Optional[float]


class IndicatorInfo(BaseModel):
    """Available indicator information"""
    name: str
    category: str
    description: str
    column_name: str
    supported_timeframes: List[str]
    is_active: bool


class DatabaseStats(BaseModel):
    """Database statistics response"""
    total_records: int
    symbols: List[str]
    date_range: Dict[str, str]
    timeframes: Dict[str, int]
    quality_stats: Dict[str, float]
    dna_stats: Dict[str, Union[int, float]]


# === API ENDPOINTS ===

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with basic info"""
    html_content = """
    <html>
        <head><title>DNA Research API</title></head>
        <body>
            <h1>DNA Research API - Trading Project 004</h1>
            <h3>Endpoints:</h3>
            <ul>
                <li><a href="/docs">API Documentation (Swagger)</a></li>
                <li><a href="/data/MSTR/1min?limit=100">Sample Data (MSTR 1min)</a></li>
                <li><a href="/indicators/available">Available Indicators</a></li>
                <li><a href="/statistics/performance">Performance Stats</a></li>
                <li><a href="/dashboard">Research Dashboard</a></li>
            </ul>
            <p><strong>Status:</strong> API Server Running on localhost:8000</p>
        </body>
    </html>
    """
    return html_content


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "database": "connected",
        "api_version": "1.0.0"
    }


@app.get("/data/{symbol}/{timeframe}", response_model=List[OHLCVWithIndicators])
async def get_historical_data(
    symbol: str = Path(..., description="Stock symbol (e.g., MSTR)"),
    timeframe: str = Path(..., description="Timeframe (1min, 5min, 15min, 1hour, 4hour, daily)"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    trading_hours_only: bool = Query(True, description="Filter to trading hours only"),
    min_quality: float = Query(95.0, description="Minimum data quality score"),
    limit: int = Query(1000, description="Maximum number of records"),
    db: Session = Depends(get_db)
):
    """
    Get historical OHLCV data with indicators

    **Purpose:** Core data retrieval for research and charting
    **Research Use:** Load data for statistical analysis and visualization
    """
    # Validate timeframe
    valid_frames = [tf.value for tf in TimeFrame]
    if timeframe not in valid_frames:
        raise HTTPException(status_code=400, detail=f'Invalid timeframe. Must be one of: {valid_frames}')

    try:
        # Build query
        query = db.query(EnhancedHistoricalData).filter(
            EnhancedHistoricalData.symbol == symbol.upper(),
            EnhancedHistoricalData.timeframe == TimeFrame(timeframe),
            EnhancedHistoricalData.data_quality_score >= min_quality
        )

        # Date filtering
        if start_date:
            query = query.filter(EnhancedHistoricalData.timestamp >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(EnhancedHistoricalData.timestamp <= datetime.combine(end_date, datetime.max.time()))

        # Trading hours filter
        if trading_hours_only:
            query = query.filter(EnhancedHistoricalData.is_trading_hours == True)

        # Execute query
        results = query.order_by(desc(EnhancedHistoricalData.timestamp)).limit(limit).all()

        if not results:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol} {timeframe}")

        # Convert to response format
        response_data = []
        for record in results:
            data = OHLCVWithIndicators(
                timestamp=record.timestamp,
                open_price=float(record.open_price),
                high_price=float(record.high_price),
                low_price=float(record.low_price),
                close_price=float(record.close_price),
                volume=record.volume,
                data_quality_score=record.data_quality_score,
                trading_session=record.trading_session.value,
                bollinger_upper=float(record.bollinger_upper) if record.bollinger_upper else None,
                bollinger_middle=float(record.bollinger_middle) if record.bollinger_middle else None,
                bollinger_lower=float(record.bollinger_lower) if record.bollinger_lower else None,
                volume_sma_20=record.volume_sma_20,
                adx_14=record.adx_14,
                custom_indicators=record.custom_indicators_dict
            )
            response_data.append(data)

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")


@app.get("/indicators/available", response_model=List[IndicatorInfo])
async def get_available_indicators(
    category: Optional[str] = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Show only active indicators"),
    db: Session = Depends(get_db)
):
    """
    Get list of available indicators

    **Purpose:** Discover what indicators can be used in research
    **Research Use:** Understand available analytical tools before building studies
    """
    try:
        query = db.query(IndicatorTemplate)

        if active_only:
            query = query.filter(IndicatorTemplate.is_active == True)

        if category:
            try:
                cat_enum = IndicatorCategory(category.lower())
                query = query.filter(IndicatorTemplate.category == cat_enum)
            except ValueError:
                valid_categories = [c.value for c in IndicatorCategory]
                raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {valid_categories}")

        indicators = query.all()

        response_data = []
        for indicator in indicators:
            info = IndicatorInfo(
                name=indicator.name,
                category=indicator.category.value,
                description=indicator.description or "",
                column_name=indicator.column_name,
                supported_timeframes=[tf.value for tf in indicator.supported_timeframes],
                is_active=indicator.is_active
            )
            response_data.append(info)

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving indicators: {str(e)}")


@app.post("/indicators/calculate")
async def calculate_indicator(
    symbol: str = Query(..., description="Stock symbol"),
    timeframe: TimeFrameStr = Query(..., description="Timeframe"),
    indicator_name: str = Query(..., description="Indicator name to calculate"),
    parameters: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
):
    """
    Calculate and store new indicator values

    **Purpose:** Dynamic indicator calculation and database updates
    **Research Use:** Add new analytical dimensions to existing data
    **Note:** This is a placeholder - full implementation requires indicator calculation engine
    """
    # This would typically integrate with a technical analysis library like TA-Lib
    # For now, return a placeholder response
    return {
        "status": "placeholder",
        "message": f"Indicator calculation for {indicator_name} would be implemented here",
        "symbol": symbol,
        "timeframe": timeframe,
        "parameters": parameters
    }


@app.get("/analysis/dna/{symbol}", response_model=List[DNAAnalysis])
async def get_dna_analysis(
    symbol: str = Path(..., description="Stock symbol"),
    timeframes: Optional[List[str]] = Query(None, description="Timeframes to analyze"),
    start_date: Optional[date] = Query(None, description="Analysis start date"),
    end_date: Optional[date] = Query(None, description="Analysis end date"),
    db: Session = Depends(get_db)
):
    """
    Get DNA trading simulation analysis

    **Purpose:** Statistical analysis of simulated trading performance
    **Research Use:** Understand profitability patterns across different timeframes and periods
    """
    try:
        # Default to all timeframes if none specified
        if not timeframes:
            timeframes = [tf.value for tf in TimeFrame]

        response_data = []

        for tf_str in timeframes:
            try:
                tf_enum = TimeFrame(tf_str)
            except ValueError:
                continue

            # Build query for DNA trades
            query = db.query(EnhancedHistoricalData).filter(
                EnhancedHistoricalData.symbol == symbol.upper(),
                EnhancedHistoricalData.timeframe == tf_enum,
                EnhancedHistoricalData.dna_entry_signal == True,
                EnhancedHistoricalData.dna_trade_result.isnot(None)
            )

            # Date filtering
            if start_date:
                query = query.filter(EnhancedHistoricalData.timestamp >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                query = query.filter(EnhancedHistoricalData.timestamp <= datetime.combine(end_date, datetime.max.time()))

            trades = query.all()

            if not trades:
                continue

            # Calculate statistics
            total_signals = len(trades)
            profitable_trades = len([t for t in trades if t.dna_trade_result == "WIN"])
            losing_trades = len([t for t in trades if t.dna_trade_result == "LOSS"])
            win_rate = (profitable_trades / total_signals) * 100 if total_signals > 0 else 0

            profits = [float(t.dna_pnl) for t in trades if t.dna_pnl and t.dna_trade_result == "WIN"]
            losses = [float(t.dna_pnl) for t in trades if t.dna_pnl and t.dna_trade_result == "LOSS"]
            all_pnl = [float(t.dna_pnl) for t in trades if t.dna_pnl]
            bars_held = [t.dna_bars_held for t in trades if t.dna_bars_held]

            analysis = DNAAnalysis(
                symbol=symbol.upper(),
                timeframe=tf_str,
                total_signals=total_signals,
                profitable_trades=profitable_trades,
                losing_trades=losing_trades,
                win_rate=round(win_rate, 2),
                avg_profit=round(sum(profits) / len(profits), 2) if profits else None,
                avg_loss=round(sum(losses) / len(losses), 2) if losses else None,
                total_pnl=round(sum(all_pnl), 2) if all_pnl else None,
                avg_bars_held=round(sum(bars_held) / len(bars_held), 2) if bars_held else None
            )
            response_data.append(analysis)

        if not response_data:
            raise HTTPException(status_code=404, detail=f"No DNA analysis data found for {symbol}")

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in DNA analysis: {str(e)}")


@app.get("/statistics/performance", response_model=DatabaseStats)
async def get_performance_statistics(db: Session = Depends(get_db)):
    """
    Get database and performance statistics

    **Purpose:** Overview of data coverage and quality metrics
    **Research Use:** Understand dataset scope before starting analysis
    """
    try:
        # Total records
        total_records = db.query(EnhancedHistoricalData).count()

        if total_records == 0:
            return DatabaseStats(
                total_records=0,
                symbols=[],
                date_range={"start": "No data", "end": "No data"},
                timeframes={},
                quality_stats={"avg_quality": 0.0, "min_quality": 0.0},
                dna_stats={"total_signals": 0, "win_rate": 0.0}
            )

        # Symbols
        symbols = db.query(EnhancedHistoricalData.symbol).distinct().all()
        symbol_list = [s[0] for s in symbols]

        # Date range
        date_range_query = db.query(
            func.min(EnhancedHistoricalData.timestamp),
            func.max(EnhancedHistoricalData.timestamp)
        ).first()

        start_date = date_range_query[0].strftime("%Y-%m-%d") if date_range_query[0] else "Unknown"
        end_date = date_range_query[1].strftime("%Y-%m-%d") if date_range_query[1] else "Unknown"

        # Timeframe distribution
        tf_counts = db.query(
            EnhancedHistoricalData.timeframe,
            func.count(EnhancedHistoricalData.id)
        ).group_by(EnhancedHistoricalData.timeframe).all()

        timeframe_dict = {tf.value: count for tf, count in tf_counts}

        # Quality statistics
        quality_stats = db.query(
            func.avg(EnhancedHistoricalData.data_quality_score),
            func.min(EnhancedHistoricalData.data_quality_score)
        ).first()

        avg_quality = float(quality_stats[0]) if quality_stats[0] else 0.0
        min_quality = float(quality_stats[1]) if quality_stats[1] else 0.0

        # DNA statistics
        dna_signals = db.query(EnhancedHistoricalData).filter(
            EnhancedHistoricalData.dna_entry_signal == True
        ).count()

        dna_wins = db.query(EnhancedHistoricalData).filter(
            EnhancedHistoricalData.dna_trade_result == "WIN"
        ).count()

        dna_win_rate = (dna_wins / dna_signals * 100) if dna_signals > 0 else 0.0

        return DatabaseStats(
            total_records=total_records,
            symbols=symbol_list,
            date_range={"start": start_date, "end": end_date},
            timeframes=timeframe_dict,
            quality_stats={"avg_quality": round(avg_quality, 2), "min_quality": round(min_quality, 2)},
            dna_stats={"total_signals": dna_signals, "win_rate": round(dna_win_rate, 2)}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")


# === UTILITY ENDPOINTS ===

@app.get("/symbols")
async def get_available_symbols(db: Session = Depends(get_db)):
    """Get list of available symbols"""
    symbols = db.query(EnhancedHistoricalData.symbol).distinct().all()
    return {"symbols": [s[0] for s in symbols]}


@app.get("/timeframes")
async def get_available_timeframes():
    """Get list of supported timeframes"""
    return {"timeframes": [tf.value for tf in TimeFrame]}


# Mount static files for dashboard
app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Research Dashboard - Interactive interface"""
    try:
        with open("dashboard/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard not found</h1><p>Please ensure dashboard/index.html exists</p>")


if __name__ == "__main__":
    import uvicorn
    print("Starting DNA Research API Server...")
    print("Dashboard will be available at: http://localhost:8000/dashboard")
    print("API Documentation at: http://localhost:8000/docs")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False  # Set to True for development
    )