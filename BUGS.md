# Open Bugs - PaperTrail

*Last audited: 2026-03-27 — Round 4 by Claude (Opus 4.6) + Codex (GPT-5.4)*

Bugs found by **[BOTH]** models are highest confidence.

---

## HIGH

### Bug #1: Transaction Lock Deadlock on connect() Failure

**Status:** FIXED
**Severity:** High — App freezes permanently
**Found by:** Codex (round 4)

`transaction()` acquires `_lock` before calling `connect()`. If `connect()` raises (e.g., during DB recovery), the `try/finally` hasn't started yet, so the lock is never released. Every subsequent DB call deadlocks.

**User impact:** If the database connection drops (e.g. disk full, file locked), the app freezes permanently. Every subsequent database operation queues behind a lock that will never be released. The only recovery is force-quitting.

**Fix:** Replaced explicit `acquire()`/`release()` with `with self._lock:` context manager, matching the pattern used by adjacent methods. `connect()` is now inside the guarded block, so any exception always releases the lock.

**Files:** `src/database/connection.py` — `transaction()` (line ~222)

---

### Bug #2: Migration executescript Partial Apply Can Advance Schema Version

**Status:** FIXED
**Severity:** High — Silent partial migration
**Found by:** Codex (round 4)

`migration_manager.py` runs migrations with `executescript()` and treats "duplicate column name" as success. If a migration partially applies, the manager may still advance the schema version.

**User impact:** During a version upgrade, if a migration SQL file half-succeeds, the app may believe the migration completed. On next launch the broken migration is skipped, leaving the database in a corrupted schema state that causes mysterious query failures.

**Fix:** Schema version now derives from introspection: counts how many migrations' `needs_run()` returns False after the migration loop, reflecting actual schema state rather than assuming all migrations in the registry were applied.

**Files:** `src/database/migration_manager.py` (lines ~49-58)

---

### Bug #3: GROUP_CONCAT ORDER BY Not Guaranteed in FTS5 Triggers

**Status:** FIXED
**Severity:** High — FTS5 delete may miss rows with different author ordering
**Found by:** Codex (round 4)

`GROUP_CONCAT(a.name, ' ') ... ORDER BY pa.author_order` in the same aggregate query does not guarantee order in SQLite. The delete command requires exact value match, so ordering drift can leave stale FTS entries.

**User impact:** When a paper's authors are reordered or updated, the FTS5 delete command may not match the stored value. The old entry stays in the search index, causing phantom search results for papers that no longer match the query.

**Fix:** All 7 GROUP_CONCAT instances in FTS5_TRIGGER_SQL wrapped in ordered subqueries: `GROUP_CONCAT(name, ' ') FROM (SELECT ... ORDER BY author_order)`. New migration `fix_fts5_group_concat_order` drops and recreates triggers on existing databases.

**Files:** `src/database/migrations/__init__.py`, `src/database/migrations/fix_fts5_group_concat_order.py`

---

### Bug #4: Batch Create Reports Success After Transaction Rollback `[BOTH]`

**Status:** FIXED
**Severity:** High — UI reports papers created when none were saved
**Found by:** Both (round 4)

`create_papers_batch()` increments counters inside a transaction. If one paper fails, the transaction rolls back ALL prior inserts, but the returned counts still claim papers were created.

**User impact:** If a batch import fails partway through, the database correctly rolls back all inserts — but the UI still reports papers were created. The user believes their import worked when nothing was actually saved.

**Fix:** On exception (after transaction rollback), reset `created_count` and `duplicate_count` to 0 and set `error_count` to the total batch size so the returned dict accurately reflects that nothing was saved.

**Files:** `src/services/paper_service.py` — `create_papers_batch()` (line ~63)

---

### Bug #5: Worker Cleanup Race — Old Worker Can Mutate UI

**Status:** OPEN
**Severity:** High — Stale operations affect current UI state
**Found by:** Codex (round 4)

`_cleanup_worker()` gives up after 2s timeout, but callers overwrite the worker attribute. The old thread keeps signal connections and can later mutate UI from a stale operation.

**Fix:** Return success/failure from cleanup and refuse replacement until old worker is fully disconnected.

**Files:** `src/ui/main_window.py` — `_cleanup_worker()` (line ~213)

---

### Bug #6: _on_cell_clicked Crashes When Non-PaperCellWidget in paper_cells `[BOTH]`

**Status:** OPEN
**Severity:** High — App crash on paper click after search
**Found by:** Claude (round 4)

`append_arxiv_search_option()` adds a plain QWidget to `paper_cells`. When user clicks any paper card, `_on_cell_clicked` iterates the list and calls `cell.paper.id` on the QWidget — `AttributeError` crash.

**Fix:** Add `isinstance(cell, PaperCellWidget)` check in the loop, or keep separate list.

**Files:** `src/ui/widgets/paper_feed_widget.py` (lines ~179, ~272)

---

### Bug #19: Partial Rating Update Overwrites Other Dimensions with NULL

**Status:** FIXED
**Severity:** High — Silent data loss on ratings
**Found by:** Claude (round 5 — migration hardening)

`RatingsRepository.create_or_update()` uses `ON CONFLICT DO UPDATE SET importance = excluded.importance, ...` which unconditionally overwrites all three fields. When a user updates only one dimension (e.g. comprehension), the other dimensions are passed as `None` and overwrite previously saved values.

**Repro:** Call `create_or_update(paper_id, importance="good")`, then `create_or_update(paper_id, comprehension="understood")`. The second call wipes `importance` to `None`.

**User impact:** If a user rates a paper's importance, then later rates its comprehension, the second save silently wipes the importance rating to NULL. Over time, users lose ratings they've already set without any indication.

**Fix:** Added `COALESCE(excluded.X, paper_ratings.X)` in the ON CONFLICT clause so NULL parameters preserve existing values instead of overwriting them.

**Files:** `src/database/repositories.py` — `RatingsRepository.create_or_update()` (line ~578)

---

## MEDIUM

### Bug #7: notes_fts Uses Plain DELETE/UPDATE on External-Content FTS5

**Status:** OPEN
**Severity:** Medium — Old note terms remain searchable after edit/delete
**Found by:** Codex (round 4)

`001_initial_schema.sql` maintains `notes_fts` with plain DELETE/UPDATE against an FTS5 external-content table. Old tokens are not removed correctly.

**User impact:** When a user edits or deletes a note, the old text remains searchable. Searching for a phrase from a deleted or edited note still returns that paper as a match, making search results unreliable.

**Fix:** Use the same FTS5 `'delete'` + reinsert pattern used for `papers_fts`.

**Files:** `src/database/migrations/001_initial_schema.sql` (lines ~174, ~178)

---

### Bug #8: Partial PDF Downloads Leave Orphaned Files `[BOTH]`

**Status:** OPEN
**Severity:** Medium — Orphaned partial files accumulate, collision logic triggered
**Found by:** Both (round 4)

`pdf_service.py` writes directly to the final path. Cancel/failure leaves partial PDFs. Retries generate suffixed filenames because the orphan already exists.

**User impact:** If a PDF download is cancelled or fails mid-stream, a partial (unreadable) file is left on disk. Retries generate suffixed filenames because the orphan already exists, so partial files accumulate and waste disk space.

**Fix:** Download into `*.part` temp file, remove on failure, atomically rename on success.

**Files:** `src/services/pdf_service.py` (line ~120)

---

### Bug #9: Source Service Legacy ID Paths Not Fully Sanitized `[BOTH]`

**Status:** FIXED
**Severity:** Medium — Legacy arXiv IDs with `/` break non-tar source extraction
**Found by:** Both (round 4)

`source_service.py` uses raw `arxiv_id` in filenames for gzip/PDF/single-file extraction. Legacy IDs like `hep-th/9901001` create paths with missing intermediate directories.

**User impact:** Papers with legacy arXiv IDs containing `/` (e.g. `hep-th/9901001`) fail during source extraction because the raw ID creates paths with nonexistent intermediate directories. Users get a cryptic file-not-found error when viewing source files for older papers.

**Fix:** `_extract_archive` now sanitizes `arxiv_id` with `replace('/', '_')` at the top of the method and uses the sanitized `safe_id` for all three filename construction paths (gzip, PDF, single-file).

**Files:** `src/services/source_service.py` (lines ~103, ~146, ~153, ~157)

---

### Bug #10: PDF/Source Download Overwrites Current Context Panel Selection

**Status:** OPEN
**Severity:** Medium — UI jumps back to old paper unexpectedly
**Found by:** Codex (round 4)

When a PDF/source download finishes, the context panel always reloads the paper that initiated the download. If the user selected a different paper while waiting, the UI jumps back.

**User impact:** If a user starts a download on paper A then navigates to paper B while waiting, the context panel jumps back to paper A when the download finishes. The user's current selection is unexpectedly overwritten.

**Fix:** Only refresh context panel if the finished paper is still the selected one.

**Files:** `src/ui/main_window.py` (lines ~654, ~809)

---

### Bug #11: IntegrityError Catch Too Broad in create()

**Status:** OPEN
**Severity:** Medium — Non-duplicate constraint errors hidden
**Found by:** Codex (round 4)

`PaperRepository.create()` catches all `sqlite3.IntegrityError` as "duplicate". Real constraint violations (NOT NULL, foreign key) are hidden.

**User impact:** Any database constraint violation during paper creation (NOT NULL, foreign key) is silently swallowed and logged as "Duplicate paper." Real data integrity problems are invisible to both users and developers debugging issues.

**Fix:** Inspect exception for UNIQUE on `papers.arxiv_id`; re-raise others.

**Files:** `src/database/repositories.py` (line ~60)

---

### Bug #12: arXiv Error Callbacks Not Generation-Guarded `[BOTH]`

**Status:** FIXED
**Severity:** Medium — Stale error can replace current UI
**Found by:** Both (round 4)

arXiv success handlers are generation-guarded, but error handlers are not. A cancelled search can show a stale error message.

**User impact:** If a user starts an arXiv search, cancels it, and starts a new one, the first search's error response can arrive late and overwrite the UI with a stale "Could not reach arXiv" message — even though the second search is succeeding.

**Fix:** Both `_on_arxiv_id_error` and `_on_arxiv_search_error` now accept a `generation` parameter and check it against `_search_generation` before acting. The error lambdas capture generation by value via default arg.

**Files:** `src/ui/main_window.py` (lines ~422-424, ~442-444, ~482-484, ~502-504)

---

### Bug #13: fetch_recent_papers Cross-Lists Not Filtered by Primary Category

**Status:** OPEN
**Severity:** Medium — Wrong papers shown in category fetch
**Found by:** Codex (round 4)

`fetch_recent_papers()` doesn't enforce `primary_category == category` like `fetch_new_papers()` does. Cross-listed papers leak into fetches.

**User impact:** When fetching recent papers for a specific category (e.g. `cs.AI`), papers merely cross-listed into that category but primarily belonging to another field leak into the results. Users see off-topic papers mixed into their feed.

**Fix:** Apply the same primary-category filter in both paths.

**Files:** `src/api/arxiv_client.py` (line ~107)

---

### Bug #14: Runtime Corruption Detection Recreates DB Without Tables

**Status:** OPEN
**Severity:** Medium — Data loss + crash if corruption detected at runtime
**Found by:** Claude (round 4)

If database corruption is detected at runtime (not startup), `_handle_corrupt_database` creates a fresh DB but no migrations are triggered, leaving an empty database.

**User impact:** If database corruption is detected while the app is already running, the recovery handler creates a fresh database file but never runs migrations. The result is an empty database with no tables — every subsequent operation crashes until the user manually restarts.

**Fix:** Trigger migrations after recovery or raise error prompting restart.

**Files:** `src/database/connection.py` — `_handle_corrupt_database()`

---

## LOW

### Bug #15: local_pdf_path IS NOT NULL Treated as "Downloaded"

**Status:** OPEN
**Severity:** Low — Filters/counts lie if files moved/deleted outside app
**Found by:** Codex (round 4)

Filters use `local_pdf_path IS NOT NULL` as proxy for "downloaded". If files are deleted externally, the filter lies.

**User impact:** If a user moves or deletes a PDF outside the app, PaperTrail still shows the paper as "downloaded" in filters and counts. Clicking "Open PDF" then fails because the file no longer exists.

**Fix:** Reconcile stale paths on access.

**Files:** `src/database/repositories.py` (lines ~259, ~414)

---

### Bug #16: Migration Version String Comparison Breaks at 100+

**Status:** OPEN
**Severity:** Low — Latent: not yet triggered
**Found by:** Claude (round 4)

Version comparison uses string ordering. `"9" > "10"` in string comparison. Currently safe with 3-digit zero-padded numbers.

**User impact:** Currently latent. If the project ever reaches migration 100+, string comparison would rank "9" above "10". Migrations would run out of order or be skipped, silently corrupting the schema on upgrade. A trap for future developers.

**Fix:** Compare as integers: `int(version) > int(current_version)`.

**Files:** `src/database/migration_manager.py` (lines ~72, ~132)

---

### Bug #17: Theme Toggle Applies Stylesheet Twice

**Status:** OPEN
**Severity:** Low — Minor performance waste
**Found by:** Claude (round 4)

`_toggle_theme()` calls `set_theme()` which notifies the listener (calling `apply_to_app`), then also calls `apply_to_app` directly.

**User impact:** Every time the user toggles light/dark mode, the entire application stylesheet is recomputed and applied twice. Minor performance waste — the user may notice a brief flicker on slower machines, but no functional impact.

**Fix:** Remove the explicit `apply_to_app()` call since the listener handles it.

**Files:** `src/ui/main_window.py` — `_toggle_theme()` (line ~200)

---

### Bug #18: clear_papers() Doesn't Remove Widgets from Layout

**Status:** OPEN
**Severity:** Low — Brief visual flicker during feed refresh
**Found by:** Claude (round 4)

`deleteLater()` is called but widgets aren't removed from `container_layout`. Old and new widgets coexist briefly.

**User impact:** When the feed refreshes, old paper cards are scheduled for deletion but remain visible in the layout until Qt processes the deferred delete. Users may see a brief flicker where old and new cards overlap.

**Fix:** Call `self.container_layout.removeWidget(cell)` before `deleteLater()`.

**Files:** `src/ui/widgets/paper_feed_widget.py` — `clear_papers()` (line ~156)

---

### Bug #19: Corrupted .venv Directory Silently Breaks Auto-Creation

**Status:** OPEN
**Severity:** Low — Edge case: requires manually broken .venv
**Found by:** Claude + Codex (build/install review, round 2)

`run.sh` and `build_app.sh` check `[ -d ".venv" ] && [ -f ".venv/bin/activate" ]`. Two failure modes:
1. `.venv/` exists but `bin/activate` is missing: falls to `else` branch, `python -m venv .venv` may produce unexpected results over partial directory contents.
2. `.venv/bin/activate` exists but Python inside is broken: takes `if` branch, activates corrupted venv, `python main.py` fails with confusing errors.

**User impact:** If `.venv` is partially corrupted (e.g. missing `bin/activate` or broken Python binary), the run/build scripts either create a venv over a broken directory or activate a broken one. The user gets confusing errors with no indication that the venv is the problem.

**Fix:** In the `else` branch, `rm -rf .venv` before creating a new one. In the `if` branch, verify the venv Python works after activation.

**Files:** `run.sh` (line ~7), `build_app.sh` (line ~34)

---

## Previously Fixed Bugs

### Round 1 — 9 bugs fixed
### Round 2 — 20 bugs fixed
### Round 3 — 14 bugs fixed
### Round 4 — 13 bugs fixed (1 false positive closed)
### Round 5 (review) — 2 bugs fixed (#9, #12)

**Total: 58 bugs fixed across 5 rounds.**

---

## Fixed Bugs — User-Facing Impact

Grouped by how the user would experience the bug.

| User Impact | ID | Bug | Severity |
|---|---|---|---|
| **Search returns wrong/phantom results** | | | |
| | R1-7 | Stale ArxivIdWorker shows old paper's preview | Medium |
| | R2-1 | FTS5 mismatch — deleted papers appear in search | Critical |
| | R2-11 | ArxivSearch stale results — old search dialog appears | Medium |
| | R3-1 | FTS5 content=papers crashes all searching | High |
| | R3-2 | Migration collision — upgrading users never get FTS5 fix | High |
| | R4-1 | FTS5 author UPDATE invalid on contentless table — author search broken | Critical |
| | R4-7 | ArxivClient.search_papers swallows exceptions — retry never triggers | Medium |
| | R4-8 | Imported view search drops origin filter — shows wrong papers | Medium |
| | R5-3 | Stale arXiv error overwrites current search UI | Medium |
| | R6-4 | FTS5 GROUP_CONCAT ordering drift leaves phantom search results | High |
| **Search/filter state silently lost** | | | |
| | R1-8 | Clearing search bar resets category/date filters | Medium |
| | R2-15 | Category refresh after fetch wipes active filters | Medium |
| | R2-16 | After import, search bar shows query but feed shows all papers | Medium |
| | R3-8 | Category filter restore uses double prefix — never matches | Medium |
| **Wrong data displayed in UI** | | | |
| | R1-2 | Lambda captures stale paper — wrong PDF status shown | High |
| | R2-18 | primary_text fallback color — button text looks wrong | Medium |
| | R2-25 | Non-primary category badge shown on paper cards | Low |
| | R3-11 | Context panel shows details for paper no longer in feed | Medium |
| | R3-14 | Stale last_accessed timestamp after PDF open | Low |
| | R4-13 | set_categories wrong "All Papers" count (double-counts) | Low |
| **Notes saved to wrong paper or lost** | | | |
| | R2-4 | Note timer fires after paper switch — saves to wrong paper | High |
| | R3-3 | set_paper ordering — flush fires against new paper's ID | High |
| | R4-2 | Note auto-save flush — verified as FALSE POSITIVE (no bug) | — |
| **Downloads fail or show wrong feedback** | | | |
| | R1-5 | arXiv search fails on first transient error instead of retrying | Medium |
| | R1-10 | Progress bar stuck at 0% when Content-Length header missing | Low |
| | R2-10 | Source "stream" mode says ready but nothing opens | Medium |
| | R2-12 | Batch insert rollback still reports "Created 30 papers" | Medium |
| | R2-17 | Network timeout shown as "Paper not found" | Medium |
| | R2-22 | Fetch completion popup hidden behind dialog | Medium |
| | R3-6 | Legacy arXiv IDs (hep-th/...) fail PDF/source download entirely | Medium |
| | R5-2 | Legacy arXiv IDs break non-tar source extraction (missing dirs) | Medium |
| | R3-12 | Failed PDF download says "complete, failed to open" | Medium |
| | R4-5 | PDF filename collision — papers can silently overwrite each other | High |
| | R4-9 | arXiv preview/search failures shown as "Not Found" not error | Medium |
| | R6-3 | Batch create reports success after transaction rollback | High |
| **App hangs, crashes, or cursor stuck** | | | |
| | R2-2 | Closing app during download crashes with thread error | Critical |
| | R2-6 | Wait cursor permanently stuck after interrupted download | High |
| | R3-4 | Replacing blocked worker can destroy live thread | High |
| | R3-7 | Source path deleted before open — cursor stuck forever | Medium |
| | R4-3 | Corrupt DB recovery infinite recursion — stack overflow | Critical |
| | R6-1 | Transaction lock deadlock on connect() failure — app freezes permanently | High |
| **Data corruption or silent data loss** | | | |
| | R2-3 | SQL interleaving across threads can corrupt database | Critical |
| | R1-3 | HTTP response stream leak — sockets accumulate | High |
| | R2-9 | Same stream leak in PDFService code path | High |
| | R2-5 | Worker signals accumulate — memory leak over time | High |
| | R2-28 | After corruption recovery, WAL/foreign keys not re-enabled | Low |
| | R3-5 | executemany doesn't commit — future bulk ops would lose data | Medium |
| | R4-4 | Migration 003 prefix collision — second migration skipped | High |
| | R4-6 | Write failures reported as duplicates — real errors hidden | High |
| **Ratings don't work correctly** | | | |
| | R2-13 | Can't un-rate a paper — old values persist | Medium |
| | R3-9 | Cleared ratings still show paper as "Rated" in filters | Medium |
| | R6-2 | Partial rating update overwrites other dimensions with NULL | High |
| **arXiv fetch returns partial/wrong data** | | | |
| | R2-7 | Failed categories silently skipped — looks like no new papers | High |
| | R2-8 | Legacy IDs (hep-th/9901001) stored wrong — broken dedup/URLs | High |
| | R2-14 | Multi-category fetch only returns first category's papers | Medium |
| **Security vulnerabilities** | | | |
| | R1-4 | Malicious archive could write files outside extraction dir | High |
| | R2-21 | SQL injection vector in reset_database table names | Medium |
| **Visual/theme inconsistencies** | | | |
| | R2-19 | Theme toggle leaves most widgets in old colors | Medium |
| | R3-13 | Import buttons nearly invisible in dark mode | Low |
| | R2-24 | Unicode checkmark violates no-emoji guideline | Low |
| | R4-10 | Theme listener wired + Ctrl+F → search, Ctrl+Shift+F → fetch | Medium |
| **User preferences ignored** | | | |
| | R4-14 | Fetch dialog ignores saved preferences (mode, days, max) | Low |
| | R4-11 | cleanup_cache_dir skips subdirectories | Medium |
| **Platform/developer experience** | | | |
| | R2-26 | PDF reader picker broken on Linux | Low |
| | R2-27 | Searching "()!!" returns all papers instead of none | Low |
| | R2-29 | PDFDownloadWorker has unused parameters | Low |
| | R1-6 | Type hint says str but receives None | Low |
| | R2-23 | Same type hint issue at repository layer | Low |
| | R1-9 | Symlink-only archive shows "ready" but folder empty | Low |
| | R2-20 | VACUUM never runs — disk space not reclaimed | Medium |
| | R5-1 | Corrupted .venv silently breaks auto-creation in run/build scripts | Low |
