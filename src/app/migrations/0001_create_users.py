"""create users

Revision ID: 0001_create_users
Revises: 
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_create_users'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('created', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )
    op.create_table(
        'tokens',
        sa.Column('token', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('created', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('token'),
    )
    op.create_table(
        'threads',
        sa.Column('thread_id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('thread_id'),
    )


def downgrade() -> None:
    op.drop_table('threads')
    op.drop_table('tokens')
    op.drop_table('users')

