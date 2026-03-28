# Building PaperTrail for macOS

This document explains how to build a standalone macOS application bundle (.app) that can be installed in the Applications folder.

## Prerequisites

- macOS 11 (Big Sur) or later
- Python 3.10 or higher
- `uv` package manager (optional — the build script auto-creates a `.venv` if one is not found)

## Building the Application

### Quick Build

Simply run the build script:

```bash
./build_app.sh
```

This will:
1. Clean previous builds
2. Build the application using PyInstaller
3. Create `dist/PaperTrail.app`
4. Verify the build

### Manual Build

If you want to build manually:

```bash
# Activate virtual environment (if you don't have one, run ./build_app.sh once — it creates one automatically)
source .venv/bin/activate

# Clean previous builds
rm -rf build dist

# Build with PyInstaller
python -m PyInstaller --clean --noconfirm src/PaperTrail.spec
```

## Installing the Application

After building, you have several options:

### Option 1: Copy to Applications (Recommended)

```bash
cp -r dist/PaperTrail.app /Applications/
```

Then launch from Launchpad or Spotlight.

### Option 2: Drag and Drop

1. Open Finder
2. Navigate to the `dist` folder
3. Drag `PaperTrail.app` to your Applications folder

### Option 3: Run from Build Directory

For testing before installing:

```bash
open dist/PaperTrail.app
```

## Application Bundle Details

- **Bundle Identifier**: com.papertrail.app
- **Version**: 0.2.0
- **Size**: ~146 MB
- **Architecture**: Matches host Python (Apple Silicon or Intel — see note below)
- **Minimum macOS**: 11 (Big Sur)

## What's Included

The application bundle includes:
- Python runtime
- PySide6 (Qt6) framework
- arXiv API client
- SQLite database engine
- All application code and dependencies

## First Run

On first run, the application will:
1. Ask you to choose a data directory (or use default)
2. Initialize the SQLite database
3. Create folder structure for PDFs and cache

Default data location:
- macOS: `~/Library/Application Support/PaperTrail`

## Troubleshooting

### "Cannot be opened because the developer cannot be verified"

This is normal for unsigned applications. To allow:

1. Right-click (or Control-click) the app
2. Select "Open"
3. Click "Open" in the dialog

Or use Terminal:
```bash
xattr -cr /Applications/PaperTrail.app
```

### Application won't start

Check the Console app for error messages:
1. Open Console.app
2. Filter for "PaperTrail"
3. Try launching the app again
4. Review any error messages

### Database issues

If the database is corrupted, you can reset it:
1. Delete `~/.papertrail_config`
2. Delete your data directory
3. Restart the application

## Build Configuration

The build is configured in `src/PaperTrail.spec`:
- Excluded packages to reduce size (matplotlib, numpy, etc.)
- Included database migration scripts
- Bundle metadata and Info.plist settings

## Development vs. Production

- **Development**: Use `./run.sh` to run from source
- **Production**: Build the .app bundle for distribution

## Updating the Application

To update an installed application:

1. Build a new version
2. Close the running application
3. Replace the app in /Applications:
   ```bash
   rm -rf /Applications/PaperTrail.app
   cp -r dist/PaperTrail.app /Applications/
   ```

## Creating a Distributable Package

For easier distribution, you can create a DMG file:

```bash
# Create a DMG (requires create-dmg)
brew install create-dmg
create-dmg --volname "PaperTrail" --window-size 600 400 --icon-size 100 \
  --icon "PaperTrail.app" 175 120 --app-drop-link 425 120 \
  "PaperTrail-0.2.0.dmg" "dist/"
```

This creates a drag-and-drop installer DMG.

## Architecture Note

PyInstaller builds for the architecture of the host Python interpreter. If you build on an Apple Silicon Mac, the `.app` will be arm64-only. If you build on Intel, it will be x86_64-only. To produce a universal binary, you would need to install a [universal2 Python build](https://www.python.org/downloads/macos/) from python.org and set `target_arch='universal2'` in the spec file.

## Notes

- The application is self-contained and doesn't require Python to be installed
- All dependencies are bundled
- Data directory is separate from the application
- Application can be safely moved or copied
