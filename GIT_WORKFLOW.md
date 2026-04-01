# Git Workflow for PaperTrail

This document explains the git branching strategy and workflow for the PaperTrail project.

## Branch Structure

### `main` branch - Clean Releases

**Purpose**: Production-ready code that users can clone, run from source, or build into a `.app`.

**Contains**:

- Source code (`src/` directory)
- Dependencies (`pyproject.toml`)
- Documentation (`README.md`, `BUILDING.md`, `CHANGELOG.md`)
- Run script (`run.sh`)
- Build script (`build_app.sh`)
- Build configuration (`src/PaperTrail.spec`)
- Git configuration (`.gitignore`, `.gitattributes`)

**Does NOT contain**:

- Test files (`test_phase2.py`)
- Internal planning documents (`IMPLEMENTATION.md`)
- Internal deployment docs (`DEPLOYMENT.md`)
- Build artifacts (`dist/`, `build/`)
- Runtime files (`data/`, `*.log`)

**Commit Policy**:

- Only release commits
- Tagged with version numbers (e.g., `v0.3.0`, `v0.4.0`)
- Clean, working code only
- No development/WIP commits

### `dev` branch - Development History

**Purpose**: Active development with full tooling, tests, and internal documentation.

**Contains**:

- Everything from `main` branch
- Test files
- Internal deployment docs (`DEPLOYMENT.md`)
- Development helpers

**Does NOT contain**:

- Internal planning (`IMPLEMENTATION.md`) - see .gitignore
- Build artifacts (`.app`, `dist/`, `build/`)
- Runtime files (`data/`, logs)

**Commit Policy**:

- Phase completion commits
- Feature branches merge here
- Work-in-progress allowed
- All development history preserved

## File Locations

### Source Code & Build Tools (Both Branches)

```
src/
├── __init__.py
├── main.py
├── models.py
├── api/
│   └── arxiv_client.py
├── database/
│   ├── connection.py
│   ├── migration_manager.py
│   ├── repositories.py
│   └── migrations/
│       └── 001_initial_schema.sql
├── services/
│   ├── config_service.py
│   ├── paper_service.py
│   ├── fetch_service.py
│   └── pdf_service.py
├── ui/
│   ├── main_window.py
│   ├── widgets/
│   │   ├── paper_cell_widget.py
│   │   └── paper_feed_widget.py
│   └── dialogs/
│       ├── fetch_papers_dialog.py
│       └── pdf_action_dialog.py
└── utils/
    ├── platform_utils.py
    ├── async_utils.py
    └── filename_utils.py

build_app.sh        - Build .app bundle
src/PaperTrail.spec - PyInstaller configuration
BUILDING.md         - Build instructions
```

### Dev-Only Files (dev branch only)

```
test_phase2.py      - Integration tests
DEPLOYMENT.md       - Internal deployment/distribution guide
```

### Ignored Files (Not in repo)

```
IMPLEMENTATION.md   - Internal planning (in .gitignore)
.venv/              - Virtual environment
build/              - Build artifacts
dist/               - Distribution files
data/               - Runtime data
*.log               - Log files
__pycache__/        - Python cache
.DS_Store           - macOS files
```

## Git Hooks

The project includes git hooks in `.githooks/` that enforce workflow rules automatically.

### Setup (run once after cloning)

```bash
sh .githooks/setup.sh
```

### What the hooks check


| Hook         | What it catches                                                                                 |
| ------------ | ----------------------------------------------------------------------------------------------- |
| `pre-commit` | Secrets files (`.env`, credentials) on any branch; dev-only files and build artifacts on `main` |
| `commit-msg` | Empty messages; vague messages like "fix" or "wip" (blocked on `main`, warned on `dev`)         |
| `pre-push`   | Pushes to `main` without a version tag (`v0.X.0`)                                               |


To bypass in an emergency: `git commit --no-verify` or `git push --no-verify`

## Workflow

### Prerequisites

The run and build scripts will automatically create a `.venv` if one is not found, so no additional tooling is strictly required beyond Python 3.10+. However, [`uv`](https://docs.astral.sh/uv/getting-started/installation/) is recommended for faster, reproducible dependency management. If you use another virtual environment manager, ensure the environment is placed in a local `.venv/` folder.

### For Users (Cloning from main)

#### Run from source

```bash
git clone <repo-url>
cd PaperTrail
uv sync          # optional — run.sh auto-creates .venv if missing
./run.sh
```

#### Build and install the .app

```bash
git clone <repo-url>
cd PaperTrail
uv sync          # optional — build_app.sh auto-creates .venv if missing
./build_app.sh
cp -r dist/PaperTrail.app /Applications/
```

**Result**: Full source code with build tools — users can run from source or build a native `.app`.

### For Developers (Working with dev)

```bash
# Clone and switch to dev
git clone <repo-url>
cd PaperTrail
git checkout dev

# Install dependencies (or let run.sh handle it automatically)
uv sync

# Run from source
./run.sh

# Or build the app
./build_app.sh

# Install
cp -r dist/PaperTrail.app /Applications/
```

**Result**: Full development environment with tests and internal docs.

## Development Workflow

### Making Changes

1. **Switch to dev branch**:
  ```bash
   git checkout dev
  ```
2. **Create feature branch** (optional):
  ```bash
   git checkout -b feature/phase4-ratings
  ```
3. **Make changes, test, commit**:
  ```bash
   git add <files>
   git commit -m "Phase 4: Add rating widgets"
  ```
4. **Merge to dev**:
  ```bash
   git checkout dev
   git merge --ff-only feature/phase4-ratings
  ```

### Creating a Release

1. **Ensure dev is clean and tested**:
  ```bash
   git checkout dev
   ./build_app.sh  # Test build
   ./run.sh        # Test run
  ```
2. **Update version numbers**:
  - Run `./bump_version.sh X.Y.Z`
  - `README.md` (if needed)
3. **Commit version bump to dev**:
  ```bash
   git commit -am "Bump version to 0.4.0"
  ```
4. **Review what changed since last release**:
  ```bash
   git log main..dev --oneline          # Commit summary
   git diff --stat main..dev            # Files changed
  ```
5. **Cherry-pick release files to main**:
  ```bash
   git checkout main
   git checkout dev -- src/ pyproject.toml README.md run.sh LICENSE build_app.sh BUILDING.md
   git add .
  ```
6. **Update CHANGELOG.md** on main with the new release entry:
  ```markdown
   ## v0.4.0 — 2026-XX-XX

   ### Added
   - Feature 1
   - Feature 2

   ### Changed
   - Change 1

   ### Fixed
   - Bug fix 1
  ```
   Use the diff log from step 4 to ensure nothing is missed.
7. **Commit and tag**:
  ```bash
   git add CHANGELOG.md
   git commit -m "Summary of changes since last release

   - Feature or fix 1
   - Feature or fix 2
   - Feature or fix 3"
   git tag -a v0.4.0 -m "v0.4.0"
  ```
8. **Switch back to dev for continued work**:
  ```bash
   git checkout dev
  ```

## Commit Message Guidelines

### Format

```
<type>: short summary (50 chars or less)

Detailed description if needed:
- What changed
- Why it changed
- Any breaking changes

Related: Phase X, Issue #Y
```

Use a conventional commit prefix that matches the primary purpose of the change:

| Prefix       | When to use                                      |
| ------------ | ------------------------------------------------ |
| `feat:`      | New feature or capability                        |
| `fix:`       | Bug fix                                          |
| `refactor:`  | Code restructuring with no behavior change       |
| `docs:`      | Documentation-only changes                       |
| `chore:`     | Config, tooling, CI, or other maintenance        |
| `version:`   | Version bump commits                             |

### Examples

**Good**:

```
feat: add inline rating widgets to paper cells

Implements three-dropdown rating system (importance,
comprehension, technicality) directly in paper cells.
Auto-saves on selection.

Phase 4: Ratings & Notes
```

```
fix: FTS5 delete commands must supply exact authors for contentless match
```

```
docs: update BUGS.md with cross-model audit findings (round 4)
```

**Bad**:

```
Fixed stuff
```

### Rules

- Always start with a conventional commit prefix (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `version:`)
- Clear, descriptive messages
- Imperative mood ("add feature" not "added feature")
- Reference phase/issue if applicable
- Explain WHY if not obvious

## Merging Strategy

### dev → main (Releases only)

**Method**: Cherry-pick source and build files, NOT merge

**Why**: Keeps main free of test files, WIP commits, and internal docs

**Command**:

```bash
git checkout main
git checkout dev -- src/ pyproject.toml README.md run.sh LICENSE build_app.sh BUILDING.md
# Update CHANGELOG.md with release notes
git add .
git commit -m "Summary of changes since last release"
```

### Feature branches → dev

**Method**: Merge or rebase

**Why**: Preserve development history

**Command**:

```bash
git checkout dev
git merge feature/my-feature
```

## Viewing History

### See all commits on dev

```bash
git checkout dev
git log --oneline --graph
```

### See releases on main

```bash
git checkout main
git log --oneline
git tag
```

### Compare branches

```bash
git diff main..dev                    # See what's in dev but not main
git log main..dev --oneline           # See commits in dev but not main
git diff main..dev -- src/            # Compare just source code
```

## Best Practices

1. **Always work on dev** - Never commit directly to main
2. **Test before releasing** - Build and run on dev first
3. **Clean commits** - One logical change per commit
4. **Meaningful messages** - Explain what and why
5. **Tag releases** - Use semantic versioning (v0.3.0, v0.4.0, etc.)
6. **Keep main focused** - Source code and build tools only, no tests or internal docs
7. **Document changes** - Update README for user-facing changes
8. **No secrets** - Never commit API keys, passwords, or personal data

## Troubleshooting

### "I accidentally committed to main"

```bash
# Move the commit to dev
git checkout dev
git cherry-pick main
git checkout main
git reset --hard HEAD~1
```

### "How do I see what's different between branches?"

```bash
git diff --name-only main..dev  # Just filenames
git diff --stat main..dev       # Summary
git diff main..dev              # Full diff
```

---

**Last Updated**: 2026-03-28
**Maintained by**: Project Team