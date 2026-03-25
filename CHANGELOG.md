# Changelog

All notable changes to PaperTrail are documented in this file.

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
