"""Explicit read-only access to an existing Stocks-and-Investment database.

The adapter deliberately reuses :class:`SQLiteStorage`'s read methods while
constructing its own SQLite connection.  It never calls the write-capable
constructor or migration routine.  SQLite's ``query_only`` mode is the final
guard against inherited persistence methods changing the database.
"""

from __future__ import annotations

import re
import sqlite3
from os import PathLike, fspath
from pathlib import Path
from urllib.parse import quote

from stocks_investment.storage.sqlite import SQLiteStorage


_SQLITE_HEADER = b"SQLite format 3\x00"
_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class ReadOnlyStorageError(ValueError):
    """Raised when a path cannot be opened as an existing read-only database."""


class ReadOnlySQLiteStorage(SQLiteStorage):
    """Read-only SQLite adapter for persisted research artifacts.

    The path must be an existing regular file containing a SQLite database.
    No parent directories, database files, schema objects, or migrations are
    created by this class.
    """

    def __init__(self, path: str | PathLike[str]) -> None:
        raw_path = fspath(path)
        if not isinstance(raw_path, str):
            raise ReadOnlyStorageError("read-only storage requires a text filesystem path")
        if any(ord(character) < 32 or ord(character) == 127 for character in raw_path):
            raise ReadOnlyStorageError("control characters are not valid in a database path")
        if _URI_SCHEME.match(raw_path):
            raise ReadOnlyStorageError("URI schemes are not accepted; provide a filesystem path")

        try:
            resolved = Path(raw_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ReadOnlyStorageError("database path must already exist") from exc
        if not resolved.is_file():
            raise ReadOnlyStorageError("database path must be an existing regular file")
        try:
            with resolved.open("rb") as database_file:
                header = database_file.read(len(_SQLITE_HEADER))
        except OSError as exc:
            raise ReadOnlyStorageError("database file is not readable") from exc
        if header != _SQLITE_HEADER:
            raise ReadOnlyStorageError("path is not a SQLite database")

        self.path = resolved
        database_uri = f"file:{quote(str(resolved), safe='/')}?mode=ro"
        try:
            self._connection = sqlite3.connect(database_uri, uri=True)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA query_only = ON")
            query_only = self._connection.execute("PRAGMA query_only").fetchone()[0]
            if query_only != 1:  # pragma: no cover - defensive SQLite/runtime guard
                raise ReadOnlyStorageError("SQLite did not enable query-only mode")
            version_row = self._connection.execute(
                "SELECT value FROM schema_meta WHERE key = 'version'"
            ).fetchone()
            if version_row is None or int(version_row[0]) != self.schema_version:
                raise ReadOnlyStorageError(
                    f"database schema must be migrated to version {self.schema_version}"
                )
        except (OSError, sqlite3.Error, ReadOnlyStorageError, ValueError) as exc:
            try:
                self._connection.close()
            except AttributeError:
                pass
            if isinstance(exc, ReadOnlyStorageError):
                raise
            raise ReadOnlyStorageError("could not open the SQLite database read-only") from exc

    def _migrate(self) -> None:
        """Reject direct migration attempts instead of relying on side effects."""

        raise ReadOnlyStorageError("schema migrations are unavailable in read-only storage")

    def __enter__(self) -> "ReadOnlySQLiteStorage":
        return self


__all__ = ["ReadOnlySQLiteStorage", "ReadOnlyStorageError"]
