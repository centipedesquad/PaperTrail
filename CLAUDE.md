# PaperTrail — Project Instructions

## Package Manager

Use `uv` for all Python dependency management.

## UI Guidelines

- NO emojis in buttons or UI elements
- Keep interface clean and professional

## Design System

Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## Git Commits

- Do NOT add "Co-Authored-By: Claude" signatures to commits.
- Use conventional commit prefixes in the subject line: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `version:`. Choose the label that matches the primary purpose of the change.
- Before committing, review the full working tree diff (`git diff` and `git status`). If the changes span multiple unrelated concerns (e.g. a bug fix and a docs update, or two independent fixes), split them into separate, atomic commits — one per logical change. Stage files selectively with `git add <file>` rather than `git add -A`.
- Any changes to the [BUGS.md](http://BUGS.md) file that mention fixes to the bugs already present in the file should be part of the same commits that include the bug fixes.

## Database Migrations

- Migrations are Python modules in `src/database/migrations/`, registered in the explicit `MIGRATION_REGISTRY` list in `__init__.py`. Ordering is determined by list position, not filenames.
- Each migration exports `name`, `description`, `needs_run(conn)` (schema introspection), and `apply(conn)`. The `needs_run()` function checks actual schema state (e.g., column existence via `PRAGMA table_info`) to decide if the migration should run.
- Some `apply()` methods use `executescript()` internally. Because `executescript()` implicitly commits, migrations cannot be wrapped in a single outer transaction. Each migration is committed individually, and `needs_run()` introspection allows retry after partial failure.
- FTS5 contentless tables (with `content=''`) do NOT support direct UPDATE or DELETE. Use the special syntax: `INSERT INTO tbl(tbl, rowid, ...) VALUES('delete', ...)` for deletes, and delete-then-reinsert for updates. Tables with `content=tablename` (like `notes_fts`) are content-based and support normal DELETE/UPDATE. Tables without any `content=` clause are regular FTS5 tables where normal DELETE/UPDATE also work.
- The `authors` column in FTS5 is computed from joins — it does NOT exist on the `papers` table. Never use `content=papers` with an `authors` column.

## Thread Safety

- `DatabaseConnection.execute()` auto-commits outside `transaction()` blocks via the `_in_transaction` flag.
- All multi-statement DB operations must use `with db.transaction():` to prevent interleaving across QThread workers.
- Workers must be cancelled and `wait()`-ed before cleanup. Check `wait()` return value — don't `deleteLater()` a thread that's still running.
- Lambda closures in signal connections must capture IDs by value (default arg), not object references that can go stale.

## Platform

- macOS is the primary target, Linux secondary.
- Use `sys.platform == 'darwin'` to branch platform-specific behavior (Finder vs xdg-open, /Applications vs /usr/bin, *.app filter).
- Legacy arXiv IDs contain `/` (e.g., `hep-th/9901001`) — sanitize with `.replace('/', '_')` before using as filenames or directory names.

## Bug Fixing Protocol

After implementing any bug fix:

1. **Check for regressions** — Verify the fix doesn't break adjacent functionality. Trace the full call chain of any modified function and confirm callers still behave correctly.
2. **Validate FTS5 triggers** — If modifying FTS5 migrations, test that INSERT, DELETE, UPDATE, and author-update triggers all work. Contentless FTS tables do NOT support direct UPDATE or DELETE — use the special `INSERT INTO tbl(tbl,...) VALUES('delete',...)` syntax.
3. **Validate signal/slot flows** — If modifying Qt signal handlers, confirm that emitted signals carry the correct data and that `current_paper`/state hasn't changed between emit and handler execution.
4. **Fix regressions before reporting done** — Do not mark a bug as fixed if the fix introduces a new bug. Verify end-to-end before committing.
5. **Update BUGS.md** — After fixing bugs, update both the open bugs section and the "Fixed Bugs — User-Facing Impact" table at the end of the file.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:

- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health

