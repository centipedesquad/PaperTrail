# Bugs — PaperTrail

*Last audited: 2026-04-01 — Round 7 by Claude (Opus 4.6)*

Bugs found by **[BOTH]** models are highest confidence.

---

## HIGH

No open HIGH severity bugs.

---

## MEDIUM

No open MEDIUM severity bugs.

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

### Bug #20: Corrupted .venv Directory Silently Breaks Auto-Creation

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

## Fixed Bugs — User-Facing Impact (71 total across 7 rounds)

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
| | R7-1 | notes_fts plain DELETE/UPDATE leaves stale tokens in search index | Medium |
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
| | R7-2 | Partial PDF downloads leave orphaned files on failure | Medium |
| | R7-3 | Download completion overwrites current paper selection | Medium |
| **App hangs, crashes, or cursor stuck** | | | |
| | R2-2 | Closing app during download crashes with thread error | Critical |
| | R2-6 | Wait cursor permanently stuck after interrupted download | High |
| | R3-4 | Replacing blocked worker can destroy live thread | High |
| | R3-7 | Source path deleted before open — cursor stuck forever | Medium |
| | R4-3 | Corrupt DB recovery infinite recursion — stack overflow | Critical |
| | R6-1 | Transaction lock deadlock on connect() failure — app freezes permanently | High |
| | R6-5 | Worker cleanup race — old worker mutates UI after replacement | High |
| | R6-6 | Clicking paper after search crashes on non-PaperCellWidget in list | High |
| | R7-4 | Runtime corruption recovery creates empty DB without tables | Medium |
| **Data corruption or silent data loss** | | | |
| | R2-3 | SQL interleaving across threads can corrupt database | Critical |
| | R1-3 | HTTP response stream leak — sockets accumulate | High |
| | R2-9 | Same stream leak in PDFService code path | High |
| | R2-5 | Worker signals accumulate — memory leak over time | High |
| | R2-28 | After corruption recovery, WAL/foreign keys not re-enabled | Low |
| | R3-5 | executemany doesn't commit — future bulk ops would lose data | Medium |
| | R4-4 | Migration 003 prefix collision — second migration skipped | High |
| | R4-6 | Write failures reported as duplicates — real errors hidden | High |
| | R7-5 | IntegrityError catch too broad — hides real constraint violations | Medium |
| **Ratings don't work correctly** | | | |
| | R2-13 | Can't un-rate a paper — old values persist | Medium |
| | R3-9 | Cleared ratings still show paper as "Rated" in filters | Medium |
| | R6-2 | Partial rating update overwrites other dimensions with NULL | High |
| **arXiv fetch returns partial/wrong data** | | | |
| | R2-7 | Failed categories silently skipped — looks like no new papers | High |
| | R2-8 | Legacy IDs (hep-th/9901001) stored wrong — broken dedup/URLs | High |
| | R2-14 | Multi-category fetch only returns first category's papers | Medium |
| | R7-6 | fetch_recent_papers returns cross-listed papers from other fields | Medium |
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
