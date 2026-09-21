# Implementation Log

## 2026-09-19

- Defined the first-cut policy: recursively scan a stable tree snapshot, classify direct files only among immediate child folders, include an explicit `none` route, and never move below `0.70` confidence.
- Chose a preview-first CLI: `jfo` renders a colored plan and `jfo --apply` performs validated moves. Added configurable model, higher confidence thresholds, content limits, hidden-file inclusion, and collision handling.
- Added secure interactive credential setup with environment and local `.env` overrides for automation and development.
- Implemented MarkItDown extraction with filename fallback for unsupported or failed conversions.
- Batched all files sharing a parent into one Jev request, with stable opaque folder IDs, request logging, bounded retries, and prompt-injection-resistant instructions.
- Added labeled evaluation metrics for accuracy, move precision/recall, coverage, abstention, and latency, plus JSON reports.
- Added unit and integration-style tests for extraction fallback, recursive planning, apply behavior, collisions, and evaluation math.
- Added a generated recursive sample corpus spanning text, Markdown, CSV, HTML, JSON, and an unsupported extension.
- Added Poetry and Docker Compose development environments.
- Restricted the supported Python range to 3.12–3.13 because MarkItDown's complete optional dependency set currently includes a package that does not support Python 3.14.
- Added FFmpeg to the runtime image so MarkItDown's audio conversion path has its required system executable.
- Kept the evaluation manifest outside the folder under test so organizer scans cannot classify or move their own ground-truth labels.
- Generated and locked the Poetry dependency graph, then successfully built the production Docker image.
- Verified the installed TypeSafe SDK client and retry configuration can be constructed and closed with the implemented interface.
- Passed Ruff and five containerized tests covering supported and unsupported extraction, recursive planning, move application, collisions, metric calculations, and the complete generated sample workflow.
- The labeled seven-file sample achieved 100% policy accuracy, precision, and recall with the deterministic test classifier. Live Jev metrics remain pending until a real `TYPESAFE_API_KEY` is configured.

## 2026-09-20

- Added `ROADMAP.md` with a separate work-item section for every proposed capability; correction learning and decision explanations are explicitly parked.
- Added corpus analysis that computes word counts and document-frequency counts from bounded extracted text, mines constrained candidate folder names, and includes those counts and names in Jev folder-usefulness questions.
- Added opt-in folder discovery with two policy gates: Jev folder confidence of at least `0.70`, followed by at least the configured number of high-confidence file assignments.
- Added inherited `.jfo.toml` descriptions, organization context, rules, and candidate-folder seeds plus `jfo init --recursive`.
- Added lightweight `.jfo-cache.json` extraction caching keyed by filename, size, nanosecond modification time, extraction settings, and cache schema version. Writes are atomic and corrupt cache files are safely rebuilt.
- Added configurable page-section retention. Confirmed MarkItDown 0.1.7 does not expose early-stop page conversion, so JFO truncates retained evidence and relies on caching to avoid repeat conversion.
- Added immutable preview plans under `.jfo/plans`, complete pre-apply validation, rollback on unexpected apply failures, `jfo apply`, and `jfo undo` with moved-file validation.
- Expanded the focused suite to cover caching, invalidation, page limits, corpus counts, candidate generation, inherited configuration, recursive initialization, discovery support gates, stale plans, apply, and undo.
- Fixed the production container entrypoint so the installed `jfo` command runs from any mounted working directory instead of requiring `pyproject.toml` there.
- Hardened the MarkItDown boundary after a real JSON file triggered an uncaught charset error: any converter failure now falls back to filename evidence, and CLI tracebacks no longer display local variables that may contain credentials.
- Replaced Choice decisiveness as the file-move gate with independent file-folder Noul fit probabilities. A live mixed corpus showed that a decisive least-wrong Choice can still be semantically unsafe; moves now require a direct fit probability of at least the configured threshold.
- Isolated classification state per file after a controlled live request proved that large multi-file state caused cross-file semantic interference. Each file now gets one Jev request containing all of its candidate-folder fit questions.
- Tightened candidate mining after live output produced weak singular/generic names: candidates now prioritize repeated filename concepts, normalize common category names, suppress architecture/version noise, and add file-type groups only when at least two files support them.
- Completed a live run against a 24-file mixed-format test corpus: the final cached preview finished in 3.99 seconds, approved 17 moves, created five proposed categories, and abstained on seven files. Manual review found all approved routes coherent for this corpus.
- Applied the saved 17-move plan, verified the organized tree, then undid it successfully. Undo restored all 17 files and removed all five created folders; only hidden cache and plan-history artifacts remain.
- Began the native CLI distribution pass: folder discovery is now the default `jfo` behavior, `--existing-folders-only` opts out, and `jfo --version` plus `jfo doctor` support installation verification.
- Made candidate provenance visible in previews and saved plans. `Software Installers` is a deterministic file-type candidate triggered by at least two installer extensions; in the live corpus its source was the two `.dmg` files, after which Jev independently approved the category and file assignments.
- Added `jfo candidates`, a read-only local audit that lists every candidate and its source before Jev filtering. Updated the discovery question to reference candidate-source evidence explicitly so extension-backed categories are judged with the evidence that generated them.
- Built version 0.2.0 as a wheel and source distribution, installed it globally on macOS with uv and an isolated Python 3.13 environment, and verified the launcher at `~/.local/bin/jfo`.
- Added a uv-first, pipx-fallback installer and migrated package metadata to the standard PEP 621 layout. Chose PyPI plus a hosted installer and Homebrew tap as the public distribution path rather than an npm wrapper around Python.
- Tested the installed command from an interactive zsh session in the real test folder: doctor, candidate audit, default preview, 14-move apply, tree inspection, and undo all passed. Undo restored every file and removed all four created folders.
- Started the public-release audit. Clean wheel installation, PyPI metadata checks, dependency vulnerability scanning, and credential-pattern scanning passed. Replaced optimization-sensitive cache assertions with explicit malformed-cache normalization after static analysis flagged them.
- Rewrote the README around preview-first safety, reversible plans, candidate provenance, privacy boundaries, and a Mermaid architecture diagram. Added a staged public rollout with explicit release gates to the roadmap.
- Added a least-privilege GitHub Actions matrix for Python 3.12–3.13 on macOS and Linux, pinned official actions to immutable revisions, and added weekly Dependabot checks for Python and workflow dependencies.
- Confirmed that `jev-file-organizer` currently has no PyPI project endpoint. This is an availability check only; the name remains unreserved until first publication.
- Completed the canonical release-readiness gate: Actionlint passed, Ruff passed, all 24 tests passed, Bandit reported no findings, `pip-audit` found no known dependency vulnerabilities, `twine check` accepted both distributions, and the wheel installed and launched under clean Python 3.13.
- Audited the release tree and built archives for credentials, personal paths, oversized files, and unintended local artifacts; no release-blocking findings remained. Restricted the ignored local `.env` from `0644` to owner-only `0600` without reading or changing its contents.
- Left the directory uninitialized as a Git repository and performed no commit, push, GitHub mutation, TestPyPI upload, or PyPI publication. The open-source license, repository identity, support address, and Jev/TypeSafe attribution remain explicit pre-release decisions.
- Verified the new empty GitHub repository at `https://github.com/nitinnat/jev-file-organizer`, initialized the local repository on `chore/initial-open-source-release`, added it as `origin`, and created the first sanitized local commit without pushing. Configured the repository-local author as `nitinnat` with a GitHub noreply address after Git initially inferred a machine-local email.
- Selected Apache License 2.0, added the canonical license text, declared its SPDX identifier in package metadata, added the final GitHub project URLs, and documented the license in the README.
- Prepared the verified root commit for publication on `chore/initial-open-source-release` and pushed that feature branch to the empty `origin` repository. No direct push to `main` was performed.
