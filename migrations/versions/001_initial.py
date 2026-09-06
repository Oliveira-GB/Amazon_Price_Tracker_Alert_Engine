"""Initial migration

Revision ID: 001_initial
Revises:
Create Date: 2026-09-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('telegram_chat_id', sa.String(length=64), nullable=False),
        sa.Column('quota_limit', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_chat_id')
    )
    op.create_index('ix_users_telegram_chat_id', 'users', ['telegram_chat_id'], unique=False)

    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('asin', sa.String(length=20), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=512), nullable=True),
        sa.Column('image_url', sa.String(length=512), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='IDLE'),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_price_full', sa.Float(), nullable=True),
        sa.Column('last_price_discount', sa.Float(), nullable=True),
        sa.Column('all_time_low', sa.Float(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asin')
    )
    op.create_index('ix_products_asin', 'products', ['asin'], unique=False)
    op.create_index('ix_products_status_checked', 'products', ['status', 'last_checked_at'], unique=False)

    op.create_table(
        'user_products',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_price', sa.Float(), nullable=True),
        sa.Column('alert_on_all_time_low', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'product_id'),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_user_product')
    )
    op.create_index('ix_user_products_user_active', 'user_products', ['user_id', 'is_active'], unique=False)

    op.create_table(
        'price_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('price_full', sa.Float(), nullable=True),
        sa.Column('price_discount', sa.Float(), nullable=True),
        sa.Column('is_discounted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_out_of_stock', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_price_history_product_id', 'price_history', ['product_id'], unique=False)
    op.create_index('ix_price_history_product_scraped', 'price_history', ['product_id', 'scraped_at'], unique=False)


def downgrade() -> None:
    op.drop_table('price_history')
    op.drop_table('user_products')
    op.drop_table('products')
    op.drop_table('users')
