# bear-mcp

MCP server that gives LLMs fast, read-only access to your Bear notes by reading the SQLite database directly.

## How it works

Bear stores notes in a Core Data SQLite file on disk. This server opens it read-only (`?mode=ro`) and queries it directly. No network calls, no CloudKit sync latency, no API keys. Queries against the tag index instead of scanning note content.

## Why this exists

The existing Bear MCP options either go through Bear's x-callback-url scheme (slow, requires Bear to be running, macOS UI automation) or the akseyh implementation that builds SQL with string concatenation. I wanted something that's fast, read-only by design, and doesn't have SQL injection issues.

Limitations:
- **macOS only** — Bear is a macOS/iOS app, the SQLite file lives on macOS
- **Read-only** — this server cannot create, edit, or delete notes
- **Needs Full Disk Access** — the process reading Bear's database needs FDA granted in System Settings > Privacy & Security

## Install

```bash
pip install git+https://github.com/mark-liu/bear-mcp.git
```

Or run without installing:

```bash
uvx --from git+https://github.com/mark-liu/bear-mcp.git bear-mcp
```

PyPI coming soon — `pip install bear-mcp` once published.

## Configure in Claude Code

```bash
claude mcp add bear -s user -- uvx --from git+https://github.com/mark-liu/bear-mcp.git bear-mcp
```

## Tools

| Tool | Description |
|------|-------------|
| `search_bear_notes` | Search notes by text and/or tag (uses tag index, not text scan) |
| `get_bear_note` | Get a specific note by UUID |
| `list_bear_tags` | List all tags (reads ZSFNOTETAG table directly) |
| `find_notes_by_title` | Find notes by title, exact or partial match |
| `get_recent_notes` | Get notes modified in the last N days |

## License

MIT
