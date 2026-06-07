# Release Manifest

This manifest describes the intended clean release package for Zotero LitWatch.

## Include

- `ai/`
- `indexer/`
- `zotero/`
- `utils/`
- `web-ui/`
- `tools/`
- `configs/`
- `api.py`
- `main.py`
- `config.py`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `README.md`
- `README_CN.md`
- `ATTRIBUTION.md`
- `SECURITY_CHECKLIST.md`
- `RELEASE_MANIFEST.md`

## Exclude by Default

- `.env`
- `.venv/`
- `venv/`
- `env/`
- `node_modules/`
- `web-ui/.next/`
- `data/`
- `artifacts/`
- `__pycache__/`
- `.pytest_cache/`
- logs
- local databases
- private Zotero exports
- raw private PDFs
- screenshots or reports containing API keys, Zotero keys, personal library IDs, or private notes

## Conditional Example Artifacts

Example artifacts may be included only when they are intentionally sanitized. If included, document:

- source topic
- generation date
- exact files included
- whether metadata is synthetic, public, or user-provided
- confirmation that no API keys, Zotero keys, personal paths, or private Zotero data are present

## Required Release Checks

- Run `git diff --stat` and review the changed file list.
- Search documentation and release files for accidental secrets.
- Confirm README files state dry-run first and `--commit` only after human confirmation.
- Confirm attribution to Jianxinnn/Zotero-review-generation is preserved.
- Confirm upstream MIT License notice is preserved or restored in a `LICENSE` file.
