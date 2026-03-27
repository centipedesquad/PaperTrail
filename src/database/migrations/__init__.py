"""
Migration registry for PaperTrail.

Each migration module exposes:
    name: str           - Human-readable name
    description: str    - What this migration does
    needs_run(conn)     - Introspect DB schema, return True if migration should apply
    apply(conn)         - Execute the migration SQL
"""

from database.migrations import baseline_schema, fts5_contentless

# Ordered list of all migrations. Order matters for fresh databases.
MIGRATION_REGISTRY = [
    baseline_schema,
    fts5_contentless,
]
