# GenomeInsight

Personal genomics analysis platform for 23andMe raw data.

## Quick Start

```bash
git clone https://github.com/bioedcam/GenomeInsight.git
cd GenomeInsight
conda activate GI        # Python 3.12+ environment
make setup               # Install Python + frontend dependencies
make test                 # Run all tests (~10 s)
make dev                  # Start backend (port 8000) + frontend (port 5173)
```

## Requirements

- Python 3.12+
- Node 20+ (for frontend)

## Local Development

**Backend only:**

```bash
make run-api
# or: uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend only:**

```bash
make run-frontend
# or: cd frontend && npm run dev
```

**Full stack (backend + frontend):**

```bash
make dev
```

**Run tests:**

```bash
make test              # All tests (backend + frontend)
make test-backend      # Backend only (pytest)
make test-frontend     # Frontend only (vitest)
```

**Lint / format:**

```bash
make lint              # Check with Ruff
make format            # Auto-fix with Ruff
```

### Python environment

The recommended path is the conda env `GI`:

```bash
conda activate GI
```

Editable install (for development):

```bash
pip install -e ".[dev]"
```

For ad-hoc `pytest` runs without installing the package:

```bash
PYTHONPATH=. pytest
```

## Module Status

| Module | Status | Phase |
|--------|--------|-------|
| Setup Wizard | Complete | 1 |
| Dashboard | Complete | 1 |
| Variant Explorer | Complete | 2 |
| Variant Detail | Complete | 2 |
| Genome Browser (IGV.js) | Complete | 2 |
| Command Palette | Complete | 4 |
| Pharmacogenomics | UI skeleton | 3 |
| Nutrigenomics | UI skeleton | 3 |
| Cancer | UI skeleton | 3 |
| Cardiovascular | UI skeleton | 3 |
| APOE | UI skeleton | 3 |
| Carrier Status | UI skeleton | 3 |
| Ancestry | UI skeleton | 3 |
| Reports | UI skeleton | 4 |
| Settings | UI skeleton | 4 |
| Login / Auth | UI skeleton | 4 |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: cannot import name 'UTC' from 'datetime'` | Python < 3.12 | Install Python 3.12+ and activate the correct environment |
| `ModuleNotFoundError: No module named 'backend'` | Package not installed / `PYTHONPATH` not set | `pip install -e ".[dev]"` or run with `PYTHONPATH=.` |
| Node version errors during `npm install` | Node < 20 | Install Node 20+ (`nvm install 20`) |
| `database is locked` / SQLite WAL errors | Concurrent writes without WAL | Ensure all connections use WAL mode (default in GenomeInsight) |

## License

MIT
