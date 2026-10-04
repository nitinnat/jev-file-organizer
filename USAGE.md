# JFO Usage Guide

JFO is a preview-first command-line organizer powered by Jev. It reads filenames and bounded document text, scores possible destinations, and saves a plan before it changes anything.

The default safety rule is simple: running `jfo` creates a preview; only `jfo apply <plan-id>` or `jfo --apply` moves files. A move must have a Jev confidence of at least `0.70`.

## Install and configure

JFO currently supports Python 3.12 and 3.13. Until the first PyPI release, install it from a source checkout:

```bash
git clone https://github.com/nitinnat/jev-file-organizer.git
cd jev-file-organizer
./scripts/install.sh .
```

The installer uses `uv tool` when available and falls back to `pipx`. Docker is not required to use JFO.

Save your TypeSafe API key using the private interactive prompt, then check the installation:

```bash
jfo configure
jfo doctor
```

You can provide `TYPESAFE_API_KEY` through the environment instead. Do not commit API keys or `.env` files.

## Choose how folders are selected

### Let JFO discover folders

Change into the folder you want to organize and run:

```bash
cd ~/Downloads
jfo
```

JFO proposes a small set of category names from repeated filename concepts, file-type groups, document word counts, and optional configuration. Jev must approve a proposed category, and enough files must independently qualify for it before the folder appears in the plan.

### Supply the folder names yourself

Use `-f` or `--folders` when you already know the categories you want:

```bash
jfo -f "Finance, Travel, Medical"
```

The option can also be repeated:

```bash
jfo -f Finance -f Travel -f Medical
```

These names become the root-level destination allowlist for the plan. Existing matching folders are reused. Missing folders are proposed only when enough files clear the confidence threshold; an empty or weak category is not created.

### Use only folders that already exist

```bash
jfo --existing-folders-only
```

This disables new-folder proposals. At every level, files are evaluated against the immediate child folders already present under their parent. JFO continues through approved children until it reaches the deepest qualifying destination.

## Review the preview

A normal run prints:

- proposed folders, discovery confidence, supporting-file count, and candidate source;
- one row per file with its status, destination, confidence, and evidence source;
- the saved plan ID, elapsed time, approval count, and extraction-cache statistics.

Common statuses are:

| Status | Meaning |
| --- | --- |
| `move` | The best destination cleared the confidence threshold. |
| `low_confidence` | Jev suggested a folder, but the score was too low to move the file. |
| `no_match` | No supplied or discovered folder was a suitable destination. |
| `collision` | The destination already contains the same filename and the collision policy prevented a move. |

Files that do not qualify remain where they are. The preview itself does not create folders or move files.

## Apply and undo a plan

Apply exactly the plan you reviewed:

```bash
jfo apply <plan-id>
```

Before moving anything, JFO validates the source fingerprints, destinations, and approved folder set saved in the plan. If the tree changed after preview, it refuses unsafe work. An unexpected failure during application triggers rollback.

Undo the latest applied plan:

```bash
jfo undo
```

Undo restores the moved files and removes folders that JFO created if they are empty. It refuses to overwrite an occupied original path or restore a file that changed after it was moved.

For a one-command preview and apply:

```bash
jfo --apply
```

Preview and explicit apply are recommended until you are comfortable with the results.

## Organize another path

JFO uses the current directory by default. Use `--path` when you do not want to change directories:

```bash
jfo --path ~/Documents/Inbox
jfo -f "Work, Personal, Archive" --path ~/Documents/Inbox
```

Organization is recursive. JFO evaluates one parent-to-child hop at a time, but previews the deepest approved path and applies it as one move. For example, a root file can be planned directly into `Finance/Taxes/2026` when each existing folder in that path clears the threshold. Newly proposed folders are leaves for the current plan; run JFO again after applying if you want it to discover children inside them.

## Add rules and context

Create an optional configuration template in the current folder:

```bash
jfo init
```

Add templates to the existing folder tree:

```bash
jfo init --recursive
```

Edit `.jfo.toml` to describe the folder and guide decisions:

```toml
description = "Incoming household and business documents"
context = "Prefer a few durable categories over narrow topics."
rules = [
  "Keep tax documents separate from ordinary receipts.",
  "Travel bookings stay together.",
]

[discovery]
candidate_names = ["Finance", "Travel", "Medical"]
```

Descriptions, context, and rules inherit from ancestor folders. Child configuration can add more specific guidance.

## Inspect folder candidates

See every locally generated candidate before Jev filters them:

```bash
jfo candidates
```

This is a read-only audit and does not call Jev. It shows the evidence that produced each candidate, such as repeated filename terms, document vocabulary, file-type groups, or `.jfo.toml` entries.

## Useful options

| Option | Purpose |
| --- | --- |
| `-f, --folders TEXT` | Supply root destinations as a comma-separated list or repeated option. |
| `-p, --path PATH` | Organize a folder other than the current directory. |
| `-t, --threshold FLOAT` | Raise the placement threshold above the `0.70` minimum. |
| `--existing-folders-only` | Disable new-folder proposals. |
| `--max-new-folders N` | Limit proposed folders per parent. |
| `--min-folder-files N` | Require at least N qualifying files before creating a folder. |
| `--max-pages N` | Retain at most N detected page or slide sections per file. |
| `--max-chars N` | Limit retained extraction text per file. |
| `--cache / --no-cache` | Enable or disable extraction caching. |
| `--refresh-cache` | Re-extract files and replace matching cache entries. |
| `--collision skip\|rename` | Skip occupied destinations or choose a safe alternate name. |
| `--include-hidden` | Include hidden files and folders. |
| `-v, --verbose` | Show extraction and Jev request diagnostics. |
| `--model TEXT` | Select a Jev model alias or pinned version. |

Run `jfo --help` for the installed version's complete option list.

## Extraction, caching, and privacy

JFO uses Microsoft MarkItDown for every supported format. If a format is unsupported or conversion fails, it classifies from the filename only. Retained evidence is bounded by `--max-pages` and `--max-chars`.

MarkItDown may still process an entire document before JFO truncates the retained result. JFO stores reusable evidence in `.jfo-cache.json`, keyed by filename, size, modification time, extraction settings, and cache version. Use `--refresh-cache` after changing extraction behavior or when you want to force conversion again.

Jev receives filenames, bounded evidence, local word counts, candidate names and sources, and applicable rules or context. `.env`, private keys, and certificate bundles are excluded by default. Add root-level project rules when needed:

```toml
[privacy]
exclude = ["private/**"]
redact = ["(?i)account-[0-9]+"]
```

`exclude` values are path globs relative to the organized root. `redact` values are regular expressions replaced with `[REDACTED]` before evidence enters the cache and again before a Jev request. Invalid regular expressions stop the run with an error.

Use `jfo payloads .` to inspect the redacted payload evidence without contacting Jev. Add `--include-hidden` to audit hidden inputs too. Use `jfo cache inspect .` for cache counts and size, or `jfo cache clear .` to remove regenerable extraction and classification caches. Plans under `.jfo/plans/` are left untouched.

## Measure organizer performance

JFO can evaluate decisions against a labeled JSON manifest without moving files:

```bash
poetry run python scripts/generate_sample.py
poetry run jfo evaluate sample-folder \
  --manifest sample-manifest.json \
  --report evaluation-report.json
```

The report includes accuracy, move precision and recall, coverage, abstention rate, and end-to-end latency. Pin `--model` when comparing formal runs.

## Troubleshooting

Start with:

```bash
jfo doctor
```

- **Missing API key:** run `jfo configure` or export `TYPESAFE_API_KEY`.
- **A file stays in place:** check its preview status. `low_confidence` and `no_match` are intentional abstentions.
- **A folder is not proposed:** lower neither the hard safety floor nor support requirements casually; first inspect `jfo candidates`, add a clear `.jfo.toml` candidate or rule, or supply the folder with `-f`.
- **Stale extracted evidence:** run with `--refresh-cache`.
- **Destination already exists:** choose `--collision rename`, or resolve the conflicting file yourself and preview again.
- **Apply is refused:** the folder changed after preview. Generate a fresh plan and review it.
- **Audio conversion fails:** install FFmpeg and rerun `jfo doctor`.

## Command reference

```text
jfo                              Preview recursive organization
jfo -f "Finance, Travel"         Preview using supplied root destinations
jfo candidates                   Explain local candidate generation
jfo apply <plan-id>              Apply a saved and validated plan
jfo undo                         Undo the latest applied plan
jfo configure                    Save a TypeSafe API key privately
jfo doctor                       Check credentials and runtime dependencies
jfo init --recursive             Create optional config templates
jfo evaluate <path> --manifest…  Run labeled evaluation without moving files
jfo --help                       Show all options
```

JFO is an organizer, not a backup. Keep important files backed up independently.
