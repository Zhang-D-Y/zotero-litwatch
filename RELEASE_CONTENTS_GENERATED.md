# Generated Clean Release Contents

This clean release directory was generated for sharing Zotero LitWatch without local secrets or runtime artifacts.

## Included top-level files

- `README.md`
- `README_CN.md`
- `ATTRIBUTION.md`
- `SECURITY_CHECKLIST.md`
- `RELEASE_MANIFEST.md`
- `RELEASE_CONTENTS_GENERATED.md`
- `.env.example`
- `.gitignore`
- `api.py`
- `config.py`
- `main.py`
- `requirements.txt`
- `start.sh`

## Included directories

- `ai/`
- `indexer/`
- `zotero/`
- `utils/`
- `web-ui/`
- `tools/`
- `configs/`

## Explicitly not included

- `.env`
- API keys
- Zotero API keys
- Zotero private data
- Zotero local caches
- private PDFs
- `artifacts/`
- `data/`
- `node_modules/`
- `web-ui/node_modules/`
- `.venv/`
- `.git/`
- `__pycache__/`
- `*.pyc`
- `*.pyo`

## Setup required by the recipient

1. Copy `.env.example` to `.env`.
2. Fill in their own Zotero API key and Zotero library settings.
3. Fill in their own AI API key and OpenAI-compatible model settings.
4. Install `uv` and Node.js >= 18.
5. Install Python dependencies with `uv pip install -r requirements.txt` after creating a virtual environment.
6. Install frontend dependencies from `web-ui/` with `npm install` or `npm.cmd install` on Windows.
7. Run LitWatch import in `--dry-run` mode first; use `--commit` only after explicit human confirmation.
