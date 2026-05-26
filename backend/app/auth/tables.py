import sqlalchemy as sa


metadata = sa.MetaData()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("name", sa.String(length=160), nullable=False),
    sa.Column("email", sa.String(length=320), nullable=False, unique=True, index=True),
    sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("password_hash", sa.Text(), nullable=True),
    sa.Column("image", sa.Text(), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("session_token", sa.String(length=255), nullable=False, unique=True, index=True),
    sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
    sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
)

recovery_tokens = sa.Table(
    "recovery_tokens",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    sa.Column("token", sa.String(length=255), nullable=False, unique=True, index=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)

identification_images = sa.Table(
    "identification_images",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("storage_path", sa.Text(), nullable=False),
    sa.Column("mime_type", sa.String(length=120), nullable=False),
    sa.Column("size_bytes", sa.Integer(), nullable=False),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("status", sa.String(length=40), nullable=False),
    sa.Column("sad_path", sa.String(length=80), nullable=True),
    sa.Column("message", sa.Text(), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)

identification_candidates = sa.Table(
    "identification_candidates",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "identification_id",
        sa.Uuid(),
        sa.ForeignKey("identification_images.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("common_name", sa.String(length=180), nullable=True),
    sa.Column("suggested_scientific_name", sa.String(length=240), nullable=False),
    sa.Column("confidence_label", sa.String(length=40), nullable=False),
    sa.Column("visible_traits", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("possible_match_copy", sa.Text(), nullable=False),
    sa.Column("gbif_key", sa.Integer(), nullable=True),
    sa.Column("gbif_accepted_key", sa.Integer(), nullable=True),
    sa.Column("accepted_scientific_name", sa.String(length=240), nullable=True),
    sa.Column("taxonomic_status", sa.String(length=80), nullable=True),
    sa.Column("synonyms", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("genus", sa.String(length=160), nullable=True),
    sa.Column("family", sa.String(length=160), nullable=True),
    sa.Column("species", sa.String(length=240), nullable=True),
    sa.Column("validation_status", sa.String(length=40), nullable=False),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

knowledge_documents = sa.Table(
    "knowledge_documents",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("species_id", sa.Uuid(), nullable=True, index=True),
    sa.Column("scientific_name", sa.String(length=240), nullable=False, index=True),
    sa.Column("topic", sa.String(length=120), nullable=False, index=True),
    sa.Column("title", sa.String(length=240), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("confidence", sa.Float(), nullable=False),
    sa.Column("review_status", sa.String(length=40), nullable=False, index=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

knowledge_sources = sa.Table(
    "knowledge_sources",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "document_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("title", sa.String(length=240), nullable=False),
    sa.Column("url", sa.Text(), nullable=False),
    sa.Column("source_domain", sa.String(length=180), nullable=False, index=True),
    sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("validation_status", sa.String(length=40), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

knowledge_chunks = sa.Table(
    "knowledge_chunks",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "document_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    sa.Column("species_id", sa.Uuid(), nullable=True, index=True),
    sa.Column("scientific_name", sa.String(length=240), nullable=False, index=True),
    sa.Column("topic", sa.String(length=120), nullable=False, index=True),
    sa.Column("source_domain", sa.String(length=180), nullable=False, index=True),
    sa.Column("source_url", sa.Text(), nullable=False),
    sa.Column("confidence", sa.Float(), nullable=False),
    sa.Column("review_status", sa.String(length=40), nullable=False, index=True),
    sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

knowledge_embeddings = sa.Table(
    "knowledge_embeddings",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "chunk_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    ),
    sa.Column("provider", sa.String(length=120), nullable=False),
    sa.Column("model", sa.String(length=120), nullable=True),
    sa.Column("embedding", sa.JSON(), nullable=False),
    sa.Column("embedding_vector", sa.Text(), nullable=True),
    sa.Column("embedding_dimension", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)
