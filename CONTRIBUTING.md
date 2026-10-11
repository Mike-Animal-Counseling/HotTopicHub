# Contributing

Open a focused pull request describing the problem, behavior change, and validation. For vulnerabilities, follow [SECURITY.md](SECURITY.md) and use private reporting.

Use Python 3.12+ and the Node.js version documented in the [README](README.md). Keep secrets, local databases, caches, and personal data out of commits. Changes to permissions, moderation, external fetching, or request handling need security regression tests.

## Checks

From `backend/`:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests test_ai_enrichment_service.py test_topic_clustering_service.py
python -m bandit -r app
python -m pip_audit -r requirements.txt -r requirements-moderation.txt -r requirements-dev.txt --no-deps --disable-pip
```

From `frontend/`:

```bash
npm ci
npm test
npm run lint
npm run build
npm audit
```

The CI tests use an isolated database and mocked model results; they do not fetch news or download model weights. `backend/test_moderation.py` is a separate, optional integration script requiring the real model and network access.

## Updating dependencies

Edit the direct dependencies in the relevant `backend/requirements*.in` file and regenerate all affected locks with `uv pip compile --universal --python-version 3.12`. Re-audit the full locked dependency trees and run the checks above. Core installation does not install PyTorch; `requirements-moderation.txt` is the separate complete lock for optional models.

Commit `frontend/package-lock.json` together with dependency changes. GitHub Actions are pinned to commit SHAs and updated through Dependabot. Workflows must use minimal permissions and must not execute untrusted PR code through `pull_request_target`.
