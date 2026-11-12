from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, cast
from uuid import UUID

try:
    import asyncpg  # type: ignore[reportMissingTypeStubs]
except ImportError:
    asyncpg = None


class DatabaseConnection(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[object]: ...

    async def fetchval(self, query: str, *args: object) -> UUID | None: ...

    async def execute(self, query: str, *args: object) -> str: ...

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, Any] | None: ...

    async def fetch(self, query: str, *args: object) -> Sequence[Mapping[str, Any]]: ...


class DatabasePool(Protocol):
    def acquire(self) -> AbstractAsyncContextManager[DatabaseConnection]: ...

    async def close(self) -> None: ...


class BaseDatabaseService:
    def __init__(self, database_url: str, pool: DatabasePool | None = None) -> None:
        self._database_url = database_url
        self._pool = pool
        self._owns_pool = pool is None

    @property
    def pool(self) -> DatabasePool | None:
        return self._pool

    def set_pool(self, pool: DatabasePool | None) -> None:
        self._pool = pool
        self._owns_pool = False

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = cast(DatabasePool, await asyncpg.create_pool(self._database_url))
            self._owns_pool = True

    async def close(self) -> None:
        if self._pool is not None and self._owns_pool:
            await self._pool.close()
            self._pool = None

    def _require_pool(self) -> DatabasePool:
        if self._pool is None:
            raise RuntimeError(f"{self.__class__.__name__} is not connected to the planner database.")
        return self._pool
