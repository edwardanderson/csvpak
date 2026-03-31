# csvpak

**csvpak** is a tool for packaging [CSV files](https://en.wikipedia.org/wiki/Comma-separated_values) as cross-platform standalone data editing applications.

It uses [redbean](https://redbean.dev/) to produce a single, portable executable that bundles the app and data; [CSV on the Web](https://csvw.org/) to describe column types and validation metadata in an open schema format; and [htmx](https://htmx.org/) to keep the editor UI server-driven and lightweight without a heavy front-end build step.

> [!WARNING]
> **csvpak** is just a prototype at this stage. It's not recommended for use in production.

## Installation

```bash
# Install in a project checkout (recommended during development)
uv sync

# Run via uv-managed environment
uv run csvpak --help
```

## Quickstart

```bash
# Build a new distributable — embeds a SQLite DB created from CSV + CSVW schema
uv run csvpak build \
   --data examples/contacts/contacts.csv \
   --schema examples/contacts/contacts.json \
   --output contacts.redbean.com

# Or build from schema only — initialises an empty SQLite DB with schema columns
uv run csvpak build \
   --schema examples/contacts/contacts.json \
   --output contacts-empty.redbean.com

# Run the distributable (edits are staged in a temporary SQLite file) on port 9000
./contacts.redbean.com -p 9000
```

Open <http://127.0.0.1:9000> in a web browser.

```bash
# Export the embedded data back to CSV
uv run csvpak export contacts.redbean.com --output path/to/file.csv

# Remove intermediary StoreAsset artefacts, keeping only the original DB and
# the most-recent saved version
uv run csvpak vacuum contacts.redbean.com
```

## How it works

1. **Build**
   Create a new a SQLite database from the CSVW schema, optionally importing CSV
   rows when `--data` is supplied, then embeds it in the redbean executable
   alongside the Lua webapp.
2. **Edit**
   When the distributable is run, the embedded SQLite is copied to a temporary file
   on the host system. All record edits are written there.
3. **Save**
   Clicking **Package data and exit** writes staged changes back into the
   distributable archive, removes the temporary file, and shuts the server down.
4. **Exit**
   Shutting down without saving keeps the temporary SQLite file so staged changes
   can be resumed next run.

## Features

- Single-file distribution via [redbean](https://redbean.dev/)
- CSV source data is converted into a structured SQLite dataset at build time
- Staged local editing: the embedded original is not modified during a session
- One-click packaging persists staged changes back into the distributable
- Exit-without-saving preserves staged edits for later resumption
- `csvpak export` writes the embedded dataset back to CSV
- `csvpak vacuum` compacts intermediary archive copies created by repeated saves
- Schema and dynamic forms driven by [CSVW](https://csvw.org/) metadata
- CSV import/export for interoperability with spreadsheets and other tools

## AI

> [!NOTE]
> **csvpak** was developed with the assistance of GitHub Copilot.
