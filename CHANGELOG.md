# Changelog

All notable changes to PaperTrail are documented in this file.

## v0.9.1 — 2026-06-13

### Changed

- Bumped PaperTrail metadata, About dialog, and build documentation from 0.9.0 to 0.9.1.
- Linked the implementation log and deployment guide from the README documentation section.

### Fixed

- Deleting or pruning a paper that had authors corrupted the FTS5 index ("database disk image is malformed") and aborted the operation: the `paper_authors` cascade fired the author-delete trigger after the paper's FTS row was already removed. Added a `WHEN EXISTS` parent-paper guard to the trigger and a `fix_fts_author_delete_guard` migration to repair existing databases. Per-paper Remove and prune now work for any authored paper.
- Pruning destroyed fetched papers whose LaTeX source archive had been permanently downloaded (PDF still absent), deleting an engaged-with paper and orphaning its extracted source directory. Prune now also requires `local_source_path` to be NULL, so it only removes genuinely untouched fetches.
- Clearing a rating metric back to "Not rated" was silently ignored — the UPSERT's `COALESCE` fell back to the stored value and the stale rating reappeared on reload. A `RATING_UNSET` sentinel now distinguishes an omitted metric (left unchanged) from an explicit clear (written as NULL).
- A note typed within the 2-second auto-save debounce was lost when the app closed; `closeEvent` now flushes the pending save before shutting down.
- A closed database connection silently reopened on the next `execute()`/`connect()`, letting a worker that outlived a library relocation resurrect a connection to the old database file. `close()` is now final and post-close access raises.
- Library relocation/merge could close the database while a download worker was still running, racing the copy/merge. `_stop_all_workers()` now reports whether every worker actually stopped, and the change-library dialog aborts with a warning if a download will not stop in time.
- Merging with "keep both" (or any non-duplicate copy) could overwrite an existing destination file when the filename lacked the arXiv ID or used a legacy slash ID — de-collision relied on string-substituting the arXiv ID into the path. Collisions are now resolved structurally by appending `_copy`/`_copyN`, and paths claimed earlier in the same merge are tracked to avoid intra-merge clobbering.
- Merging into an older-schema destination library failed with "no such column"; `merge_library` now brings the destination schema up to date (running migrations) before inserting.
- Merging two databases that share one files directory crashed with `shutil.SameFileError`; copying a file onto itself is now skipped.
- A merge committed its database inserts before copying files, so a copy failure (disk full, permission) left the destination database referencing files that were never copied while the UI reported the library unchanged. Files are now copied inside the transaction, so any failure rolls the database back.
- Cancelling a PDF or source download left the wait cursor stuck and could surface a scary failure dialog. The download now re-raises so the worker emits its terminal signal (restoring the cursor), and the error handlers suppress the dialog for user-initiated cancellation, showing a brief status message instead.
- The manual prune result was reported via the status bar, which `_load_papers` immediately overwrote, so the user never saw how many papers were removed. The count is now shown in a dialog after the reload.

## v0.9.0 — 2026-06-13

### Added

- Added manual pruning for old batch-fetched papers that have no saved PDF, including a sidebar action, confirmation dialog, configurable age threshold, and status refresh after pruning.
- Added optional startup auto-pruning with Preferences controls for enabling the behavior and choosing the pruning threshold.
- Added an individual "Remove Paper" action in the context panel that deletes the database record and associated local PDF/source files.
- Added repository and service support for paper deletion and pruning, relying on cascade/FTS cleanup for related data.
- Added a pytest suite covering database repositories, service behavior, migrations, library relocation and merge workflows, filename utilities, and regression cases for FTS5 searches, batch imports, and concurrent database access.
- Added shared test fixtures for isolated migrated test databases and reusable sample paper records.

### Changed

- Bumped PaperTrail metadata, About dialog, and build documentation from 0.8.0 to 0.9.0.

## v0.8.0 — 2026-04-07

### Added

- Library relocation: move your database and files directories to new locations via Preferences > Storage
- Three migration modes: Export (copy library), Create New (fresh library), and Merge (combine libraries)
- Split paths: database and files directories can be set independently (e.g., database on local SSD, PDFs in synced folder)
- Library merge with duplicate detection by arXiv ID and three conflict resolution strategies (keep existing, keep incoming, keep both)
- Merge conflict dialog for choosing duplicate resolution strategy
- Progress bar and cancellation support during library migration
- "Show in Finder" for current and previous library locations in the Storage tab
- Previous library path display after migration for easy cleanup
- `LibraryMigrationWorker` for non-blocking background migrations
- `open_directory()` cross-platform utility (macOS Finder / Linux file managers)
- Storage tab in Preferences dialog showing library locations and migration controls

## v0.7.1 — 2026-04-01

### Changed

- Version bumped to 0.7.1
- Removed `install.sh` — installation is handled by `build_app.sh` and documented in README
- Added changelog for v0.7.0

## v0.7.0 — 2026-04-01

### Added

- Smart search with arXiv fallback: when local results are empty, a "Search arXiv" button appears; when results exist, an option is appended at the bottom of the feed
- arXiv ID search: paste an arXiv ID into the search bar to preview the paper and import it in one click
- arXiv query search: search arXiv by keyword and browse results in a multi-select dialog for batch import
- Source file downloads: download and extract arXiv LaTeX source archives (e-print) with permanent or cached storage
- "Show in Finder" button to reveal downloaded PDFs in the system file manager
- Paper origin tracking: papers are tagged as `fetch` or `search` with corresponding filter in the sidebar
- Library counts (total and imported) displayed in the filter panel
- New background workers: `ArxivIdWorker`, `ArxivSearchWorker`, `SourceDownloadWorker`
- `SourceService` for the full source file lifecycle (download, extract, open, delete)
- `ArxivSearchResultsDialog` for browsing and selectively importing arXiv search results
- `reveal_in_file_manager()` and `get_file_manager_name()` platform utilities
- `FilenameGenerator.generate_folder_name()` for source directories
- `download_utils` module for shared HTTP download logic

### Fixed

- FTS5 `GROUP_CONCAT` ignored `ORDER BY` inside aggregate — wrapped in subqueries so author ordering is deterministic
- Notes FTS triggers did not fire correctly on insert/delete
- Corrupt-database recovery silently reconnected to an empty database — now raises so the app restarts cleanly
- Transaction context manager could leak the lock on unexpected errors — now uses `with self._lock`
- PDF downloads were not atomic — now write to a `.part` temp file and rename on success
- Worker cleanup on timeout leaked signals — now disconnects signals before discarding the worker
- Batch paper creation miscounted on transaction failure — error handling now resets counters

### Changed

- Search bar now checks for arXiv ID patterns before falling back to text search
- `search_papers()` accepts `origin` and `include_downloaded` filter parameters
- Stale arXiv search results are rejected via a generation counter
- Context panel groups PDF actions (open, show in finder, delete) and adds a Source section
- README updated with smart search, source file, and arXiv fallback documentation
- Four new database migrations: `add_local_source_path`, `add_origin_column`, `fix_fts5_group_concat_order`, `fix_notes_fts_triggers`

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
