#!/usr/bin/env python3
"""
Bear App MCP Server — read-only access to Bear notes via direct SQLite.

Reads Bear's Core Data SQLite database directly. No network calls, no API keys,
no CloudKit latency. Requires macOS with Bear installed and Full Disk Access
for the process reading the database.

The database uses Core Data timestamps (seconds since 2001-01-01 00:00:00 UTC).
"""

import datetime
import os
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

BEAR_DB_PATH = os.path.expanduser(
    "~/Library/Group Containers/9K33E3U3T4.net.shinyfrog.bear"
    "/Application Data/database.sqlite"
)

_CORE_DATA_EPOCH = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)

mcp = FastMCP("Bear Notes")

# Shared connection — opened lazily on first call, reused thereafter.
# check_same_thread=False because MCP may dispatch tool calls from
# different threads.
_shared_conn: sqlite3.Connection | None = None


def _get_connection() -> sqlite3.Connection:
    """Return the shared read-only connection, creating it on first call."""
    global _shared_conn
    if _shared_conn is None:
        if not os.path.exists(BEAR_DB_PATH):
            raise FileNotFoundError(f"Bear database not found: {BEAR_DB_PATH}")
        _shared_conn = sqlite3.connect(
            f"file:{BEAR_DB_PATH}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        _shared_conn.row_factory = sqlite3.Row
    return _shared_conn


def _note_row_to_dict(row: sqlite3.Row, *, include_content: bool = True) -> dict[str, Any]:
    """Convert a ZSFNOTE row to a serialisable dict."""
    content = row["content"] or ""
    result: dict[str, Any] = {
        "id": row["id"],
        "title": row["title"] or "Untitled",
        "created_date": row["created_date"],
        "modified_date": row["modified_date"],
        "word_count": len(content.split()) if content else 0,
    }
    if include_content:
        result["content"] = content
    result["preview"] = content[:200] + "..." if len(content) > 200 else content
    return result


# ── SQL fragments ───────────────────────────────────────────────────────────

_NOTE_COLUMNS = """
    ZUNIQUEIDENTIFIER AS id,
    ZTITLE            AS title,
    ZTEXT             AS content,
    ZCREATIONDATE     AS created_date,
    ZMODIFICATIONDATE AS modified_date
"""

_NOT_TRASHED = "ZTRASHED = 0"


# ── Tools ───────────────────────────────────────────────────────────────────

@mcp.tool()
def search_bear_notes(
    query: str = "",
    tag: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search Bear notes by text and/or tag.

    Args:
        query: Text to search for in title and content.
        tag: Tag to filter by (without the # prefix). Uses the tag index, not text search.
        limit: Maximum results to return.
    """
    conn = _get_connection()
    try:
        params: list[Any] = []

        if tag:
            # Join through the note-tag relationship table for indexed lookup.
            # Z_5TAGS maps note Z_PK (Z_5NOTES) to tag Z_PK (Z_13TAGS).
            sql = f"""
                SELECT {_NOTE_COLUMNS}
                FROM ZSFNOTE
                INNER JOIN Z_5TAGS   ON Z_5TAGS.Z_5NOTES  = ZSFNOTE.Z_PK
                INNER JOIN ZSFNOTETAG ON ZSFNOTETAG.Z_PK   = Z_5TAGS.Z_13TAGS
                WHERE {_NOT_TRASHED}
                  AND ZSFNOTETAG.ZTITLE = ?
            """
            params.append(tag)
        else:
            sql = f"""
                SELECT {_NOTE_COLUMNS}
                FROM ZSFNOTE
                WHERE {_NOT_TRASHED}
            """

        if query:
            sql += " AND (ZTITLE LIKE ? OR ZTEXT LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        sql += " ORDER BY ZMODIFICATIONDATE DESC LIMIT ?"
        params.append(limit)

        return [_note_row_to_dict(row) for row in conn.execute(sql, params).fetchall()]
    except Exception as e:
        return [{"error": f"Search error: {e}"}]


@mcp.tool()
def get_bear_note(note_id: str) -> dict[str, Any]:
    """Get a specific Bear note by its unique identifier.

    Args:
        note_id: The note's unique identifier (UUID).
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            f"SELECT {_NOTE_COLUMNS} FROM ZSFNOTE WHERE ZUNIQUEIDENTIFIER = ? AND {_NOT_TRASHED}",
            (note_id,),
        ).fetchone()
        return _note_row_to_dict(row) if row else {"error": "Note not found"}
    except Exception as e:
        return {"error": f"Error retrieving note: {e}"}


@mcp.tool()
def list_bear_tags() -> list[str]:
    """List all tags in Bear.

    Reads from the ZSFNOTETAG table directly — no full-text scan.
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT t.ZTITLE
            FROM ZSFNOTETAG t
            INNER JOIN Z_5TAGS jt ON jt.Z_13TAGS = t.Z_PK
            INNER JOIN ZSFNOTE n  ON n.Z_PK = jt.Z_5NOTES
            WHERE n.ZTRASHED = 0
            ORDER BY t.ZTITLE
            """
        ).fetchall()
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        return [f"Error listing tags: {e}"]


@mcp.tool()
def find_notes_by_title(
    title_query: str,
    exact_match: bool = False,
) -> list[dict[str, Any]]:
    """Find notes by title.

    Args:
        title_query: Title text to search for.
        exact_match: If true, match the title exactly; otherwise partial match.
    """
    conn = _get_connection()
    try:
        if exact_match:
            where = f"{_NOT_TRASHED} AND ZTITLE = ?"
            params: list[Any] = [title_query]
        else:
            where = f"{_NOT_TRASHED} AND ZTITLE LIKE ?"
            params = [f"%{title_query}%"]

        rows = conn.execute(
            f"SELECT {_NOTE_COLUMNS} FROM ZSFNOTE WHERE {where} ORDER BY ZMODIFICATIONDATE DESC",
            params,
        ).fetchall()
        return [_note_row_to_dict(row) for row in rows]
    except Exception as e:
        return [{"error": f"Error searching by title: {e}"}]


@mcp.tool()
def get_recent_notes(days: int = 7, limit: int = 20) -> list[dict[str, Any]]:
    """Get recently modified notes.

    Args:
        days: Number of days to look back.
        limit: Maximum results to return.
    """
    conn = _get_connection()
    try:
        cutoff = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days) - _CORE_DATA_EPOCH
        ).total_seconds()

        rows = conn.execute(
            f"""
            SELECT {_NOTE_COLUMNS}
            FROM ZSFNOTE
            WHERE {_NOT_TRASHED} AND ZMODIFICATIONDATE > ?
            ORDER BY ZMODIFICATIONDATE DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [_note_row_to_dict(row) for row in rows]
    except Exception as e:
        return [{"error": f"Error getting recent notes: {e}"}]


def main() -> None:
    """Entry point for the bear-mcp server."""
    mcp.run()


if __name__ == "__main__":
    main()
