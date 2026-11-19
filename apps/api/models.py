from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB


metadata = MetaData()
json_type = Text().with_variant(JSONB(), "postgresql")

models = Table(
    "models",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", Text, nullable=False),
    Column("provider", Text, nullable=False),
    Column("family", Text, nullable=False),
    Column("parameters", Text, nullable=False),
    Column("modality", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("color", Text, nullable=False),
    Column("values_json", json_type, nullable=False),
    Column("is_demo", Boolean, nullable=False, default=True, server_default="true"),
)

regions = Table(
    "regions",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("is_demo", Boolean, nullable=False, default=True, server_default="true"),
)

datasets = Table(
    "datasets",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", Text, nullable=False),
    Column("provider", Text, nullable=False),
    Column("resolution", Text, nullable=False),
    Column("coverage", Text, nullable=False),
    Column("type", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("is_demo", Boolean, nullable=False, default=True, server_default="true"),
)

runs = Table(
    "runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("region_id", String, ForeignKey("regions.id"), nullable=False),
    Column("crop", Text, nullable=False),
    Column("season", Text, nullable=False),
    Column("dataset_id", String, ForeignKey("datasets.id"), nullable=False),
    Column("model_ids", json_type, nullable=False),
    Column("results_json", json_type, nullable=False),
    Column("is_demo", Boolean, nullable=False, default=True, server_default="true"),
    Column("provenance_json", json_type),
)
Index("ix_runs_created_at", runs.c.created_at)

data_sources = Table(
    "data_sources",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", Text, nullable=False),
    Column("provider", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("coverage", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("access_type", Text, nullable=False),
    Column("source_url", Text),
    Column("updated_at", DateTime(timezone=True)),
)

data_assets = Table(
    "data_assets",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_id", String, ForeignKey("data_sources.id"), nullable=False),
    Column("region_id", String, ForeignKey("regions.id"), nullable=False),
    Column("asset_type", Text, nullable=False),
    Column("payload_json", json_type, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("status", Text, nullable=False),
)
Index("ix_data_assets_region_type_fetched", data_assets.c.region_id, data_assets.c.asset_type, data_assets.c.fetched_at)

ingestion_jobs = Table(
    "ingestion_jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_id", String, ForeignKey("data_sources.id"), nullable=False),
    Column("region_id", String, ForeignKey("regions.id")),
    Column("asset_id", String, ForeignKey("data_assets.id")),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("detail", Text),
)
Index("ix_ingestion_jobs_created_at", ingestion_jobs.c.created_at)

evaluation_jobs = Table(
    "evaluation_jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("runs.id")),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("manifest_json", json_type),
    Column("result_json", json_type),
    Column("detail", Text),
    Column("provenance_json", json_type),
)
Index("ix_evaluation_jobs_created_at", evaluation_jobs.c.created_at)

TABLES = (
    models,
    regions,
    datasets,
    runs,
    data_sources,
    data_assets,
    ingestion_jobs,
    evaluation_jobs,
)
