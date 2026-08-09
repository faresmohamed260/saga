from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "analysis_outputs" / "saga_canonical.sqlite3"
DEFAULT_OUTPUT = PROJECT_ROOT / "deploy" / "sqlite" / "saga_team_seed.sqlite3"


def _exec_many(connection: sqlite3.Connection, statements: list[str]) -> None:
    for statement in statements:
        connection.execute(statement)


def sanitize_database(source: Path, output: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    connection = sqlite3.connect(output)
    try:
        source_connection.backup(connection)
        _exec_many(
            connection,
            [
                "DELETE FROM provider_account_statuses",
                "DELETE FROM provider_accounts",
                "DELETE FROM provider_configs",
                "UPDATE generated_images SET image_bytes = NULL, output_path = NULL, thumbnail_path = NULL",
                "UPDATE generated_images SET manifest_json = NULL",
                "UPDATE entities SET generated_image_bytes = NULL, generated_image_path = NULL, generated_thumbnail_path = NULL",
                "UPDATE books SET source_path = '', contract_path = NULL",
                "UPDATE scenes SET payload_json = NULL",
                "UPDATE uploaded_sources SET stored_path = ''",
            ],
        )
        connection.commit()
        connection.execute("VACUUM")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"Integrity check failed for {output}: {integrity!r}")
    finally:
        source_connection.close()
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a sanitized team-shareable SQLite seed database.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to the live source SQLite database.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to write the sanitized SQLite database.")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    sanitize_database(source, output)
    print(output)


if __name__ == "__main__":
    main()
