# Building myArXiv for macOS

This document explains how to build a standalone macOS application bundle (.app) that can be installed in the Applications folder.

## Prerequisites

- macOS 10.13 or later
- Python 3.10 or higher
- `uv` package manager

## Building the Application

### Quick Build

Simply run the build script:

```bash
./build_app.sh
```

This will:
1. Clean previous builds
2. Build the application using PyInstaller
3. Create `dist/myArXiv.app`
4. Verify the build

### Manual Build

If you want to build manually:

```bash
# Activate virtual environment
source .venv/bin/activate

# Clean previous builds
rm -rf build dist

# Build with PyInstaller
pyinstaller --clean --noconfirm myarxiv.spec
```

## Installing the Application

After building, you have several options:

### Option 1: Copy to Applications (Recommended)

```bash
cp -r dist/myArXiv.app /Applications/
```

Then launch from Launchpad or Spotlight.

### Option 2: Drag and Drop

1. Open Finder
2. Navigate to the `dist` folder
3. Drag `myArXiv.app` to your Applications folder

### Option 3: Run from Build Directory

For testing before installing:

```bash
open dist/myArXiv.app
```

## Application Bundle Details

- **Bundle Identifier**: com.myarxiv.app
- **Version**: 0.2.0
- **Size**: ~146 MB
- **Architecture**: Universal (Intel + Apple Silicon)
- **Minimum macOS**: 10.13

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
- macOS: `~/Library/Application Support/myArXiv`

## Troubleshooting

### "Cannot be opened because the developer cannot be verified"

This is normal for unsigned applications. To allow:

1. Right-click (or Control-click) the app
2. Select "Open"
3. Click "Open" in the dialog

Or use Terminal:
```bash
xattr -cr /Applications/myArXiv.app
```

### Application won't start

Check the Console app for error messages:
1. Open Console.app
2. Filter for "myArXiv"
3. Try launching the app again
4. Review any error messages

### Database issues

If the database is corrupted, you can reset it:
1. Delete `~/.myarxiv_config`
2. Delete your data directory
3. Restart the application

## Build Configuration

The build is configured in `myarxiv.spec`:
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
   rm -rf /Applications/myArXiv.app
   cp -r dist/myArXiv.app /Applications/
   ```

## Creating a Distributable Package

For easier distribution, you can create a DMG file:

```bash
# Create a DMG (requires create-dmg)
brew install create-dmg
create-dmg --volname "myArXiv" --window-size 600 400 --icon-size 100 \
  --icon "myArXiv.app" 175 120 --app-drop-link 425 120 \
  "myArXiv-0.2.0.dmg" "dist/"
```

This creates a drag-and-drop installer DMG.

## Notes

- The application is self-contained and doesn't require Python to be installed
- All dependencies are bundled
- Data directory is separate from the application
- Application can be safely moved or copied
