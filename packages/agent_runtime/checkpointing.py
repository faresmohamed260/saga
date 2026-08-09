from __future__ import annotations

import random
from datetime import datetime, timezone
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from sqlalchemy import JSON, Column, DateTime, MetaData, String, Table, delete, desc, insert, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.sql.sqltypes import Integer, LargeBinary

from packages.persistence_runtime.providers import create_sqlalchemy_engine


checkpoint_metadata = MetaData()

agent_checkpoints_table = Table(
    "agent_runtime_checkpoints",
    checkpoint_metadata,
    Column("thread_id", String(160), primary_key=True),
    Column("checkpoint_ns", String(255), primary_key=True, default=""),
    Column("checkpoint_id", String(160), primary_key=True),
    Column("parent_checkpoint_id", String(160), nullable=True),
    Column("checkpoint_type", String(120), nullable=False),
    Column("checkpoint_bytes", LargeBinary, nullable=False),
    Column("metadata_type", String(120), nullable=False),
    Column("metadata_bytes", LargeBinary, nullable=False),
    Column("metadata_json", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True)),
)

agent_checkpoint_blobs_table = Table(
    "agent_runtime_checkpoint_blobs",
    checkpoint_metadata,
    Column("thread_id", String(160), primary_key=True),
    Column("checkpoint_ns", String(255), primary_key=True, default=""),
    Column("channel", String(255), primary_key=True),
    Column("version", String(160), primary_key=True),
    Column("blob_type", String(120), nullable=False),
    Column("blob_bytes", LargeBinary, nullable=False),
)

agent_checkpoint_writes_table = Table(
    "agent_runtime_checkpoint_writes",
    checkpoint_metadata,
    Column("thread_id", String(160), primary_key=True),
    Column("checkpoint_ns", String(255), primary_key=True, default=""),
    Column("checkpoint_id", String(160), primary_key=True),
    Column("task_id", String(160), primary_key=True),
    Column("write_idx", Integer, primary_key=True),
    Column("channel", String(255), nullable=False),
    Column("value_type", String(120), nullable=False),
    Column("value_bytes", LargeBinary, nullable=False),
    Column("task_path", String(512), nullable=False, default=""),
)


class SqlCheckpointSaver(BaseCheckpointSaver[str]):
    def __init__(
        self,
        *,
        engine: Engine | None = None,
        database_url: str = "",
        serde=None,
    ) -> None:
        super().__init__(serde=serde)
        if engine is None and not str(database_url or "").strip():
            raise ValueError("SqlCheckpointSaver requires either an engine or a database_url.")
        self.engine = engine or create_sqlalchemy_engine(str(database_url or "").strip())
        if self.engine.dialect.name == "sqlite":
            checkpoint_metadata.create_all(self.engine)
        else:
            missing = [name for name in checkpoint_metadata.tables if not inspect(self.engine).has_table(name)]
            if missing:
                raise RuntimeError("Agent checkpoint schema is missing; run `saga-deploy migrate upgrade`: " + ", ".join(missing))

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id, checkpoint_ns, checkpoint_id = _config_parts(config)
        with self.engine.begin() as conn:
            if checkpoint_id:
                row = conn.execute(
                    select(agent_checkpoints_table).where(
                        agent_checkpoints_table.c.thread_id == thread_id,
                        agent_checkpoints_table.c.checkpoint_ns == checkpoint_ns,
                        agent_checkpoints_table.c.checkpoint_id == checkpoint_id,
                    )
                ).mappings().first()
            else:
                row = conn.execute(
                    select(agent_checkpoints_table)
                    .where(
                        agent_checkpoints_table.c.thread_id == thread_id,
                        agent_checkpoints_table.c.checkpoint_ns == checkpoint_ns,
                    )
                    .order_by(
                        desc(agent_checkpoints_table.c.created_at),
                        desc(agent_checkpoints_table.c.checkpoint_id),
                    )
                ).mappings().first()
            if row is None:
                return None
            checkpoint = self.serde.loads_typed((str(row["checkpoint_type"]), bytes(row["checkpoint_bytes"])))
            metadata = self.serde.loads_typed((str(row["metadata_type"]), bytes(row["metadata_bytes"])))
            checkpoint_with_values = {
                **checkpoint,
                "channel_values": self._load_blobs(
                    conn,
                    thread_id=str(row["thread_id"]),
                    checkpoint_ns=str(row["checkpoint_ns"] or ""),
                    versions=checkpoint["channel_versions"],
                ),
            }
            writes = conn.execute(
                select(agent_checkpoint_writes_table)
                .where(
                    agent_checkpoint_writes_table.c.thread_id == str(row["thread_id"]),
                    agent_checkpoint_writes_table.c.checkpoint_ns == str(row["checkpoint_ns"] or ""),
                    agent_checkpoint_writes_table.c.checkpoint_id == str(row["checkpoint_id"]),
                )
                .order_by(agent_checkpoint_writes_table.c.task_id.asc(), agent_checkpoint_writes_table.c.write_idx.asc())
            ).mappings().all()
        resolved_checkpoint_id = str(row["checkpoint_id"])
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": str(row["thread_id"]),
                    "checkpoint_ns": str(row["checkpoint_ns"] or ""),
                    "checkpoint_id": resolved_checkpoint_id,
                }
            },
            checkpoint=checkpoint_with_values,
            metadata=metadata,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": str(row["thread_id"]),
                        "checkpoint_ns": str(row["checkpoint_ns"] or ""),
                        "checkpoint_id": str(row["parent_checkpoint_id"]),
                    }
                }
                if row["parent_checkpoint_id"]
                else None
            ),
            pending_writes=[
                (
                    str(write["task_id"]),
                    str(write["channel"]),
                    self.serde.loads_typed((str(write["value_type"]), bytes(write["value_bytes"]))),
                )
                for write in writes
            ],
        )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        stmt = select(agent_checkpoints_table).order_by(
            agent_checkpoints_table.c.thread_id.asc(),
            agent_checkpoints_table.c.checkpoint_ns.asc(),
            desc(agent_checkpoints_table.c.created_at),
            desc(agent_checkpoints_table.c.checkpoint_id),
        )
        if config is not None:
            thread_id, checkpoint_ns, checkpoint_id = _config_parts(config)
            stmt = stmt.where(agent_checkpoints_table.c.thread_id == thread_id)
            stmt = stmt.where(agent_checkpoints_table.c.checkpoint_ns == checkpoint_ns)
            if checkpoint_id:
                stmt = stmt.where(agent_checkpoints_table.c.checkpoint_id == checkpoint_id)
        before_id = get_checkpoint_id(before) if before else None
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        remaining = limit
        for row in rows:
            if before_id and str(row["checkpoint_id"]) >= str(before_id):
                continue
            metadata_json = dict(row["metadata_json"] or {})
            if filter and not all(metadata_json.get(key) == value for key, value in filter.items()):
                continue
            if remaining is not None and remaining <= 0:
                break
            checkpoint_tuple = self.get_tuple(
                {
                    "configurable": {
                        "thread_id": str(row["thread_id"]),
                        "checkpoint_ns": str(row["checkpoint_ns"] or ""),
                        "checkpoint_id": str(row["checkpoint_id"]),
                    }
                }
            )
            if checkpoint_tuple is None:
                continue
            if remaining is not None:
                remaining -= 1
            yield checkpoint_tuple

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id, checkpoint_ns, _ = _config_parts(config)
        checkpoint_payload = checkpoint.copy()
        values: dict[str, Any] = checkpoint_payload.pop("channel_values")  # type: ignore[misc]
        serialized_checkpoint = self.serde.dumps_typed(checkpoint_payload)
        serialized_metadata = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        metadata_json = dict(get_checkpoint_metadata(config, metadata) or {})
        with self.engine.begin() as conn:
            for channel, version in new_versions.items():
                version_key = _version_key(version)
                conn.execute(
                    delete(agent_checkpoint_blobs_table).where(
                        agent_checkpoint_blobs_table.c.thread_id == thread_id,
                        agent_checkpoint_blobs_table.c.checkpoint_ns == checkpoint_ns,
                        agent_checkpoint_blobs_table.c.channel == str(channel),
                        agent_checkpoint_blobs_table.c.version == version_key,
                    )
                )
                blob = self.serde.dumps_typed(values[channel]) if channel in values else ("empty", b"")
                conn.execute(
                    insert(agent_checkpoint_blobs_table).values(
                        thread_id=thread_id,
                        checkpoint_ns=checkpoint_ns,
                        channel=str(channel),
                        version=version_key,
                        blob_type=str(blob[0]),
                        blob_bytes=bytes(blob[1]),
                    )
                )
            conn.execute(
                delete(agent_checkpoints_table).where(
                    agent_checkpoints_table.c.thread_id == thread_id,
                    agent_checkpoints_table.c.checkpoint_ns == checkpoint_ns,
                    agent_checkpoints_table.c.checkpoint_id == str(checkpoint["id"]),
                )
            )
            conn.execute(
                insert(agent_checkpoints_table).values(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                    checkpoint_id=str(checkpoint["id"]),
                    parent_checkpoint_id=config.get("configurable", {}).get("checkpoint_id"),
                    checkpoint_type=str(serialized_checkpoint[0]),
                    checkpoint_bytes=bytes(serialized_checkpoint[1]),
                    metadata_type=str(serialized_metadata[0]),
                    metadata_bytes=bytes(serialized_metadata[1]),
                    metadata_json=metadata_json,
                    created_at=datetime.now(timezone.utc),
                )
            )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": str(checkpoint["id"]),
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id, checkpoint_ns, checkpoint_id = _config_parts(config)
        if not checkpoint_id:
            raise ValueError("checkpoint_id is required to persist checkpoint writes.")
        with self.engine.begin() as conn:
            existing_rows = conn.execute(
                select(agent_checkpoint_writes_table.c.task_id, agent_checkpoint_writes_table.c.write_idx).where(
                    agent_checkpoint_writes_table.c.thread_id == thread_id,
                    agent_checkpoint_writes_table.c.checkpoint_ns == checkpoint_ns,
                    agent_checkpoint_writes_table.c.checkpoint_id == checkpoint_id,
                )
            ).all()
            existing_keys = {(str(row[0]), int(row[1])) for row in existing_rows}
            for index, (channel, value) in enumerate(writes):
                write_idx = int(WRITES_IDX_MAP.get(channel, index))
                key = (str(task_id), write_idx)
                if write_idx >= 0 and key in existing_keys:
                    continue
                conn.execute(
                    delete(agent_checkpoint_writes_table).where(
                        agent_checkpoint_writes_table.c.thread_id == thread_id,
                        agent_checkpoint_writes_table.c.checkpoint_ns == checkpoint_ns,
                        agent_checkpoint_writes_table.c.checkpoint_id == checkpoint_id,
                        agent_checkpoint_writes_table.c.task_id == str(task_id),
                        agent_checkpoint_writes_table.c.write_idx == write_idx,
                    )
                )
                serialized = self.serde.dumps_typed(value)
                conn.execute(
                    insert(agent_checkpoint_writes_table).values(
                        thread_id=thread_id,
                        checkpoint_ns=checkpoint_ns,
                        checkpoint_id=checkpoint_id,
                        task_id=str(task_id),
                        write_idx=write_idx,
                        channel=str(channel),
                        value_type=str(serialized[0]),
                        value_bytes=bytes(serialized[1]),
                        task_path=str(task_path or ""),
                    )
                )

    def delete_thread(self, thread_id: str) -> None:
        normalized_thread_id = str(thread_id or "").strip()
        if not normalized_thread_id:
            raise ValueError("thread_id is required.")
        with self.engine.begin() as conn:
            conn.execute(delete(agent_checkpoint_writes_table).where(agent_checkpoint_writes_table.c.thread_id == normalized_thread_id))
            conn.execute(delete(agent_checkpoint_blobs_table).where(agent_checkpoint_blobs_table.c.thread_id == normalized_thread_id))
            conn.execute(delete(agent_checkpoints_table).where(agent_checkpoints_table.c.thread_id == normalized_thread_id))

    def delete_for_runs(self, run_ids: Sequence[str]) -> None:
        normalized_run_ids = [str(run_id or "").strip() for run_id in run_ids if str(run_id or "").strip()]
        if not normalized_run_ids:
            return
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(agent_checkpoints_table.c.thread_id)
                .where(agent_checkpoints_table.c.metadata_json["run_id"].as_string().in_(normalized_run_ids))
            ).all()
        for (thread_id,) in rows:
            self.delete_thread(str(thread_id))

    def copy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        self.delete_thread(target_thread_id)
        with self.engine.begin() as conn:
            checkpoint_rows = conn.execute(
                select(agent_checkpoints_table).where(agent_checkpoints_table.c.thread_id == str(source_thread_id))
            ).mappings().all()
            blob_rows = conn.execute(
                select(agent_checkpoint_blobs_table).where(agent_checkpoint_blobs_table.c.thread_id == str(source_thread_id))
            ).mappings().all()
            write_rows = conn.execute(
                select(agent_checkpoint_writes_table).where(agent_checkpoint_writes_table.c.thread_id == str(source_thread_id))
            ).mappings().all()
            for row in checkpoint_rows:
                payload = dict(row)
                payload["thread_id"] = str(target_thread_id)
                conn.execute(insert(agent_checkpoints_table).values(**payload))
            for row in blob_rows:
                payload = dict(row)
                payload["thread_id"] = str(target_thread_id)
                conn.execute(insert(agent_checkpoint_blobs_table).values(**payload))
            for row in write_rows:
                payload = dict(row)
                payload["thread_id"] = str(target_thread_id)
                conn.execute(insert(agent_checkpoint_writes_table).values(**payload))

    def prune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        normalized_thread_ids = [str(thread_id or "").strip() for thread_id in thread_ids if str(thread_id or "").strip()]
        if not normalized_thread_ids:
            return
        if strategy == "delete":
            for thread_id in normalized_thread_ids:
                self.delete_thread(thread_id)
            return
        if strategy != "keep_latest":
            raise ValueError(f"Unsupported prune strategy '{strategy}'.")
        for thread_id in normalized_thread_ids:
            with self.engine.begin() as conn:
                rows = conn.execute(
                    select(agent_checkpoints_table.c.checkpoint_ns, agent_checkpoints_table.c.checkpoint_id)
                    .where(agent_checkpoints_table.c.thread_id == thread_id)
                    .order_by(agent_checkpoints_table.c.checkpoint_ns.asc(), desc(agent_checkpoints_table.c.checkpoint_id))
                ).all()
                keep_pairs: set[tuple[str, str]] = set()
                for checkpoint_ns, checkpoint_id in rows:
                    pair = (str(checkpoint_ns or ""), str(checkpoint_id))
                    if pair[0] not in {item[0] for item in keep_pairs}:
                        keep_pairs.add(pair)
                for checkpoint_ns, checkpoint_id in rows:
                    pair = (str(checkpoint_ns or ""), str(checkpoint_id))
                    if pair in keep_pairs:
                        continue
                    conn.execute(
                        delete(agent_checkpoint_writes_table).where(
                            agent_checkpoint_writes_table.c.thread_id == thread_id,
                            agent_checkpoint_writes_table.c.checkpoint_ns == pair[0],
                            agent_checkpoint_writes_table.c.checkpoint_id == pair[1],
                        )
                    )
                    conn.execute(
                        delete(agent_checkpoints_table).where(
                            agent_checkpoints_table.c.thread_id == thread_id,
                            agent_checkpoints_table.c.checkpoint_ns == pair[0],
                            agent_checkpoints_table.c.checkpoint_id == pair[1],
                        )
                    )

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return self.get_tuple(config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        self.put_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        self.delete_thread(thread_id)

    async def adelete_for_runs(self, run_ids: Sequence[str]) -> None:
        self.delete_for_runs(run_ids)

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        self.copy_thread(source_thread_id, target_thread_id)

    async def aprune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        self.prune(thread_ids, strategy=strategy)

    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(str(current).split(".", 1)[0])
        next_v = current_v + 1
        next_h = random.random()
        return f"{next_v:032}.{next_h:016}"

    def _load_blobs(
        self,
        conn,
        *,
        thread_id: str,
        checkpoint_ns: str,
        versions: ChannelVersions,
    ) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for channel, version in (versions or {}).items():
            row = conn.execute(
                select(agent_checkpoint_blobs_table)
                .where(
                    agent_checkpoint_blobs_table.c.thread_id == thread_id,
                    agent_checkpoint_blobs_table.c.checkpoint_ns == checkpoint_ns,
                    agent_checkpoint_blobs_table.c.channel == str(channel),
                    agent_checkpoint_blobs_table.c.version == _version_key(version),
                )
            ).mappings().first()
            if row is None or str(row["blob_type"]) == "empty":
                continue
            values[str(channel)] = self.serde.loads_typed((str(row["blob_type"]), bytes(row["blob_bytes"])))
        return values


def _config_parts(config: RunnableConfig) -> tuple[str, str, str]:
    configurable = dict((config or {}).get("configurable") or {})
    thread_id = str(configurable.get("thread_id") or "").strip()
    if not thread_id:
        raise ValueError("RunnableConfig.configurable.thread_id is required for checkpoint persistence.")
    checkpoint_ns = str(configurable.get("checkpoint_ns") or "").strip()
    checkpoint_id = str(configurable.get("checkpoint_id") or "").strip()
    return thread_id, checkpoint_ns, checkpoint_id


def _version_key(value: Any) -> str:
    return str(value)
