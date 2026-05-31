"""knowledge rag acquisition

Revision ID: 0004_knowledge_rag
Revises: 0003_plant_id_taxonomy
Create Date: 2026-05-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_knowledge_rag"
down_revision: Union[str, None] = "0003_plant_id_taxonomy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("species_id", sa.Uuid(), nullable=True),
        sa.Column("scientific_name", sa.String(length=240), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_knowledge_documents_species_id", "knowledge_documents", ["species_id"])
    op.create_index(
        "ix_knowledge_documents_scientific_name", "knowledge_documents", ["scientific_name"]
    )
    op.create_index("ix_knowledge_documents_topic", "knowledge_documents", ["topic"])
    op.create_index(
        "ix_knowledge_documents_review_status", "knowledge_documents", ["review_status"]
    )

    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.String(length=180), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_knowledge_sources_document_id", "knowledge_sources", ["document_id"])
    op.create_index("ix_knowledge_sources_source_domain", "knowledge_sources", ["source_domain"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("species_id", sa.Uuid(), nullable=True),
        sa.Column("scientific_name", sa.String(length=240), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("source_domain", sa.String(length=180), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_species_id", "knowledge_chunks", ["species_id"])
    op.create_index(
        "ix_knowledge_chunks_scientific_name", "knowledge_chunks", ["scientific_name"]
    )
    op.create_index("ix_knowledge_chunks_topic", "knowledge_chunks", ["topic"])
    op.create_index("ix_knowledge_chunks_source_domain", "knowledge_chunks", ["source_domain"])
    op.create_index("ix_knowledge_chunks_review_status", "knowledge_chunks", ["review_status"])
    op.create_index("ix_knowledge_chunks_retrieved_at", "knowledge_chunks", ["retrieved_at"])

    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "chunk_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("embedding_vector", sa.Text(), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_knowledge_embeddings_chunk_id", "knowledge_embeddings", ["chunk_id"])
    op.execute(
        "ALTER TABLE knowledge_embeddings "
        "ALTER COLUMN embedding_vector TYPE vector(8) USING embedding_vector::vector"
    )
    op.execute(
        "CREATE INDEX ix_knowledge_embeddings_vector "
        "ON knowledge_embeddings USING hnsw (embedding_vector vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_embeddings_vector", table_name="knowledge_embeddings")
    op.drop_index("ix_knowledge_embeddings_chunk_id", table_name="knowledge_embeddings")
    op.drop_table("knowledge_embeddings")
    op.drop_index("ix_knowledge_chunks_retrieved_at", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_review_status", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_source_domain", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_topic", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_scientific_name", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_species_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_sources_source_domain", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_document_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
    op.drop_index("ix_knowledge_documents_review_status", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_topic", table_name="knowledge_documents")
    op.drop_index(
        "ix_knowledge_documents_scientific_name", table_name="knowledge_documents"
    )
    op.drop_index("ix_knowledge_documents_species_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
