# Attribution

This repository is based on the upstream Zotero-review-generation / Zotero Chat project by Jianxinnn.

## Upstream Work

- Upstream project: `Jianxinnn/Zotero-review-generation`
- Common project name in inherited documentation: Zotero Chat
- Upstream license notice: MIT License, as documented in the inherited README

The upstream project provides the local Zotero AI assistant foundation, including:

- Zotero collection scanning
- Local PDF extraction workflow
- AI summarization
- Deep research over selected papers
- Paper categorization
- Chat with selected papers
- Semantic search
- Global Zotero search
- FastAPI backend
- Next.js frontend

## Extensions in This Repository

This repository extends the upstream system with LitWatch capabilities:

- Topic-configured literature search scripts
- Screening, scoring, normalization, and deduplication workflow
- Dry-run first Zotero import workflow
- Explicit `--commit` Zotero write path after human confirmation
- Generated research reports and audit outputs
- Related-work matrix and must-read list conventions
- Literature knowledge graph generation
- Release and security documentation

## Redistribution Requirements

Keep the upstream attribution and MIT License notice when redistributing this project or derivative work. Do not present this repository as a fully original implementation.
