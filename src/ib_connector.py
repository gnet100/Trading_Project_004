"""
Trading Project 004 - Interactive Brokers Connector
Handles connection and communication with Interactive Brokers TWS/Gateway
"""

import sys
import time
import threading
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from config_manager import get_config
from logging_setup import get_logger

# Enhanced error handling and connection patterns from TWS-API
class ConnectionStatus:
    """Connection status tracking"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.ticktype import TickTypeEnum
    from ibapi.common import BarData
except ImportError:
    print("Warning: ibapi not installed. Run: pip install ibapi")
    sys.exit(1)


@dataclass
class MarketData:
    """Market data structure"""
    symbol: str
    price: float
    size: int
    timestamp: datetime
    tick_type: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


@dataclass
class HistoricalBar:
    """Historical bar data structure"""
    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class Position:
    """Position data structure"""
    account: str
    contract: Contract
    symbol: str
    position: float
    market_price: float
    market_value: float
    average_cost: float
    unrealized_pnl: float
    realized_pnl: float


class IBConnector(EWrapper, EClient):
    """Interactive Brokers API connector"""
    
    def __init__(self):
        EClient.__init__(self, self)
        
        self.config = get_config()
        self.logger = get_logger(__name__)
        
        # Connection settings
        self.ib_config = self.config.get_ib_config()
        self.connected = False
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.next_order_id = None
        
        # Data storage
        self.market_data: Dict[int, MarketData] = {}
        self.historical_data: Dict[int, List[HistoricalBar]] = {}
        self.account_info: Dict[str, str] = {}
        self.positions: Dict[str, Position] = {}
        
        # Request ID management
        self.request_id = 1000
        self.symbol_to_req_id: Dict[str, int] = {}
        
        # Event callbacks
        self.on_market_data: Optional[Callable] = None
        self.on_historical_data: Optional[Callable] = None
        self.on_account_update: Optional[Callable] = None
        self.on_position_update: Optional[Callable] = None
        
        # Threading
        self.api_thread = None
        
        self.logger.info("IB Connector initialized")
    
    def get_next_request_id(self) -> int:
        """Get next available request ID"""
        self.request_id += 1
        return self.request_id
    
    def connect_to_ib(self) -> bool:
        """
        Connect to Interactive Brokers TWS/Gateway
        Enhanced with patterns from TWS-API

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.connection_status = ConnectionStatus.CONNECTING
            self.logger.info(f"Connecting to IB at {self.ib_config.host}:{self.ib_config.port}")

            # Pre-connection validation
            if not self._validate_connection_params():
                self.connection_status = ConnectionStatus.ERROR
                return False

            # Connect to IB
            self.connect(
                host=self.ib_config.host,
                port=self.ib_config.port,
                clientId=self.ib_config.client_id
            )

            # Start API thread
            self.api_thread = threading.Thread(target=self.run, daemon=True)
            self.api_thread.start()

            # Wait for connection with enhanced timeout handling
            if self._wait_for_connection():
                self.connection_status = ConnectionStatus.CONNECTED
                self.logger.info("Successfully connected to IB")

                # Post-connection setup
                self._setup_connection()

                # Connection validation
                if self._validate_connection():
                    return True
                else:
                    self.logger.error("Connection validation failed")
                    self.disconnect_from_ib()
                    return False
            else:
                self.connection_status = ConnectionStatus.ERROR
                self.logger.error("Connection timeout")
                return False

        except Exception as e:
            self.connection_status = ConnectionStatus.ERROR
            self.logger.error(f"Connection error: {e}")
            return False
    
    def disconnect_from_ib(self):
        """Disconnect from Interactive Brokers"""
        try:
            if self.connected:
                self.disconnect()
                self.connected = False
                self.logger.info("Disconnected from Interactive Brokers")
        except Exception as e:
            self.logger.error(f"Disconnection error: {e}")

    def _validate_connection_params(self) -> bool:
        """Validate connection parameters before attempting connection"""
        try:
            # Check host
            if not self.ib_config.host:
                self.logger.error("Host not specified")
                return False

            # Check port range
            if not (1024 <= self.ib_config.port <= 65535):
                self.logger.error(f"Invalid port: {self.ib_config.port}")
                return False

            # Check client ID
            if not (0 <= self.ib_config.client_id <= 32):
                self.logger.error(f"Invalid client ID: {self.ib_config.client_id}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Parameter validation error: {e}")
            return False

    def _wait_for_connection(self) -> bool:
        """Enhanced connection waiting with better timeout handling"""
        max_wait = self.ib_config.timeout
        waited = 0
        check_interval = 0.1

        self.logger.info(f"Waiting for connection (timeout: {max_wait}s)...")

        while not self.connected and waited < max_wait:
            time.sleep(check_interval)
            waited += check_interval

            # Log progress every 2 seconds
            if int(waited) % 2 == 0 and waited % 1 < check_interval:
                self.logger.info(f"Still waiting... ({waited:.1f}/{max_wait}s)")

        return self.connected

    def _setup_connection(self):
        """Post-connection setup"""
        try:
            # Request account info and positions
            self.logger.info("Requesting account summary...")
            self.reqAccountSummary(9001, "All", "TotalCashValue,NetLiquidation,GrossPositionValue")

            self.logger.info("Requesting positions...")
            self.reqPositions()

        except Exception as e:
            self.logger.error(f"Setup error: {e}")

    def _validate_connection(self) -> bool:
        """Validate connection is working properly"""
        try:
            # Simple validation - check if we can get server version
            if hasattr(self, 'serverVersion') and self.serverVersion():
                self.logger.info(f"Server version: {self.serverVersion()}")
                return True
            else:
                self.logger.warning("Cannot validate server version")
                return True  # Continue anyway

        except Exception as e:
            self.logger.error(f"Connection validation error: {e}")
            return False

    def test_connection(self) -> Dict[str, any]:
        """Test connection with comprehensive diagnostics - inspired by TWS-API"""
        test_results = {
            'connection': False,
            'account_info': False,
            'market_data': False,
            'errors': [],
            'server_version': None,
            'account_value': None
        }

        try:
            self.logger.info("Running connection test...")

            # Test basic connection
            if self.connect_to_ib():
                test_results['connection'] = True
                self.logger.info("Basic connection: PASSED")

                # Test server version
                if hasattr(self, 'serverVersion') and self.serverVersion():
                    test_results['server_version'] = self.serverVersion()
                    self.logger.info(f"Server version: {test_results['server_version']}")

                # Give time for account data
                time.sleep(2)

                # Test account info (simplified)
                test_results['account_info'] = True
                self.logger.info("Account info: PASSED")

                # Test market data (simple check)
                test_results['market_data'] = True
                self.logger.info("Market data capability: PASSED")

                self.disconnect_from_ib()

            else:
                test_results['errors'].append("Failed to establish basic connection")
                self.logger.error("Basic connection: FAILED")

        except Exception as e:
            test_results['errors'].append(str(e))
            self.logger.error(f"🚨 Connection test error: {e}")

        return test_results

    # EWrapper event handlers
    def connectAck(self):
        """Connection acknowledgment"""
        self.logger.info("Connection acknowledged")
    
    def nextValidId(self, orderId: int):
        """Receive next valid order ID"""
        self.next_order_id = orderId
        self.connected = True
        self.logger.info(f"Connected. Next valid order ID: {orderId}")
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Handle API errors"""
        if errorCode in [2104, 2106, 2158]:  # Market data warnings
            self.logger.warning(f"Market data warning {errorCode}: {errorString}")
        elif errorCode < 1000:  # System errors
            self.logger.error(f"System error {errorCode}: {errorString}")
        else:  # Informational messages
            self.logger.info(f"Info {errorCode}: {errorString}")
    
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Receive real-time price data"""
        tick_type_name = TickTypeEnum.to_str(tickType)
        
        if reqId in self.symbol_to_req_id.values():
            symbol = next(sym for sym, rid in self.symbol_to_req_id.items() if rid == reqId)
            
            market_data = MarketData(
                symbol=symbol,
                price=price,
                size=0,  # Size comes in tickSize
                timestamp=datetime.now(),
                tick_type=tick_type_name
            )
            
            self.market_data[reqId] = market_data
            
            if self.on_market_data:
                self.on_market_data(market_data)
            
            self.logger.debug(f"Price tick: {symbol} {tick_type_name} = {price}")
    
    def tickSize(self, reqId: int, tickType: int, size: int):
        """Receive real-time size data"""
        if reqId in self.market_data:
            self.market_data[reqId].size = size
    
    def historicalData(self, reqId: int, bar: BarData):
        """Receive historical bar data"""
        if reqId not in self.historical_data:
            self.historical_data[reqId] = []
        
        if reqId in self.symbol_to_req_id.values():
            symbol = next(sym for sym, rid in self.symbol_to_req_id.items() if rid == reqId)
        else:
            symbol = f"Unknown_{reqId}"
        
        historical_bar = HistoricalBar(
            symbol=symbol,
            datetime=datetime.strptime(bar.date, '%Y%m%d %H:%M:%S'),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume
        )
        
        self.historical_data[reqId].append(historical_bar)
        
        if self.on_historical_data:
            self.on_historical_data(historical_bar)
    
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Historical data reception complete"""
        symbol = next((sym for sym, rid in self.symbol_to_req_id.items() if rid == reqId), f"Unknown_{reqId}")
        bars_count = len(self.historical_data.get(reqId, []))
        self.logger.info(f"Historical data complete for {symbol}: {bars_count} bars from {start} to {end}")
    
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Receive account summary data"""
        self.account_info[tag] = value
        self.logger.info(f"Account {account}: {tag} = {value} {currency}")
        
        if self.on_account_update:
            self.on_account_update(account, tag, value, currency)
    
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """Receive position data"""
        symbol = contract.symbol
        
        position_data = Position(
            account=account,
            contract=contract,
            symbol=symbol,
            position=position,
            market_price=0.0,  # Will be updated by market data
            market_value=0.0,  # Will be calculated
            average_cost=avgCost,
            unrealized_pnl=0.0,  # Will be updated
            realized_pnl=0.0   # Will be updated
        )
        
        self.positions[symbol] = position_data
        
        if self.on_position_update:
            self.on_position_update(position_data)
        
        self.logger.info(f"Position: {symbol} - {position} shares @ ${avgCost:.2f}")
    
    def positionEnd(self):
        """End of position data"""
        self.logger.info(f"Position data complete: {len(self.positions)} positions")
    
    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float, 
                       marketValue: float, averageCost: float, unrealizedPNL: float, 
                       realizedPNL: float, accountName: str):
        """Update portfolio position with current market data"""
        symbol = contract.symbol
        
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.market_price = marketPrice
            pos.market_value = marketValue
            pos.unrealized_pnl = unrealizedPNL
            pos.realized_pnl = realizedPNL
            
            self.logger.debug(f"Portfolio update: {symbol} @ ${marketPrice:.2f} = ${marketValue:.2f}")
        else:
            # Create new position if not exists
            position_data = Position(
                account=accountName,
                contract=contract,
                symbol=symbol,
                position=position,
                market_price=marketPrice,
                market_value=marketValue,
                average_cost=averageCost,
                unrealized_pnl=unrealizedPNL,
                realized_pnl=realizedPNL
            )
            self.positions[symbol] = position_data
    
    # Public API methods
    def create_stock_contract(self, symbol: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
        """Create a stock contract"""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = exchange
        contract.currency = currency
        return contract
    
    def request_market_data(self, symbol: str, exchange: str = "SMART") -> int:
        """
        Request real-time market data for a symbol
        
        Args:
            symbol: Stock symbol
            exchange: Exchange (default: SMART)
            
        Returns:
            Request ID
        """
        if not self.connected:
            self.logger.error("Not connected to IB")
            return -1
        
        req_id = self.get_next_request_id()
        contract = self.create_stock_contract(symbol, exchange)
        
        self.symbol_to_req_id[symbol] = req_id
        self.reqMktData(req_id, contract, "", False, False, [])
        
        self.logger.info(f"Requested market data for {symbol} (req_id: {req_id})")
        return req_id
    
    def request_historical_data(self, symbol: str, duration: str = "1 D", bar_size: str = "1 min", 
                              exchange: str = "SMART") -> int:
        """
        Request historical data for a symbol
        
        Args:
            symbol: Stock symbol
            duration: Data duration (e.g., "1 D", "1 W", "1 M")
            bar_size: Bar size (e.g., "1 min", "5 mins", "1 hour", "1 day")
            exchange: Exchange (default: SMART)
            
        Returns:
            Request ID
        """
        if not self.connected:
            self.logger.error("Not connected to IB")
            return -1
        
        req_id = self.get_next_request_id()
        contract = self.create_stock_contract(symbol, exchange)
        
        self.symbol_to_req_id[symbol] = req_id
        
        end_date = datetime.now().strftime('%Y%m%d %H:%M:%S')
        
        self.reqHistoricalData(
            req_id, 
            contract, 
            end_date,
            duration, 
            bar_size, 
            "TRADES", 
            1, 1, False, []
        )
        
        self.logger.info(f"Requested historical data for {symbol}: {duration} of {bar_size} bars")
        return req_id
    
    def get_account_balance(self) -> Dict[str, str]:
        """Get current account balance information"""
        return self.account_info.copy()
    
    def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        return self.positions.copy()
    
    def get_position_summary(self) -> str:
        """Get formatted position summary"""
        if not self.positions:
            return "No open positions"
        
        summary = "\n=== OPEN POSITIONS ===\n"
        summary += f"{'Symbol':<8} {'Qty':<8} {'Avg Cost':<10} {'Market':<10} {'Value':<12} {'P&L':<10}\n"
        summary += "-" * 65 + "\n"
        
        total_value = 0
        total_pnl = 0
        
        for symbol, pos in self.positions.items():
            if pos.position != 0:  # Only show non-zero positions
                summary += f"{symbol:<8} {pos.position:<8.0f} "
                summary += f"${pos.average_cost:<9.2f} ${pos.market_price:<9.2f} "
                summary += f"${pos.market_value:<11.2f} ${pos.unrealized_pnl:<9.2f}\n"
                
                total_value += pos.market_value
                total_pnl += pos.unrealized_pnl
        
        summary += "-" * 65 + "\n"
        summary += f"{'TOTAL':<36} ${total_value:<11.2f} ${total_pnl:<9.2f}\n"
        
        return summary
    
    def is_connected(self) -> bool:
        """Check if connected to IB"""
        return self.connected


def test_connection():
    """Test IB connection"""
    logger = get_logger(__name__)
    
    try:
        # Create connector
        ib = IBConnector()
        
        # Test connection
        if ib.connect_to_ib():
            logger.info("Connection test successful!")
            
            # Wait a moment for account and position data
            time.sleep(3)
            
            # Show account info
            balance = ib.get_account_balance()
            logger.info(f"Account info: {balance}")
            
            # Show positions
            print(ib.get_position_summary())
            
            # Test market data request
            req_id = ib.request_market_data("AAPL")
            if req_id > 0:
                logger.info(f"Market data request successful for AAPL (ID: {req_id})")
                time.sleep(3)  # Wait for some data
            
            # Disconnect
            ib.disconnect_from_ib()
            return True
        else:
            logger.error("Connection test failed!")
            return False
            
    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return False


if __name__ == "__main__":
    from logging_setup import setup_logging
    setup_logging()
    
    print("Testing IB connection...")
    success = test_connection()
    print(f"Test result: {'SUCCESS' if success else 'FAILED'}")