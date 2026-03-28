# PaperTrail - arXiv Paper Management Application

A desktop application for efficiently managing and organizing arXiv papers for research workflows.

## Features

- **arXiv Integration**: Fetch papers by subject class (new submissions or recent papers)
- **Rich Metadata**: Store papers with full metadata including authors, categories, and abstracts
- **Rating System**: Three-metric rating system (importance, comprehension, technicality)
- **Note Taking**: Take notes directly on papers with full-text search
- **PDF Management**: On-demand download with customizable naming patterns
- **Reader Integration**: Opens PDFs in configurable PDF readers
- **Full-Text Search**: Fast FTS5-powered search across titles, abstracts, authors, and notes
- **Advanced Filtering**: Filter by categories, date ranges, rating status, and PDF availability
- **Theme Support**: Light and dark mode with Ctrl+T toggle
- **Preferences Dialog**: Configurable theme, font size, PDF settings, and fetch defaults
- **Hierarchical Categories**: Smart grouping of arXiv categories by field (Physics, CS, Math, etc.)
- **Cross-Platform**: Works on macOS and Linux

## Installation

### Preparation

The run and build scripts will automatically create a `.venv` if one is not found, so no additional tooling is strictly required beyond Python 3.10+. However, using [`uv`](https://docs.astral.sh/uv/getting-started/installation/) is recommended for faster, reproducible dependency management. If you use another virtual environment manager, ensure the environment is placed in a local `.venv/` folder.

### Option 1: Pre-built Application (Recommended for macOS)

1. Download or build the .app bundle:
  ```bash
   ./build_app.sh
  ```
2. Copy to Applications folder:
  ```bash
   cp -r dist/PaperTrail.app /Applications/
  ```
3. If macOS Gatekeeper blocks the app (since it is not notarized), run:
  ```bash
   xattr -cr /Applications/PaperTrail.app
  ```
4. Launch from Launchpad or Spotlight

See [BUILDING.md](BUILDING.md) for detailed build instructions.

### Option 2: Run from Source

#### Prerequisites

- Python 3.10 or higher
- `uv` package manager (optional but recommended — see [Preparation](#preparation))

#### Setup

1. Clone or download this repository
2. Install dependencies:

```bash
uv sync          # if you have uv
# or
./run.sh         # auto-creates .venv and installs deps on first run
```

## Usage

### Running from Source

```bash
./run.sh
```

Or manually:

```bash
cd src
source ../.venv/bin/activate
python main.py
```

### Running the Installed App

- Launch from Applications folder
- Or: `open /Applications/PaperTrail.app`

### First Run

On first run, you'll be prompted to choose a data directory location. This is where:

- The SQLite database will be stored
- Downloaded PDFs will be saved
- Cache files will be kept

You can choose the default location or select a custom directory (e.g., in your cloud sync folder).

### Fetching Papers

1. Click "Fetch Papers" in the toolbar
2. Select arXiv categories (e.g., hep-th, cs.AI, gr-qc)
3. Choose fetch mode:
  - **New**: Today's new submissions
  - **Recent**: Papers from the last N days
4. Click Fetch

Papers will appear in the feed view with expandable/collapsible cells.

### Managing PDFs

When you click "View PDF" on a paper:

- If PDF is already downloaded, it opens immediately
- If not downloaded, you'll be asked:
  - **Download & Keep**: Save to permanent storage with custom naming
  - **Stream (Temp)**: Download to cache (cleaned on exit)

### Rating Papers

1. Expand a paper cell
2. Click "Rate Paper"
3. Select ratings for:
  - **Importance**: path-breaking, good, routine, passable, meh, trash
  - **Comprehension**: understood, partially understood, not understood
  - **Technicality**: tough, not tough, doesn't make sense

### Taking Notes

1. Expand a paper cell
2. Click "Add/Edit Notes"
3. Type your notes (auto-saves after 2 seconds)

### Searching & Filtering

The left panel provides a comprehensive filter system:

- **Full-text search** across titles, abstracts, and authors (powered by FTS5)
- **Category filtering** with hierarchical grouping (Physics, CS, Math, etc.) and paper counts
- **Date range** with quick presets (today, this week, this month) and custom range
- **Rating status**: all, rated only, or unrated only
- **PDF availability**: all, has PDF, or no PDF
- **Sort by**: newest first, oldest first, title A-Z, or title Z-A

## Configuration

### PDF Naming Pattern

Default: `[{author1}_{author2}][{title}][{arxiv_id}].pdf`

Available variables:

- `{author1}`: First author last name
- `{author2}`: Second author last name
- `{authors_all}`: All authors
- `{title}`: Paper title
- `{arxiv_id}`: arXiv ID
- `{year}`: Publication year

Example: `Smith_Jones_Attention_Is_All_You_Need_2301.12345.pdf`

### PDF Reader

**macOS**: Automatically uses Skim (or Preview as fallback)

**Linux**: Auto-detects installed readers (evince, okular, xpdf, atril, mupdf)

You can set a custom reader path in Preferences.

### Preferences

Access via **File > Preferences** (or Cmd+, on macOS):

- **General**: Theme (light/dark), font size (8-20pt)
- **PDF**: Reader path, default download behavior (ask/download/stream), naming pattern
- **Fetching**: Max results per category, default fetch mode, number of recent days

### Keyboard Shortcuts


| Shortcut           | Action                  |
| ------------------ | ----------------------- |
| `Ctrl+T`           | Toggle light/dark theme |
| `Ctrl+F`           | Fetch papers            |
| `Cmd+,` / `Ctrl+,` | Open Preferences        |
| `Cmd+Q` / `Ctrl+Q` | Quit                    |


## Documentation

- **[README.md](README.md)** - This file, user guide
- **[BUILDING.md](BUILDING.md)** - Build and distribution instructions

## Development

### Project Structure

```
PaperTrail/
├── src/
│   ├── main.py                    # Application entry point
│   ├── models.py                  # Data models
│   ├── database/                  # Database layer
│   │   ├── connection.py
│   │   ├── repositories.py
│   │   ├── migration_manager.py
│   │   └── migrations/
│   ├── api/                       # External API integrations
│   │   └── arxiv_client.py
│   ├── services/                  # Business logic
│   │   ├── config_service.py
│   │   ├── paper_service.py
│   │   ├── pdf_service.py
│   │   └── fetch_service.py
│   ├── ui/                        # User interface
│   │   ├── main_window.py
│   │   ├── theme.py               # Light/dark theme system
│   │   ├── widgets/
│   │   │   ├── paper_cell_widget.py
│   │   │   ├── paper_feed_widget.py
│   │   │   ├── filter_panel_widget.py
│   │   │   ├── rating_widget.py
│   │   │   └── note_editor_widget.py
│   │   └── dialogs/
│   │       ├── fetch_papers_dialog.py
│   │       ├── pdf_action_dialog.py
│   │       └── preferences_dialog.py
│   ├── assets/                    # App resources
│   │   └── AppIcon.icns           # Application icon
│   └── utils/                     # Utilities
│       ├── platform_utils.py
│       ├── async_utils.py
│       └── filename_utils.py
├── data/                          # Runtime data (user-chosen location)
├── tests/                         # Test suite
└── pyproject.toml
```

### Running Tests

```bash
pytest tests/
```

## Future Features

- Author citation metrics from InspireHEP
- AI-powered keyword extraction
- PDF annotation import from Skim
- Export to BibTeX

## License

AGPL-3.0-only. See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please open an issue or pull request.

## Support

For issues or questions, please open a GitHub issue.
