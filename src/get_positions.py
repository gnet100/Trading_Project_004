"""
Trading Project 004 - Get Current Positions
Script to retrieve and display current positions from Interactive Brokers
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from ib_connector import IBConnector
from logging_setup import setup_logging, get_logger


def get_positions_data():
    """Get and display current positions from IB"""
    
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    try:
        print("Connecting to Interactive Brokers...")
        
        # Create IB connector
        ib = IBConnector()
        
        # Connect to IB
        if not ib.connect_to_ib():
            print("❌ Failed to connect to Interactive Brokers")
            print("Make sure TWS/Gateway is running and API is enabled")
            return False
        
        print("✅ Connected successfully!")
        print("📊 Retrieving account and position data...")
        
        # Wait for data to arrive
        time.sleep(4)
        
        # Get account summary
        balance = ib.get_account_balance()
        print(f"\n=== ACCOUNT SUMMARY ===")
        print(f"Account: U3050259")
        for key, value in balance.items():
            if key in ['NetLiquidation', 'TotalCashValue', 'GrossPositionValue']:
                print(f"{key}: ${value}")
        
        # Get and display positions
        positions = ib.get_positions()
        if positions:
            print(ib.get_position_summary())
            
            # Detailed position info
            print("\n=== DETAILED POSITIONS ===")
            for symbol, pos in positions.items():
                if pos.position != 0:
                    print(f"\n{symbol}:")
                    print(f"  Position: {pos.position} shares")
                    print(f"  Average Cost: ${pos.average_cost:.2f}")
                    print(f"  Market Price: ${pos.market_price:.2f}")
                    print(f"  Market Value: ${pos.market_value:.2f}")
                    print(f"  Unrealized P&L: ${pos.unrealized_pnl:.2f}")
                    print(f"  Realized P&L: ${pos.realized_pnl:.2f}")
        else:
            print("\n📭 No open positions found")
        
        # Disconnect
        print("\n🔌 Disconnecting...")
        ib.disconnect_from_ib()
        
        return True
        
    except Exception as e:
        logger.error(f"Error retrieving positions: {e}")
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("🏦 Interactive Brokers Position Report")
    print("=" * 50)
    
    success = get_positions_data()
    
    print("=" * 50)
    if success:
        print("✅ Position report completed successfully")
    else:
        print("❌ Position report failed")
    print("=" * 50)