# Git Workflow for PaperTrail

This document explains the git branching strategy and workflow for the PaperTrail project.

## Branch Structure

### `main` branch - Clean Releases Only

**Purpose**: Production-ready code that users can clone and run from source.

**Contains**:
- ✅ Source code (`src/` directory)
- ✅ Dependencies (`requirements.txt`)
- ✅ Documentation (`README.md`)
- ✅ Run script (`run.sh`)
- ✅ Git configuration (`.gitignore`, `.gitattributes`)

**Does NOT contain**:
- ❌ Build scripts (`build_app.sh`, `install.sh`)
- ❌ Build configuration (`papertrail.spec`, `setup.py`)
- ❌ Build documentation (`BUILDING.md`, `DEPLOYMENT.md`)
- ❌ Test files (`test_phase2.py`)
- ❌ Internal planning documents (`IMPLEMENTATION.md`)
- ❌ Build artifacts (`dist/`, `build/`)
- ❌ Runtime files (`data/`, `*.log`)

**Commit Policy**:
- Only release commits
- Tagged with version numbers (e.g., `v0.3.0`, `v0.4.0`)
- Clean, working code only
- No development/WIP commits

### `dev` branch - Development History

**Purpose**: Active development with full build tooling and documentation.

**Contains**:
- ✅ Everything from `main` branch
- ✅ Build scripts and tools
- ✅ Build documentation
- ✅ Test files
- ✅ Development helpers

**Does NOT contain**:
- ❌ Internal planning (`IMPLEMENTATION.md`) - see .gitignore
- ❌ Build artifacts (`.app`, `dist/`, `build/`)
- ❌ Runtime files (`data/`, logs)

**Commit Policy**:
- Phase completion commits
- Feature branches merge here
- Work-in-progress allowed
- All development history preserved

## File Locations

### Source Code (Both Branches)

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
```

### Build Files (dev branch only)

```
build_app.sh        - Build script
install.sh          - Installation script
papertrail.spec        - PyInstaller configuration
setup.py            - py2app configuration (unused)
test_phase2.py      - Integration tests
BUILDING.md         - Build instructions
DEPLOYMENT.md       - Deployment guide
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

## Workflow

### For Users (Cloning from main)

```bash
# Clone the repository
git clone <repo-url>
cd PaperTrail

# Install dependencies
uv venv
uv pip install -r requirements.txt

# Run the application
./run.sh
```

**Result**: Clean source code, no build clutter.

### For Developers (Working with dev)

```bash
# Clone and switch to dev
git clone <repo-url>
cd PaperTrail
git checkout dev

# Install dependencies
uv venv
uv pip install -r requirements.txt

# Run from source
./run.sh

# Or build the app
./build_app.sh

# Install
./install.sh
```

**Result**: Full development environment with build tools.

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
   git merge feature/phase4-ratings
   ```

### Creating a Release

1. **Ensure dev is clean and tested**:
   ```bash
   git checkout dev
   ./build_app.sh  # Test build
   ./run.sh        # Test run
   ```

2. **Update version numbers**:
   - `papertrail.spec` (version)
   - `README.md` (if needed)

3. **Commit version bump to dev**:
   ```bash
   git commit -am "Bump version to 0.4.0"
   ```

4. **Cherry-pick source changes to main**:
   ```bash
   git checkout main
   git checkout dev -- src/
   git checkout dev -- requirements.txt
   git checkout dev -- README.md
   git add .
   git commit -m "Release v0.4.0 - Phase 4: Ratings & Notes

   Features:
   - Inline rating widgets
   - Note editor with auto-save
   - Visual indicators

   See dev branch for build instructions."
   ```

5. **Tag the release**:
   ```bash
   git tag -a v0.4.0 -m "Release v0.4.0"
   ```

6. **Switch back to dev for continued work**:
   ```bash
   git checkout dev
   ```

## Commit Message Guidelines

### Format

```
Short summary (50 chars or less)

Detailed description if needed:
- What changed
- Why it changed
- Any breaking changes

Related: Phase X, Issue #Y
```

### Examples

**Good**:
```
Add inline rating widgets to paper cells

Implements three-dropdown rating system (importance,
comprehension, technicality) directly in paper cells.
Auto-saves on selection.

Phase 4: Ratings & Notes
```

**Bad**:
```
Fixed stuff

Co-Authored-By: Claude <email>  # DON'T include this
```

### Rules

- ❌ **NO** `Co-Authored-By:` lines
- ✅ Clear, descriptive messages
- ✅ Imperative mood ("Add feature" not "Added feature")
- ✅ Reference phase/issue if applicable
- ✅ Explain WHY if not obvious

## Merging Strategy

### dev → main (Releases only)

**Method**: Cherry-pick source files, NOT merge

**Why**: Keeps main clean without build files

**Command**:
```bash
git checkout main
git checkout dev -- src/ requirements.txt README.md
git commit -m "Release vX.Y.Z"
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
6. **Keep main clean** - Only source code needed to run
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

### "I need a build file from dev while on main"

```bash
# Don't commit it! Just copy temporarily
git checkout dev -- build_app.sh
# Use it, but don't commit
git checkout HEAD -- build_app.sh  # Undo
```

### "How do I see what's different between branches?"

```bash
git diff --name-only main..dev  # Just filenames
git diff --stat main..dev       # Summary
git diff main..dev              # Full diff
```

## Current Status

**Branches**:
- `main`: v0.3.0 (Phases 1-3 complete)
- `dev`: v0.3.0 + build tools

**Next**:
- Phase 4 development on `dev`
- Release v0.4.0 when complete

---

**Last Updated**: 2026-02-09
**Maintained by**: Project Team
