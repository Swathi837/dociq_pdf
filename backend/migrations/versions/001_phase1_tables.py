"""create phase1 tables

Revision ID: 001_phase1_tables
Revises: 
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

revision = '001_phase1_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # ── users ──────────────────────────────────
    op.create_table('users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # ── workspaces ─────────────────────────────
    op.create_table('workspaces',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_workspaces_slug', 'workspaces', ['slug'], unique=True)

    # ── workspace_members ──────────────────────
    op.create_table('workspace_members',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.Enum('owner', 'editor', 'viewer', name='memberrole'), nullable=False, server_default='viewer'),
        sa.Column('joined_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    # ── documents ──────────────────────────────
    op.create_table('documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('uploaded_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('s3_key', sa.String(1000), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), server_default='application/pdf'),
        sa.Column('status', sa.Enum('pending', 'processing', 'processed', 'failed', name='documentstatus'), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('extracted_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_documents_workspace_id', 'documents', ['workspace_id'])
    op.create_index('ix_documents_status', 'documents', ['status'])

    # ── chunks ─────────────────────────────────
    op.create_table('chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page_num', sa.Integer(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'])
    op.create_index('ix_chunks_workspace_id', 'chunks', ['workspace_id'])

    # Vector similarity search index (cosine distance)
    op.execute("""
        CREATE INDEX ix_chunks_embedding
        ON chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # ── alerts ─────────────────────────────────
    op.create_table('alerts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('deadline_date', sa.DateTime(), nullable=False),
        sa.Column('notify_days_before', sa.Integer(), server_default='7'),
        sa.Column('notify_email', sa.Boolean(), server_default='true'),
        sa.Column('notify_slack', sa.Boolean(), server_default='false'),
        sa.Column('status', sa.Enum('active', 'triggered', 'dismissed', name='alertstatus'), nullable=False, server_default='active'),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_alerts_workspace_id', 'alerts', ['workspace_id'])
    op.create_index('ix_alerts_deadline_date', 'alerts', ['deadline_date'])


def downgrade() -> None:
    op.drop_table('alerts')
    op.drop_table('chunks')
    op.drop_table('documents')
    op.drop_table('workspace_members')
    op.drop_table('workspaces')
    op.drop_table('users')
    op.execute('DROP TYPE IF EXISTS alertstatus')
    op.execute('DROP TYPE IF EXISTS documentstatus')
    op.execute('DROP TYPE IF EXISTS memberrole')
    op.execute("""
    CREATE INDEX ix_chunks_embedding
    ON chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
""")