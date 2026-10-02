# Congressional legislators — Agent Guide

Read `README.md` for the source and generated data contracts. Preserve stable
identifiers, array/object shapes and unrelated changes. Do not regenerate
production outputs or edit source records as part of converter work.

## Converter scope

- `scripts/alternate_bulk_formats.py`: direct CLI for JSON and legacy CSV.
  Builds use `--json-only --input-dir <yaml-root> --output-dir <json-root>
  --force-refresh`. Explicit destinations must be outside the source tree and
  require JSON-only mode; no pickle caches are read/written. Legacy no-argument
  behavior still generates JSON and CSV in checkout-relative default locations.
- `scripts/test_alternate_bulk_formats.py`: offline synthetic CLI tests with
  copied scripts, real YAML loading and temporary output. Covers the five backend
  filenames/shapes, large social IDs, date values, skip/force behavior, isolation,
  legacy defaults, invalid options and rejection of unsafe YAML tags.
- `scripts/requirements.txt`: legacy script dependencies; this converter and its
  focused tests need only Python 3.9+ and PyYAML, not scraper dependencies.
- `scripts/converter_safety.py`: strict SafeLoader rejects duplicate keys, all
  merges and recursive aliases; output symlink preflight and POSIX no-follow
  descriptor-relative fresh-inode replacement protect JSON and legacy CSV.
  Kept self-contained in both converter submodules; keep safety policy aligned.

Converter errors never authorize publication; per-file writes are atomic, not
the entire dataset. Preserve source bytes/mtime and leave source snapshot binding
and independent validation to the build coordinator.

Test/build execution needs approval. Stop on the first validation failure and
report the exact error/proposed fix rather than fixing and retrying. Ask the
coordinator for a read-only TestValueReviewer review of new/affected tests before
handoff; static review is not a passing test run. Do not use a review ledger.
