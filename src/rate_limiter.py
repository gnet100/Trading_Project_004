"""
Trading Project 004 - Rate Limiter for IB API
Manages API rate limits and optimizes request timing for Interactive Brokers
"""

import asyncio
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from queue import PriorityQueue, Queue
from typing import Any, Callable, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))
from logging_setup import get_logger


class RequestType(Enum):
    """Types of IB API requests with different rate limits"""

    HISTORICAL_DATA = "historical_data"
    MARKET_DATA = "market_data"
    ACCOUNT_DATA = "account_data"
    CONTRACT_DETAILS = "contract_details"
    ORDERS = "orders"


class Priority(Enum):
    """Request priority levels"""

    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class RateLimitConfig:
    """Rate limit configuration for different request types"""

    requests_per_second: float
    burst_limit: int
    cooldown_seconds: float
    max_retries: int


@dataclass
class RequestItem:
    """Individual request item for queue"""

    request_id: str
    request_type: RequestType
    priority: Priority
    request_func: Callable
    request_args: tuple
    request_kwargs: dict
    created_at: datetime
    retry_count: int = 0
    last_attempt: Optional[datetime] = None

    def __lt__(self, other):
        """Required for PriorityQueue comparison"""
        return self.created_at < other.created_at


class IBRateLimiter:
    """
    Rate limiter for Interactive Brokers API requests

    IB API Limits (based on documentation):
    - Historical Data: 60 requests per 10 minutes (6 per minute)
    - Market Data: 100 simultaneous streams
    - Account Updates: No specific limit but throttled
    - Contract Details: 50 requests per second
    """

    def __init__(self):
        self.logger = get_logger(__name__)

        # Configure rate limits for different request types
        self.rate_configs = {
            RequestType.HISTORICAL_DATA: RateLimitConfig(
                requests_per_second=0.1,  # 6 requests per minute = 0.1 per second
                burst_limit=3,  # Allow 3 quick requests
                cooldown_seconds=10.0,  # 10 second cooldown after burst
                max_retries=3,
            ),
            RequestType.MARKET_DATA: RateLimitConfig(
                requests_per_second=10.0,  # Higher rate for market data
                burst_limit=50,
                cooldown_seconds=1.0,
                max_retries=2,
            ),
            RequestType.ACCOUNT_DATA: RateLimitConfig(
                requests_per_second=1.0,  # Conservative for account data
                burst_limit=5,
                cooldown_seconds=2.0,
                max_retries=2,
            ),
            RequestType.CONTRACT_DETAILS: RateLimitConfig(
                requests_per_second=20.0,  # IB allows 50/sec, we use 20 for safety
                burst_limit=30,
                cooldown_seconds=0.5,
                max_retries=2,
            ),
            RequestType.ORDERS: RateLimitConfig(
                requests_per_second=5.0,  # Conservative for order management
                burst_limit=10,
                cooldown_seconds=1.0,
                max_retries=1,  # Orders are critical, fewer retries
            ),
        }

        # Request tracking
        self.request_history: Dict[RequestType, list] = {
            req_type: [] for req_type in RequestType
        }

        # Request queue with priority
        self.request_queue = PriorityQueue()
        self.processing_lock = threading.Lock()
        self.is_running = False

        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retried_requests": 0,
            "rate_limited_requests": 0,
            "average_wait_time": 0.0,
        }

        self.logger.info("IB Rate Limiter initialized")
        self.logger.info(
            f"Historical data rate: {self.rate_configs[RequestType.HISTORICAL_DATA].requests_per_second} req/sec"
        )

    def can_make_request(self, request_type: RequestType) -> tuple[bool, float]:
        """
        Check if request can be made now

        Args:
            request_type: Type of request to check

        Returns:
            (can_make_request, suggested_wait_time)
        """
        config = self.rate_configs[request_type]
        now = datetime.now()

        # Clean old requests from history (keep last 60 seconds)
        cutoff_time = now - timedelta(seconds=60)
        self.request_history[request_type] = [
            req_time
            for req_time in self.request_history[request_type]
            if req_time > cutoff_time
        ]

        recent_requests = self.request_history[request_type]

        # Check requests per second rate
        recent_second = [
            req_time
            for req_time in recent_requests
            if req_time > now - timedelta(seconds=1)
        ]

        if len(recent_second) >= config.requests_per_second:
            # Rate limit exceeded
            wait_time = 1.0 - (now - recent_second[0]).total_seconds()
            return False, max(wait_time, 0.1)

        # Check burst limit
        recent_burst = [
            req_time
            for req_time in recent_requests
            if req_time > now - timedelta(seconds=config.cooldown_seconds)
        ]

        if len(recent_burst) >= config.burst_limit:
            # Burst limit exceeded, need cooldown
            oldest_in_burst = min(recent_burst)
            wait_time = (
                config.cooldown_seconds - (now - oldest_in_burst).total_seconds()
            )
            return False, max(wait_time, 0.1)

        return True, 0.0

    def add_request(
        self,
        request_func: Callable,
        request_type: RequestType,
        priority: Priority = Priority.NORMAL,
        *args,
        **kwargs,
    ) -> str:
        """
        Add request to queue

        Args:
            request_func: Function to call for the request
            request_type: Type of request
            priority: Request priority
            *args: Arguments for request function
            **kwargs: Keyword arguments for request function

        Returns:
            Request ID for tracking
        """
        request_id = (
            f"{request_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        )

        request_item = RequestItem(
            request_id=request_id,
            request_type=request_type,
            priority=priority,
            request_func=request_func,
            request_args=args,
            request_kwargs=kwargs,
            created_at=datetime.now(),
        )

        # Add to priority queue (lower priority value = higher priority)
        self.request_queue.put((priority.value, request_item))

        self.logger.info(
            f"Added request {request_id} to queue (type: {request_type.value}, priority: {priority.value})"
        )
        return request_id

    def start_processing(self):
        """Start the request processing thread"""
        if self.is_running:
            self.logger.warning("Request processor already running")
            return

        self.is_running = True
        processing_thread = threading.Thread(target=self._process_requests, daemon=True)
        processing_thread.start()
        self.logger.info("Started request processing thread")

    def stop_processing(self):
        """Stop the request processing thread"""
        self.is_running = False
        self.logger.info("Stopped request processing thread")

    def _process_requests(self):
        """Main request processing loop (runs in separate thread)"""
        while self.is_running:
            try:
                if self.request_queue.empty():
                    time.sleep(0.1)
                    continue

                # Get next request
                priority, request_item = self.request_queue.get(timeout=1.0)

                # Check rate limits
                can_process, wait_time = self.can_make_request(
                    request_item.request_type
                )

                if not can_process:
                    # Put back in queue and wait
                    self.request_queue.put((priority, request_item))
                    self.stats["rate_limited_requests"] += 1
                    self.logger.debug(
                        f"Rate limited: waiting {wait_time:.2f}s for {request_item.request_id}"
                    )
                    time.sleep(wait_time)
                    continue

                # Execute request
                self._execute_request(request_item)

            except Exception as e:
                self.logger.error(f"Error in request processing: {e}")
                time.sleep(1.0)

    def _execute_request(self, request_item: RequestItem):
        """Execute a single request with retry logic"""
        config = self.rate_configs[request_item.request_type]
        request_item.last_attempt = datetime.now()

        try:
            # Record request timing
            start_time = time.time()
            self.request_history[request_item.request_type].append(datetime.now())

            # Execute the request
            result = request_item.request_func(
                *request_item.request_args, **request_item.request_kwargs
            )

            # Record success
            end_time = time.time()
            execution_time = end_time - start_time

            self.stats["total_requests"] += 1
            self.stats["successful_requests"] += 1

            # Update average wait time
            wait_time = (
                request_item.last_attempt - request_item.created_at
            ).total_seconds()
            self._update_average_wait_time(wait_time)

            self.logger.info(
                f"Request {request_item.request_id} completed in {execution_time:.2f}s "
                f"(waited {wait_time:.2f}s in queue)"
            )

            return result

        except Exception as e:
            self.logger.error(f"Request {request_item.request_id} failed: {e}")

            # Retry logic
            if request_item.retry_count < config.max_retries:
                request_item.retry_count += 1

                # Exponential backoff
                backoff_time = min(2**request_item.retry_count, 30)  # Max 30 seconds

                self.logger.info(
                    f"Retrying {request_item.request_id} in {backoff_time}s "
                    f"(attempt {request_item.retry_count + 1}/{config.max_retries + 1})"
                )

                # Schedule retry
                def schedule_retry():
                    time.sleep(backoff_time)
                    self.request_queue.put((request_item.priority.value, request_item))

                retry_thread = threading.Thread(target=schedule_retry, daemon=True)
                retry_thread.start()

                self.stats["retried_requests"] += 1
            else:
                self.logger.error(
                    f"Request {request_item.request_id} failed after "
                    f"{config.max_retries} retries"
                )
                self.stats["failed_requests"] += 1

            self.stats["total_requests"] += 1

    def _update_average_wait_time(self, wait_time: float):
        """Update average wait time using exponential moving average"""
        alpha = 0.1  # Smoothing factor
        if self.stats["average_wait_time"] == 0:
            self.stats["average_wait_time"] = wait_time
        else:
            self.stats["average_wait_time"] = (
                alpha * wait_time + (1 - alpha) * self.stats["average_wait_time"]
            )

    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.request_queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        stats = self.stats.copy()
        stats["queue_size"] = self.get_queue_size()
        stats["success_rate"] = (
            stats["successful_requests"] / max(stats["total_requests"], 1) * 100
        )
        return stats

    def get_rate_info(self, request_type: RequestType) -> Dict[str, Any]:
        """Get rate limit information for specific request type"""
        config = self.rate_configs[request_type]
        can_make, wait_time = self.can_make_request(request_type)

        recent_requests = len(
            [
                req_time
                for req_time in self.request_history[request_type]
                if req_time > datetime.now() - timedelta(seconds=60)
            ]
        )

        return {
            "request_type": request_type.value,
            "can_make_request": can_make,
            "suggested_wait_time": wait_time,
            "recent_requests_count": recent_requests,
            "requests_per_second_limit": config.requests_per_second,
            "burst_limit": config.burst_limit,
            "cooldown_seconds": config.cooldown_seconds,
        }


def main():
    """Demo of rate limiter functionality"""
    print("=" * 60)
    print("IB Rate Limiter Demo")
    print("=" * 60)

    # Create rate limiter
    rate_limiter = IBRateLimiter()
    rate_limiter.start_processing()

    # Demo function for testing
    def dummy_request(symbol: str, duration: str):
        print(f"Executing request: {symbol} for {duration}")
        time.sleep(0.5)  # Simulate API call
        return f"Data for {symbol}"

    # Add some test requests
    print("Adding test requests...")

    # Add multiple historical data requests (should be rate limited)
    for i in range(8):
        rate_limiter.add_request(
            dummy_request,
            RequestType.HISTORICAL_DATA,
            Priority.NORMAL,
            f"MSTR_{i}",
            "1 D",
        )

    # Add high priority request
    rate_limiter.add_request(
        dummy_request, RequestType.HISTORICAL_DATA, Priority.HIGH, "URGENT_MSTR", "1 H"
    )

    print(f"Queue size: {rate_limiter.get_queue_size()}")

    # Wait and show statistics
    time.sleep(15)

    stats = rate_limiter.get_stats()
    print("\nRate Limiter Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Show rate info for historical data
    rate_info = rate_limiter.get_rate_info(RequestType.HISTORICAL_DATA)
    print(f"\nHistorical Data Rate Info:")
    for key, value in rate_info.items():
        print(f"  {key}: {value}")

    rate_limiter.stop_processing()
    print("\nDemo completed!")


if __name__ == "__main__":
    main()
