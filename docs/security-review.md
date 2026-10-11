# Security review — 2026-10-10

[← Back to README](../README.md) · [Security policy](../SECURITY.md)

Reviewed the repository's tracked files and 28 existing commits, backend route permissions and moderation, frontend credential handling and external URLs, dependency locks, and GitHub security settings. This is a source review and targeted regression assessment, not a penetration test or a guarantee of a secure production deployment.

## Findings and fixes

| Severity | Finding | Fix |
| --- | --- | --- |
| High | A publicly documented default admin token granted access to moderation and AI rebuilds. | Removed the default; unset tokens disable admin access. Configured tokens must be at least 32 characters and comparisons use constant-time equality. |
| High | Anyone could edit or delete any comment by its numeric ID. Edited content inherited approval. | Edit/delete routes now require admin authorization. Edits return to hidden, pending review. |
| High | Public feed refresh and some GET routes could trigger source collection and paid AI enrichment. | Rebuilds require admin authorization and have a separate rate budget. Public reads use stored data. |
| High | A missing or failing moderation model approved unchecked comments; images had no review gate. | Failures and images now require manual review. Reopened/pending comments cannot appear in public lists or highlights. |
| Medium | Client-controlled identifiers allowed vote impersonation and bypassed per-user checks. | Interaction ownership uses a signed, HttpOnly visitor cookie; request body/query identifiers do not authorize actions. Anonymous interactions are disabled by default. |
| Medium | One anonymous report immediately unpublished someone else's comment. | Reports create review requests without removing published content. The admin queue includes unresolved reports; decisions resolve them. |
| Medium | No general request size/rate bound existed for anonymous mutation endpoints. | Added a 16 KiB limit covering declared and streamed bodies, bounded per-IP/per-worker budgets, trusted hosts, and explicit CORS/write-origin checks. |
| Medium | Provider response bodies, unsafe URL schemes/redirects, and unbounded external responses increased exposure. | HTTPS-only fetches refuse redirects and private literal addresses, bound response sizes, and avoid logging provider error bodies. RSS uses `defusedxml`. |
| Medium | Model dependencies and embedding artifacts were unpinned; downloads occurred implicitly. | Locked the complete dependency trees, separated optional models from core installation, disabled model downloads by default, and required an immutable embedding revision with remote code disabled and safetensors weights. |
| Medium | Admin credentials persisted indefinitely in browser local storage. | Removed legacy stored tokens and limited new storage to the current tab's session storage. This reduces persistence; it does not make tokens immune to XSS. |
| Medium | Untrusted source/attachment URLs reached browser navigation/image elements. | Added HTTP(S)-only URL validation without embedded credentials; images omit referrers and require manual review. React continues to render content as text. |
| Maintenance | Known vulnerable frontend and Python dependency versions were locked in the repo. | Updated all locked trees to audited versions and added recurring CI, Dependabot, and CodeQL checks. |

## Validation

- Gitleaks 8.30.1 found no secrets in the 28-commit history or the working tree. The scanner executable was verified against its official release checksum. No previously committed `.env`, private key, or SQLite database was found by the tracked-file/history checks.
- The original npm audit reported 17 affected packages: 13 high, 3 moderate, and 1 low. After updating the lock, npm audit reported **0 known vulnerabilities** across production and development dependencies.
- The original pinned Python subset had 16 advisory records across 4 affected packages (some records were duplicate aliases). The updated complete core, optional model, and development locks audited **98 distinct package versions with 0 known vulnerabilities**, including platform-specific packages queried explicitly without installing them.
- **50 backend tests** (security plus existing parsing/clustering tests) pass, covering authorization, cookie tampering, identifier spoofing, vote ownership, moderation visibility, report abuse, cross-origin writes, oversized/streamed bodies, rate limits, read-only routes, unsafe URLs, XML entities, and outbound credential handling.
- **3 frontend security tests**, ESLint, and the production build pass. Bandit reports no findings in application code.
- GitHub private vulnerability reporting and Dependabot vulnerability alerts/security updates were enabled. Existing provider secret scanning and push protection were already enabled; the current secret-scanning alert list was empty.

## Practical limits

The default branch remains unchanged until this pull request is merged. The application changes and workflow configuration take effect after that merge; repository settings listed above take effect immediately.

No live deployment, DNS/proxy/TLS configuration, or real model-weight inference was tested. The optional model dependency tree is locked and audited, but real Detoxify/embedding integration must be validated in the deployment environment; any loading/inference failure leaves comments pending. Browser visual review was unavailable.

Anonymous browser cookies do not establish verified identity or prevent a person from creating multiple visitors. Rate limits operate per process; multiple workers, shared IPs, and distributed traffic require edge/shared controls. Outbound URL checks do not replace DNS/egress restrictions. See [SECURITY.md](../SECURITY.md) before exposing a public service.
