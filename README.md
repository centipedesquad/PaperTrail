# PaperTrail - arXiv Paper Management Application

A desktop application for efficiently managing and organizing arXiv papers for research workflows.

## Features

- **arXiv Integration**: Fetch papers by subject class (new submissions or recent papers)
- **Rich Metadata**: Store papers with full metadata including authors, categories, and abstracts
- **Rating System**: Three-metric rating system (importance, comprehension, technicality)
- **Note Taking**: Take notes directly on papers with full-text search
- **PDF Management**: On-demand download with customizable naming patterns
- **Reader Integration**: Opens PDFs in Skim (macOS) or configurable Linux readers
- **Full-Text Search**: Fast FTS5-powered search across titles, abstracts, authors, and notes
- **Advanced Filtering**: Filter by categories, date ranges, rating status, and PDF availability
- **Flexible Sorting**: Sort papers by date (newest/oldest first) or title (A-Z/Z-A)
- **Cross-Platform**: Works on macOS and Linux

## Installation

### Option 1: Pre-built Application (Recommended for macOS)

1. Download or build the .app bundle:
   ```bash
   ./build_app.sh
   ```

2. Copy to Applications folder:
   ```bash
   cp -r dist/PaperTrail.app /Applications/
   ```

3. Launch from Launchpad or Spotlight

See [BUILDING.md](BUILDING.md) for detailed build instructions.

### Option 2: Run from Source

#### Prerequisites

- Python 3.10 or higher
- `uv` package manager

#### Setup

1. Clone or download this repository

2. Create a virtual environment:
```bash
uv venv
```

3. Install dependencies:
```bash
uv pip install "PySide6>=6.6.0" "arxiv>=2.1.0" "requests>=2.31.0" \
               "python-dateutil>=2.8.2" "PyMuPDF>=1.23.0"
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

### Searching

- Use the search box in the toolbar for full-text search
- Filter by categories, date range, and ratings in the left panel

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

## Documentation

- **[README.md](README.md)** - This file, user guide
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Complete implementation log tracking all phases, files, and changes
- **[BUILDING.md](BUILDING.md)** - Build and distribution instructions
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Deployment guide and bundle details

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
│   │   ├── widgets/
│   │   └── dialogs/
│   └── utils/                     # Utilities
│       ├── platform_utils.py
│       └── async_utils.py
├── data/                          # Runtime data (user-chosen location)
├── tests/                         # Test suite
└── requirements.txt
```

### Running Tests

```bash
pytest tests/
```

### Development Phases

- ✅ **Phase 1**: Foundation (database, config, platform utils)
- 🚧 **Phase 2**: arXiv Integration (API client, fetch service)
- 🚧 **Phase 3**: PDF Management
- 🚧 **Phase 4**: Ratings & Notes
- 🚧 **Phase 5**: Search & Filtering
- 🚧 **Phase 6**: Polish & Testing

## Future Features

- Author citation metrics from InspireHEP
- AI-powered keyword extraction
- PDF annotation import from Skim
- Export to BibTeX
- Advanced filtering and sorting

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or pull request.

## Support

For issues or questions, please open a GitHub issue.
