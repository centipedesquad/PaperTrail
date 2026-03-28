# Changelog

All notable changes to PaperTrail are documented in this file.

## v0.6.4 — 2026-03-28

### Changed

- `run.sh` and `build_app.sh` now auto-create a local `.venv` and install required dependencies when missing
- Build and installation docs now point to `src/PaperTrail.spec`, document macOS 11+ support, and clarify architecture-specific app builds
- Application metadata and About dialog updated for version `0.6.4`

### Fixed

- Running or building from a fresh checkout no longer requires manually creating the virtual environment first

## v0.6.3 — 2026-03-27

### Changed

- Refactored the code for migrating old databases.

## v0.6.2 — 2026-03-27

### Fixed

- FTS5 author search completely broken — contentless table triggers used invalid UPDATE syntax, now use correct delete-then-reinsert with exact value matching
- Corrupt database recovery could infinitely recurse and crash the app
- PDF downloads could silently overwrite another paper's file on filename collision
- Database write failures (disk full, schema errors) misreported as "paper already exists"
- arXiv search swallowed all exceptions, preventing retry logic from working
- arXiv preview/search network errors shown as "Not Found" instead of proper error messages
- Theme toggle only partially updated widgets — main window now subscribes to theme listener
- Cache cleanup skipped subdirectories, leaving orphaned folders
- Ctrl+F opened Fetch dialog instead of focusing search bar (now Ctrl+F = search, Ctrl+Shift+F = fetch)
- "All Papers" count temporarily wrong after category refresh (double-counted multi-category papers)
- Fetch dialog ignored saved preferences, always starting with defaults
- Migration file numbering collision caused FTS5 fix to be silently skipped on upgrades
- Imported view search ignored origin filter, showing all papers instead of imports only
- Batch import error count not shown in status bar
- Test suite updated for new batch creation return type

### Changed

- `PaperRepository.create()` now only catches `sqlite3.IntegrityError` — other errors propagate
- `create_papers_batch()` returns `{created, duplicates, errors}` dict instead of bare int
- FTS5 triggers use BEFORE DELETE/UPDATE to ensure author data is available for exact-match deletes

## v0.6.1 — 2026-03-26

### Fixed

- Crash fix for new databases

## v0.6.0 — 2026-03-25

### Added

- Three-metric rating system (importance, comprehension, technicality) with auto-save
- Inline note editor with auto-save and full-text search across notes
- Full-text search powered by FTS5 across titles, abstracts, and authors
- Advanced filtering by category, date range, rating status, and PDF availability
- Flexible sorting (newest/oldest, title A-Z/Z-A)
- Hierarchical category organization with smart grouping (Physics, CS, Math, etc.)
- Three-column layout with nav rail, paper feed, and context panel
- Editorial design system with bundled fonts (DM Sans, Source Serif 4, JetBrains Mono)
- Light/dark theme system with Ctrl+T toggle
- Preferences dialog (theme, font size, PDF settings, fetch defaults)
- Delete local PDF with confirmation dialog
- Loading indicators and tooltips throughout the UI
- Error handling layer with retry logic, integrity checks, and input validation
- App icon (AppIcon.icns / AppIcon.png)
- PyInstaller build system with build and install scripts
- Git hooks for workflow enforcement (secrets, branch rules, release tagging)
- Comprehensive test suite (117 tests)

### Changed

- Renamed application from myArXiv to PaperTrail
- Switched from requirements.txt to pyproject.toml with uv sync
- License changed from MIT to AGPL-3.0-only
- Batch-load related data to eliminate N+1 query performance issues
- Fetch service now only returns papers with primary category matching selection
- Fetch new papers mode limited to today's submissions only
- Reduced API request multiplier and added rate limiting error handling
- Multi-select categories in nav rail
- Wider splitter handle and resizable panel defaults
- Full abstract expands in-place when paper is selected

### Fixed

- PDF viewer no longer blocks on database operations
- Crash bugs and thread safety issues resolved
- Fetch dialog progress and completion updates wired correctly
- Font size setting now applies to UI
- Preferences dialog layout and visual issues
- Button text sizing and removal of gaudy borders
- Author search indexing (migration 002)
- Date filter regression

## v0.3.0 — 2026-02-09

Initial public release with Phases 1-3 complete.

- arXiv paper fetching by subject class
- Paper metadata storage with SQLite and FTS5
- PDF download, streaming, and reader integration (Skim/evince)
- Customizable PDF naming patterns
- Cross-platform support (macOS and Linux)
