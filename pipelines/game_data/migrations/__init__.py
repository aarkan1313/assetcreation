"""Sequential game-data record migrations.

Each migration module exposes `MIGRATION_ID` and `migrate(record, record_type)`.
The runner keeps migrations small and deterministic so JSONL records can stay
diff-friendly.
"""

