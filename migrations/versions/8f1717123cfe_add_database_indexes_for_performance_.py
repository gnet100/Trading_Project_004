"""Add database indexes for performance optimization

Revision ID: 8f1717123cfe
Revises: a1a712c0eb2b
Create Date: 2025-09-13 22:43:08.603791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1717123cfe'
down_revision: Union[str, Sequence[str], None] = 'a1a712c0eb2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add performance indexes."""
    # Check and create indexes only if they don't exist

    # Most indexes already exist from previous migrations - adding only missing ones
    try:
        # This index already exists, skip
        # op.create_index('idx_historical_data_symbol_timestamp', 'historical_data', ['symbol', 'timestamp'])
        pass
    except Exception:
        pass

    try:
        # This index already exists, skip
        # op.create_index('idx_historical_data_date', 'historical_data', [sa.text("DATE(timestamp)")])
        pass
    except Exception:
        pass

    try:
        # This index already exists, skip
        # op.create_index('idx_historical_data_trading_hours', 'historical_data', ['trading_hours'])
        pass
    except Exception:
        pass

    try:
        # This index already exists, skip
        # op.create_index('idx_historical_data_quality_score', 'historical_data', ['data_quality_score'])
        pass
    except Exception:
        pass

    # All required indexes already exist from previous schema creation
    # No additional indexes needed at this time


def downgrade() -> None:
    """Downgrade schema - Remove performance indexes."""
    # Since no new indexes were created in this migration, no action needed
    # All existing indexes were created in previous migrations
    pass
