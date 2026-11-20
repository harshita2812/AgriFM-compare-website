"""Add relational constraints and lookup indexes.

Revision ID: 0002_foreign_keys_and_indexes
Revises: 0001_initial_schema
"""
from alembic import op
from sqlalchemy import inspect


revision = "0002_foreign_keys_and_indexes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


FOREIGN_KEYS = {
    "runs": (
        ("fk_runs_region_id_regions", "regions", "region_id", "id"),
        ("fk_runs_dataset_id_datasets", "datasets", "dataset_id", "id"),
    ),
    "data_assets": (
        ("fk_data_assets_source_id_data_sources", "data_sources", "source_id", "id"),
        ("fk_data_assets_region_id_regions", "regions", "region_id", "id"),
    ),
    "ingestion_jobs": (
        ("fk_ingestion_jobs_source_id_data_sources", "data_sources", "source_id", "id"),
        ("fk_ingestion_jobs_region_id_regions", "regions", "region_id", "id"),
        ("fk_ingestion_jobs_asset_id_data_assets", "data_assets", "asset_id", "id"),
    ),
    "evaluation_jobs": (
        ("fk_evaluation_jobs_run_id_runs", "runs", "run_id", "id"),
    ),
}


INDEXES = (
    ("ix_runs_created_at", "runs", ("created_at",)),
    ("ix_data_assets_region_type_fetched", "data_assets", ("region_id", "asset_type", "fetched_at")),
    ("ix_ingestion_jobs_created_at", "ingestion_jobs", ("created_at",)),
    ("ix_evaluation_jobs_created_at", "evaluation_jobs", ("created_at",)),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    for table_name, constraints in FOREIGN_KEYS.items():
        existing = inspector.get_foreign_keys(table_name)
        missing = [
            constraint for constraint in constraints
            if not any(
                foreign_key["constrained_columns"] == [constraint[2]]
                and foreign_key["referred_table"] == constraint[1]
                and foreign_key["referred_columns"] == [constraint[3]]
                for foreign_key in existing
            )
        ]
        if missing:
            with op.batch_alter_table(table_name, recreate=recreate) as batch:
                for name, referred_table, local_column, remote_column in missing:
                    batch.create_foreign_key(
                        name,
                        referred_table,
                        [local_column],
                        [remote_column],
                    )
        inspector = inspect(bind)

    existing_indexes = {
        table_name: {index["name"] for index in inspect(bind).get_indexes(table_name)}
        for _, table_name, _ in INDEXES
    }
    for name, table_name, columns in INDEXES:
        if name not in existing_indexes[table_name]:
            op.create_index(name, table_name, list(columns))


def downgrade() -> None:
    bind = op.get_bind()
    for name, table_name, _columns in reversed(INDEXES):
        if any(index["name"] == name for index in inspect(bind).get_indexes(table_name)):
            op.drop_index(name, table_name=table_name)

    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    for table_name, constraints in reversed(tuple(FOREIGN_KEYS.items())):
        existing = inspect(bind).get_foreign_keys(table_name)
        names = {foreign_key.get("name") for foreign_key in existing}
        removable = [name for name, _, _, _ in constraints if name in names]
        if removable:
            with op.batch_alter_table(table_name, recreate=recreate) as batch:
                for name in removable:
                    batch.drop_constraint(name, type_="foreignkey")
