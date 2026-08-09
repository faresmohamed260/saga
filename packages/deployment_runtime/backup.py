"""Postgres backup/restore commands with secret-safe process invocation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

from sqlalchemy.engine import make_url


class BackupRuntime:
    def __init__(self, *, pg_dump: str = "pg_dump", pg_restore: str = "pg_restore", psql: str = "psql", schemas: tuple[str, ...] = ("public",), required_extensions: tuple[str, ...] = ("vector",), runner=subprocess.run) -> None:
        self.pg_dump = pg_dump
        self.pg_restore = pg_restore
        self.psql = psql
        self.schemas = tuple(str(schema).strip() for schema in schemas if str(schema).strip())
        if not self.schemas:
            raise ValueError("At least one application-owned schema is required.")
        self.required_extensions = tuple(str(extension).strip() for extension in required_extensions if str(extension).strip())
        if any(not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", extension) for extension in self.required_extensions):
            raise ValueError("Extension names must be PostgreSQL identifiers.")
        self.runner = runner

    def create(self, *, database_url: str, output_path: str | Path, release_id: str = "") -> dict[str, object]:
        target = Path(output_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        schema_args = [f"--schema={schema}" for schema in self.schemas]
        command, environment = self._command(self.pg_dump, database_url, ["--format=custom", "--no-owner", "--no-acl", *schema_args, f"--file={target}"])
        self._run(command, environment, operation="backup")
        if not target.is_file() or target.stat().st_size <= 0:
            raise RuntimeError("Backup command completed without a non-empty artifact.")
        manifest = {"path": str(target), "size_bytes": target.stat().st_size, "sha256": _sha256(target), "release_id": release_id, "created_at_ms": int(time.time() * 1000)}
        target.with_suffix(target.suffix + ".json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return manifest

    def restore(self, *, database_url: str, backup_path: str | Path, confirm_target: str) -> dict[str, object]:
        source = Path(backup_path).resolve()
        if not source.is_file():
            raise FileNotFoundError(str(source))
        url = make_url(database_url)
        database = str(url.database or "")
        if confirm_target != database:
            raise ValueError("Restore confirmation must exactly match the target database name.")
        for extension in self.required_extensions:
            command, environment = self._command(self.psql, database_url, ["--set=ON_ERROR_STOP=1", f"--command=CREATE EXTENSION IF NOT EXISTS {extension};"])
            self._run(command, environment, operation="restore preparation")
        schema_args = [f"--schema={schema}" for schema in self.schemas]
        command, environment = self._command(self.pg_restore, database_url, [f"--dbname={database}", "--clean", "--if-exists", "--no-owner", "--no-acl", *schema_args, str(source)])
        self._run(command, environment, operation="restore")
        return {"restored": True, "database": database, "sha256": _sha256(source)}

    def _run(self, command: list[str], environment: dict[str, str], *, operation: str) -> None:
        try:
            self.runner(command, env=environment, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            raw = exc.stderr or exc.stdout or b""
            detail = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            raise RuntimeError(f"PostgreSQL {operation} failed: {detail[-2000:].strip() or type(exc).__name__}") from None

    @staticmethod
    def _command(executable: str, database_url: str, arguments: list[str]) -> tuple[list[str], dict[str, str]]:
        url = make_url(database_url)
        environment = dict(os.environ)
        environment.update({"PGHOST": str(url.host or ""), "PGPORT": str(url.port or 5432), "PGDATABASE": str(url.database or ""), "PGUSER": str(url.username or "")})
        if url.password:
            environment["PGPASSWORD"] = str(url.password)
        return [executable, *arguments], environment


class ArtifactBackupRuntime:
    def __init__(self, *, object_store, page_size: int = 100) -> None:
        self.object_store = object_store
        self.page_size = max(1, min(1000, int(page_size)))

    def create(self, *, bucket_names: list[str], output_path: str | Path, release_id: str = "") -> dict[str, object]:
        target = Path(output_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        objects: list[dict[str, object]] = []
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for bucket in sorted({str(name).strip() for name in bucket_names if str(name).strip()}):
                offset = 0
                while True:
                    page = self.object_store.list_objects(bucket, limit=self.page_size, offset=offset)
                    if not page:
                        break
                    for item in page:
                        path = str(item.get("path") or item.get("name") or "").strip()
                        if not path:
                            raise RuntimeError(f"Storage provider returned an object without a path in bucket '{bucket}'.")
                        data = self.object_store.download_bytes(bucket, path)
                        member = f"objects/{len(objects):09d}.bin"
                        archive.writestr(member, data)
                        objects.append({
                            "bucket": bucket, "path": path, "member": member, "size_bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(), "content_type": str(item.get("content_type") or "application/octet-stream"),
                        })
                    offset += len(page)
                    if len(page) < self.page_size:
                        break
            manifest = {"format": "saga-artifact-backup-v1", "release_id": release_id, "created_at_ms": int(time.time() * 1000), "objects": objects}
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True, separators=(",", ":")))
        return {"path": str(target), "size_bytes": target.stat().st_size, "sha256": _sha256(target), "object_count": len(objects), "bucket_count": len({item["bucket"] for item in objects})}

    def restore(self, *, backup_path: str | Path, confirm_target: str) -> dict[str, object]:
        if confirm_target != "artifact-storage":
            raise ValueError("Artifact restore confirmation must exactly match 'artifact-storage'.")
        source = Path(backup_path).resolve()
        with zipfile.ZipFile(source, "r") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != "saga-artifact-backup-v1":
                raise ValueError("Unsupported artifact backup format.")
            restored = 0
            buckets: set[str] = set()
            for item in manifest.get("objects") or []:
                data = archive.read(str(item["member"]))
                if len(data) != int(item["size_bytes"]) or hashlib.sha256(data).hexdigest() != item["sha256"]:
                    raise RuntimeError(f"Artifact backup integrity check failed for {item['bucket']}/{item['path']}.")
                bucket = str(item["bucket"])
                if bucket not in buckets:
                    self.object_store.ensure_bucket(bucket)
                    buckets.add(bucket)
                self.object_store.upload_bytes(bucket, str(item["path"]), data, content_type=str(item.get("content_type") or "application/octet-stream"), upsert=True)
                restored += 1
        return {"restored": True, "object_count": restored, "bucket_count": len(buckets), "sha256": _sha256(source)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
