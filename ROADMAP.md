# Product Roadmap

Each section is an independently trackable work item. Status values describe product maturity, not implementation difficulty.

## Execution Priority

1. Performance, cost, and scale controls.
2. Privacy and data controls.
3. Evaluation and confidence calibration.
4. Public packaging and distribution.
5. Deterministic organization rules.
6. Decision explanations and interactive review.
7. Validate hierarchical routing on a labeled deep-tree corpus.
8. Correction learning.
9. Duplicate and filename management.
10. Watch mode.

This order minimizes irreversible risk: first make runs bounded and observable, then protect what leaves the machine, measure decision quality, and only afterward add more autonomous behavior.

## 1. Intelligent Folder Discovery — Implemented; Live Pilot Complete

Mine possible folder names from filenames, sampled document text, corpus word counts, document-frequency counts, existing metadata, and user-provided seeds. Send the counted words and candidate names to Jev so every possible folder receives an independent usefulness confidence for that collection. Jev then classifies files into approved candidates. A proposed folder is created only when enough files independently qualify above the confidence threshold.

The first 24-file mixed-format pilot produced 17 coherent moves and seven abstentions at the `0.70` threshold, then passed apply and undo verification. Discovery is enabled in the default preview, but mutations still require explicit apply. Larger labeled corpora are required before recommending `--apply` as a default workflow.

## 2. Reversible Plans and Undo — Implemented

Persist previews as immutable plans containing file fingerprints, proposed folders, destinations, confidence values, and Jev request IDs. Validate that inputs have not changed before applying. Record completed actions so moves can be undone and newly created empty folders can be removed safely.

## 3. Hierarchical Folder Configuration — Implemented

Support optional `.jfo.toml` files at any level. Configuration contains a folder description, organization context, explicit rules, candidate-folder seeds, and discovery policy. Context and rules inherit from ancestors; the nearest folder can add more specific guidance.

## 4. Lightweight Extraction Cache — Implemented

Store bounded extracted evidence in one hidden JSON file per directory. Invalidate entries using filename, size, nanosecond modification time, extraction settings, and cache schema version. Use atomic writes and avoid databases or central indexes.

## 5. Page-Limited Evidence — Implemented with Format Limitations

Retain only the configurable first pages when MarkItDown exposes page boundaries and enforce a character ceiling for formats without reliable pages. MarkItDown currently converts complete documents internally, so caching supplies the main repeated-run performance improvement. A true early-stop converter remains a possible specialized optimization.

## 6. User Rules and Organization Context — Context Implemented; Deterministic Rules Planned

Send applicable inherited rules and context to Jev in both discovery and classification calls. Support deterministic rules later for exact paths, extensions, filename patterns, dates, and metadata so obvious routing does not require a model call.

## 7. Correction Learning — Parked

Capture accepted overrides and rejected moves as a local labeled dataset. Use corrections as evaluation examples and propose explicit rules, but never silently change routing policy.

## 8. Decision Explanations — Parked

Show top candidate destinations, probability distributions, extraction method, and evidence snippets. Add commands for inspecting a decision and the exact bounded content sent to Jev.

## 9. Complete Hierarchical Routing — Implemented

Plan a full nested destination without mutating the tree between classification steps. Every hop must clear policy, the final path is visible before applying, and the weakest accepted hop becomes the route confidence. Existing nested folders can form a complete route; newly proposed folders remain leaves until a later run so discovery cannot generate an unbounded hierarchy.

## 10. Performance, Cost, and Scale Controls — In Progress

Add bounded concurrency, request chunking, rate limiting, cache statistics, estimated request counts, run budgets, and maximum-file limits. Avoid repeat extraction or classification for unchanged evidence and policies.

First slice complete: lightweight commands now defer MarkItDown, ONNX Runtime, and the TypeSafe SDK until a command actually needs extraction or model access. Five isolated launches improved from a 0.770-second average to 0.096 seconds, with the first launch falling from 1.807 to 0.153 seconds. Next slices are request-count previews and hard budgets, then bounded Jev concurrency with rate-limit tests.

## 11. Evaluation and Confidence Calibration — Planned

Build live Jev benchmarks spanning Office documents, PDFs, email, images, audio, archives, ambiguous cases, corrupt inputs, prompt injection, collisions, and deep trees. Report performance by file type, confidence band, and action type.

Pilot baseline: a fully cached 24-file recursive run completed in 3.99 seconds, with 17 approved moves and seven abstentions. This is a product smoke test, not a statistically useful benchmark.

## 12. Privacy and Data Controls — Planned

Preview the content sent to Jev, redact configured patterns, exclude sensitive paths, cap evidence per file and run, and provide cache inspection and clearing commands.

## 13. Watch Mode — Deferred

Offer opt-in continuous organization for inbox-like folders only after reversible plans, audit history, privacy controls, and evaluation safeguards are mature.

## 14. Duplicate and Filename Management — Planned

Detect exact and near duplicates, suggest canonical filenames, and offer date-aware naming. Keep these operations separate from folder-routing approval.

## 15. Suggested Folder Review UI — Planned

Provide an interactive terminal review for approving, renaming, merging, or rejecting proposed folders before any filesystem mutation.

## 16. Packaging and Automation Interfaces — Local Installer Implemented; Publishing Planned

JFO now builds standard wheel and source distributions, installs into an isolated user environment with uv or pipx, exposes `jfo --version` and `jfo doctor`, and runs independently of the source checkout. Publish the package to PyPI, host the installer behind a signed release URL, and add a Homebrew tap. Prefer a native installer plus Homebrew/PyPI over an npm shim that would add Node solely to launch Python. Machine-readable JSON output, stable documented exit codes, update checks, and automation integrations remain planned.

### Public rollout plan

1. **Resolve release identity.** Apache-2.0 is selected and the repository is `nitinnat/jev-file-organizer`. Confirm the package name, security-reporting channel, maintainer identity, and Jev/TypeSafe naming and attribution language.
2. **Create the public repository from a sanitized source tree.** Do not copy local `.env`, caches, plans, coverage data, generated samples, or built distributions. Add the license, contribution guide, code of conduct, security policy, issue forms, and pull-request template.
3. **Protect the repository.** Require pull requests and passing CI on the default branch. Enable secret scanning, push protection, Dependabot, private vulnerability reporting, and dependency review. Restrict workflow permissions to read-only unless a job explicitly needs more.
4. **Establish continuous verification.** Test Python 3.12 and 3.13 on macOS and Linux. Gate merges on Ruff, the complete test suite, package build, clean-wheel installation, `twine check`, static security analysis, dependency vulnerability scanning, and a credential-pattern scan.
5. **Rehearse distribution.** Publish a release candidate to TestPyPI from a protected GitHub environment using OIDC Trusted Publishing. Install that artifact on a clean macOS user account, run `jfo doctor`, preview a generated fixture, apply, undo, and verify uninstall/reinstall behavior.
6. **Ship the first release.** Freeze the dependency lock, generate release notes from the implementation log, create a signed `v0.2.0` tag, publish a GitHub release, and promote the exact CI-built artifacts to PyPI through Trusted Publishing. Never store a long-lived PyPI token in GitHub.
7. **Expand installation paths.** After the PyPI artifact is proven, host the installer at a stable HTTPS URL and add a Homebrew tap. Add an npm package only if JFO later ships signed per-platform native binaries rather than a Node-to-Python bootstrap wrapper.
8. **Operate the launch.** Publish known limitations and privacy behavior, watch installation and classification failures, label good-first issues, and define a patch-release process. If a release is unsafe, yank the PyPI version and publish a corrected patch rather than replacing an immutable artifact.

### Release gates

- No secrets, personal paths, or user documents in the release tree or built artifacts.
- Zero known high or critical dependency vulnerabilities and zero medium/high static-analysis findings.
- All supported OS/Python CI jobs pass from a clean checkout.
- Wheel and source archive metadata pass `twine check`; both install and launch cleanly.
- Preview, candidate audit, apply, stale-plan refusal, rollback, and undo have automated coverage.
- README accurately states what leaves the machine, what is cached, and how to recover.
- License, security policy, contribution rules, and maintainer/support channels are visible before the repository is announced.
