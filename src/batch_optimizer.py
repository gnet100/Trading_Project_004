"""
Trading Project 004 - Batch Request Optimizer
Optimizes multiple data requests for efficient IB API usage
"""

import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from logging_setup import get_logger
from rate_limiter import IBRateLimiter, Priority, RequestType


class BatchStrategy(Enum):
    """Different batching strategies"""

    SEQUENTIAL = "sequential"  # One by one (safest)
    PARALLEL_SYMBOL = "parallel_symbol"  # Multiple symbols, same timeframe
    PARALLEL_TIMEFRAME = "parallel_timeframe"  # Same symbol, multiple timeframes
    MIXED_PARALLEL = "mixed_parallel"  # Mixed approach


@dataclass
class BatchRequest:
    """Individual request in a batch"""

    symbol: str
    duration: str
    bar_size: str
    exchange: str = "SMART"
    priority: Priority = Priority.NORMAL
    request_id: Optional[str] = None
    status: str = "pending"  # pending, queued, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class BatchOptimizer:
    """
    Optimizes batch requests for historical data downloads

    Strategies:
    1. Group by timeframe - download all symbols for each timeframe
    2. Group by symbol - download all timeframes for each symbol
    3. Prioritize high-priority requests
    4. Distribute load across time to avoid rate limits
    """

    def __init__(self, rate_limiter: IBRateLimiter):
        self.logger = get_logger(__name__)
        self.rate_limiter = rate_limiter
        self.batches: Dict[str, List[BatchRequest]] = {}
        self.batch_stats = {
            "total_requests": 0,
            "completed_requests": 0,
            "failed_requests": 0,
            "average_batch_time": 0.0,
            "batches_processed": 0,
        }

        self.logger.info("Batch Optimizer initialized")

    def create_multi_symbol_batch(
        self,
        symbols: List[str],
        duration: str,
        bar_size: str,
        batch_name: str = None,
        exchange: str = "SMART",
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """
        Create batch for multiple symbols, same timeframe

        Args:
            symbols: List of stock symbols
            duration: Duration string (e.g., "1 D", "2 Y")
            bar_size: Bar size (e.g., "1 min", "15 mins")
            batch_name: Optional batch name
            exchange: Exchange
            priority: Request priority

        Returns:
            Batch ID
        """
        if not batch_name:
            batch_name = f"multi_symbol_{bar_size.replace(' ', '_')}_{datetime.now().strftime('%H%M%S')}"

        requests = []
        for symbol in symbols:
            request = BatchRequest(
                symbol=symbol,
                duration=duration,
                bar_size=bar_size,
                exchange=exchange,
                priority=priority,
            )
            requests.append(request)

        self.batches[batch_name] = requests
        self.batch_stats["total_requests"] += len(requests)

        self.logger.info(
            f"Created multi-symbol batch '{batch_name}': "
            f"{len(symbols)} symbols, {bar_size}, {duration}"
        )
        return batch_name

    def create_multi_timeframe_batch(
        self,
        symbol: str,
        timeframes: List[Tuple[str, str]],
        batch_name: str = None,
        exchange: str = "SMART",
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """
        Create batch for single symbol, multiple timeframes

        Args:
            symbol: Stock symbol
            timeframes: List of (duration, bar_size) tuples
            batch_name: Optional batch name
            exchange: Exchange
            priority: Request priority

        Returns:
            Batch ID
        """
        if not batch_name:
            batch_name = f"multi_timeframe_{symbol}_{datetime.now().strftime('%H%M%S')}"

        requests = []
        for duration, bar_size in timeframes:
            request = BatchRequest(
                symbol=symbol,
                duration=duration,
                bar_size=bar_size,
                exchange=exchange,
                priority=priority,
            )
            requests.append(request)

        self.batches[batch_name] = requests
        self.batch_stats["total_requests"] += len(requests)

        self.logger.info(
            f"Created multi-timeframe batch '{batch_name}': "
            f"{symbol}, {len(timeframes)} timeframes"
        )
        return batch_name

    def create_comprehensive_batch(
        self,
        symbols: List[str],
        timeframes: List[Tuple[str, str]],
        batch_name: str = None,
        exchange: str = "SMART",
        priority_map: Optional[Dict[str, Priority]] = None,
    ) -> str:
        """
        Create comprehensive batch for multiple symbols and timeframes

        Args:
            symbols: List of stock symbols
            timeframes: List of (duration, bar_size) tuples
            batch_name: Optional batch name
            exchange: Exchange
            priority_map: Optional mapping of symbols to priorities

        Returns:
            Batch ID
        """
        if not batch_name:
            batch_name = f"comprehensive_{len(symbols)}x{len(timeframes)}_{datetime.now().strftime('%H%M%S')}"

        requests = []
        for symbol in symbols:
            symbol_priority = (
                priority_map.get(symbol, Priority.NORMAL)
                if priority_map
                else Priority.NORMAL
            )

            for duration, bar_size in timeframes:
                request = BatchRequest(
                    symbol=symbol,
                    duration=duration,
                    bar_size=bar_size,
                    exchange=exchange,
                    priority=symbol_priority,
                )
                requests.append(request)

        self.batches[batch_name] = requests
        self.batch_stats["total_requests"] += len(requests)

        total_requests = len(symbols) * len(timeframes)
        self.logger.info(
            f"Created comprehensive batch '{batch_name}': "
            f"{len(symbols)} symbols × {len(timeframes)} timeframes = {total_requests} requests"
        )
        return batch_name

    def execute_batch(
        self,
        batch_name: str,
        strategy: BatchStrategy = BatchStrategy.SEQUENTIAL,
        downloader_func: callable = None,
    ) -> Dict[str, Any]:
        """
        Execute a batch of requests

        Args:
            batch_name: Name of batch to execute
            strategy: Batching strategy to use
            downloader_func: Function to call for each download

        Returns:
            Batch execution results
        """
        if batch_name not in self.batches:
            raise ValueError(f"Batch '{batch_name}' not found")

        batch_requests = self.batches[batch_name]
        start_time = datetime.now()

        self.logger.info(
            f"Executing batch '{batch_name}' with {len(batch_requests)} requests"
        )
        self.logger.info(f"Strategy: {strategy.value}")

        if strategy == BatchStrategy.SEQUENTIAL:
            results = self._execute_sequential(batch_requests, downloader_func)
        elif strategy == BatchStrategy.PARALLEL_SYMBOL:
            results = self._execute_parallel_by_symbol(batch_requests, downloader_func)
        elif strategy == BatchStrategy.PARALLEL_TIMEFRAME:
            results = self._execute_parallel_by_timeframe(
                batch_requests, downloader_func
            )
        else:
            results = self._execute_mixed_parallel(batch_requests, downloader_func)

        # Calculate batch statistics
        end_time = datetime.now()
        batch_time = (end_time - start_time).total_seconds()

        completed = sum(1 for req in batch_requests if req.status == "completed")
        failed = sum(1 for req in batch_requests if req.status == "failed")

        self.batch_stats["completed_requests"] += completed
        self.batch_stats["failed_requests"] += failed
        self.batch_stats["batches_processed"] += 1

        # Update average batch time
        if self.batch_stats["average_batch_time"] == 0:
            self.batch_stats["average_batch_time"] = batch_time
        else:
            alpha = 0.2
            self.batch_stats["average_batch_time"] = (
                alpha * batch_time
                + (1 - alpha) * self.batch_stats["average_batch_time"]
            )

        batch_results = {
            "batch_name": batch_name,
            "strategy": strategy.value,
            "total_requests": len(batch_requests),
            "completed": completed,
            "failed": failed,
            "success_rate": (completed / len(batch_requests)) * 100,
            "execution_time_seconds": batch_time,
            "requests_per_minute": (completed / batch_time) * 60
            if batch_time > 0
            else 0,
            "requests": batch_requests,
        }

        self.logger.info(
            f"Batch '{batch_name}' completed: "
            f"{completed}/{len(batch_requests)} successful "
            f"in {batch_time:.1f}s"
        )

        return batch_results

    def _execute_sequential(
        self, requests: List[BatchRequest], downloader_func: callable
    ) -> List[BatchRequest]:
        """Execute requests one by one"""
        for request in requests:
            self._execute_single_request(request, downloader_func)
            # Small delay between requests
            time.sleep(0.1)
        return requests

    def _execute_parallel_by_symbol(
        self, requests: List[BatchRequest], downloader_func: callable
    ) -> List[BatchRequest]:
        """Group by symbol, execute timeframes in parallel for each symbol"""
        # Group requests by symbol
        symbol_groups = {}
        for request in requests:
            if request.symbol not in symbol_groups:
                symbol_groups[request.symbol] = []
            symbol_groups[request.symbol].append(request)

        # Execute each symbol group sequentially, but timeframes in parallel
        for symbol, symbol_requests in symbol_groups.items():
            self.logger.info(
                f"Processing {len(symbol_requests)} timeframes for {symbol}"
            )

            # Add all requests for this symbol to rate limiter simultaneously
            for request in symbol_requests:
                self._execute_single_request(request, downloader_func)

            # Small delay between symbols
            time.sleep(0.5)

        return requests

    def _execute_parallel_by_timeframe(
        self, requests: List[BatchRequest], downloader_func: callable
    ) -> List[BatchRequest]:
        """Group by timeframe, execute symbols in parallel for each timeframe"""
        # Group requests by timeframe
        timeframe_groups = {}
        for request in requests:
            tf_key = f"{request.bar_size}_{request.duration}"
            if tf_key not in timeframe_groups:
                timeframe_groups[tf_key] = []
            timeframe_groups[tf_key].append(request)

        # Execute each timeframe group sequentially, but symbols in parallel
        for tf_key, tf_requests in timeframe_groups.items():
            self.logger.info(
                f"Processing {len(tf_requests)} symbols for timeframe {tf_key}"
            )

            # Add all requests for this timeframe to rate limiter simultaneously
            for request in tf_requests:
                self._execute_single_request(request, downloader_func)

            # Longer delay between timeframes (rate limiting consideration)
            time.sleep(2.0)

        return requests

    def _execute_mixed_parallel(
        self, requests: List[BatchRequest], downloader_func: callable
    ) -> List[BatchRequest]:
        """Mixed strategy: prioritize high priority, then parallel execution"""
        # Sort by priority first
        sorted_requests = sorted(requests, key=lambda r: r.priority.value)

        # Execute high priority requests first (sequential)
        high_priority = [
            r
            for r in sorted_requests
            if r.priority in [Priority.CRITICAL, Priority.HIGH]
        ]
        normal_priority = [
            r for r in sorted_requests if r.priority in [Priority.NORMAL, Priority.LOW]
        ]

        if high_priority:
            self.logger.info(
                f"Processing {len(high_priority)} high priority requests first"
            )
            for request in high_priority:
                self._execute_single_request(request, downloader_func)
                time.sleep(0.2)

        if normal_priority:
            self.logger.info(
                f"Processing {len(normal_priority)} normal priority requests in parallel"
            )
            # Use parallel by timeframe for normal priority
            self._execute_parallel_by_timeframe(normal_priority, downloader_func)

        return requests

    def _execute_single_request(self, request: BatchRequest, downloader_func: callable):
        """Execute a single request"""
        try:
            request.status = "queued"

            if downloader_func:
                # Use provided downloader function
                result = downloader_func(
                    symbol=request.symbol,
                    duration=request.duration,
                    bar_size=request.bar_size,
                    exchange=request.exchange,
                )
                request.result = result
                request.status = "completed"
            else:
                # Add to rate limiter queue (actual execution happens there)
                def dummy_request():
                    return f"Data for {request.symbol} {request.bar_size}"

                request.request_id = self.rate_limiter.add_request(
                    dummy_request, RequestType.HISTORICAL_DATA, request.priority
                )
                request.status = "queued"

            request.completed_at = datetime.now()

        except Exception as e:
            request.status = "failed"
            request.error = str(e)
            request.completed_at = datetime.now()
            self.logger.error(
                f"Request failed: {request.symbol} {request.bar_size} - {e}"
            )

    def get_batch_status(self, batch_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific batch"""
        if batch_name not in self.batches:
            return None

        requests = self.batches[batch_name]

        status_counts = {}
        for request in requests:
            status_counts[request.status] = status_counts.get(request.status, 0) + 1

        return {
            "batch_name": batch_name,
            "total_requests": len(requests),
            "status_breakdown": status_counts,
            "completion_percentage": (status_counts.get("completed", 0) / len(requests))
            * 100,
            "requests": requests,
        }

    def get_optimizer_stats(self) -> Dict[str, Any]:
        """Get overall optimizer statistics"""
        stats = self.batch_stats.copy()
        stats["active_batches"] = len(self.batches)

        if stats["total_requests"] > 0:
            stats["overall_success_rate"] = (
                stats["completed_requests"] / stats["total_requests"]
            ) * 100
        else:
            stats["overall_success_rate"] = 0.0

        return stats

    def clear_batch(self, batch_name: str):
        """Clear a completed batch from memory"""
        if batch_name in self.batches:
            del self.batches[batch_name]
            self.logger.info(f"Cleared batch '{batch_name}' from memory")


def main():
    """Demo of batch optimizer"""
    print("=" * 60)
    print("Batch Optimizer Demo")
    print("=" * 60)

    # Create rate limiter and batch optimizer
    from rate_limiter import IBRateLimiter

    rate_limiter = IBRateLimiter()
    rate_limiter.start_processing()

    batch_optimizer = BatchOptimizer(rate_limiter)

    # Demo: Create multi-symbol batch
    symbols = ["MSTR", "TSLA", "AAPL", "NVDA"]
    batch_id = batch_optimizer.create_multi_symbol_batch(
        symbols=symbols, duration="1 D", bar_size="1 min", batch_name="demo_batch"
    )

    print(f"Created batch: {batch_id}")

    # Check initial status
    status = batch_optimizer.get_batch_status(batch_id)
    print(f"Initial status: {status['completion_percentage']:.1f}% complete")

    # Execute batch
    results = batch_optimizer.execute_batch(
        batch_id, strategy=BatchStrategy.PARALLEL_TIMEFRAME
    )

    print(f"\nBatch Results:")
    print(f"  Total requests: {results['total_requests']}")
    print(f"  Completed: {results['completed']}")
    print(f"  Success rate: {results['success_rate']:.1f}%")
    print(f"  Execution time: {results['execution_time_seconds']:.1f}s")
    print(f"  Requests per minute: {results['requests_per_minute']:.1f}")

    # Get optimizer statistics
    stats = batch_optimizer.get_optimizer_stats()
    print(f"\nOptimizer Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    rate_limiter.stop_processing()
    print("\nDemo completed!")


if __name__ == "__main__":
    main()
