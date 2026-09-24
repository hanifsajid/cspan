# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-09-24

First release on PyPI: `pip install cspan`. Documentation site at
https://hanifsajid.com/cspan/.

### Fixed
- Empty search results no longer produce a phantom row. When nothing matches,
  the API omits the result key and returns only `{"cursor": ...}`; `to_records`
  treated that envelope as a one-row record, so `format="records"` returned a
  fake row, `format="csv"` emitted a bogus `cursor` column, and `iter_records`
  / `save()` wrote it to disk. Cursor-only envelopes are now an empty result set.
- `speeches_on_bill` no longer raises `ValidationError: 'person_id' is required`.
  It inherited the phantom row above (and any segment lacking a `personid`) and
  called `person(None)`, which made the method fail for every input. Segments
  with no speaker id are now skipped. Verified against the live API.

### Added
- `CSpanClient.speeches_on_bill(...)` — find every senator who spoke about a
  bill on the floor, grouped with their transcript segments. Searches
  `/mentions` for title/number phrase variants within the Congress date window,
  keeps `Speech`/`Debate` segments, and makes one `/people/{id}` lookup per
  unique speaker.
- `examples/advanced.ipynb` — advanced examples for all six endpoints: every
  optional parameter, Lucene query recipes, manual cursor control,
  cross-endpoint joins, dataset export, quota handling, and validation.
- `examples/notebook.ipynb` rewritten as a basics tour with a working call for
  each of the six endpoints, using real IDs.

### Documented
- `/programs/{videoId}` rejects public ID strings (e.g. `"556839-1"`) with HTTP
  400 despite the API docs listing them; use the numeric `id`.
- `/people/{personId}` returns HTTP 200 with an empty payload for unknown IDs
  rather than a 404.
- `/programs/search` returns HTTP 500 for Lucene range queries such as
  `date:[2024-01-01 TO 2024-12-31]`; sort and filter client-side instead.
- The portal's "Enable Search CSV Exports" setting does not affect the REST API,
  which returns JSON on every endpoint. All CSV/XLSX/Parquet output is
  produced locally by this client.

## [0.2.0] - 2026-06-18

### Fixed
- `iter_records` now stops when the pagination cursor repeats. The API returns a
  `cursor` on every page (including the last), so without this guard pagination
  could loop until rate-limited. Verified against the live API.

### Added
- `CSpanClient.save(...)` — fetch and write results to disk in one call:
  file or directory dest (directory auto-names `<endpoint>.<ext>` and is created
  if missing), optional full-dataset pagination, and `csv` / `json` / `jsonl` /
  `xlsx` / `parquet` formats. Plus a `to_jsonl` helper and `SAVE_FORMATS`.
- Fast-fail input validation (`ValidationError`) for dates (`yyyy-mm-dd`),
  `sort` direction, positive integers (`limit`, `page`), required `query`,
  path IDs, and output `format`.
- Typed exception hierarchy: `APIError`, `AuthenticationError`, `NotFoundError`,
  `RateLimitError`, `ValidationError` (all under `CSpanError`), each carrying
  `status_code`/`response` where relevant.
- Automatic retries with exponential backoff on HTTP 429 and 5xx, honoring the
  `Retry-After` header.
- API key can be read from the `CSPAN_API_KEY` environment variable.
- `iter_records(...)` cursor auto-pagination helper.
- Output-format selection (`output_format=` / per-call `format=`): `json`,
  `records`, `csv`, `dataframe`, plus standalone `to_records`/`to_csv`/`to_dataframe`.
- Context-manager support and `close()`.
- `py.typed` marker (PEP 561), `src/` layout, test suite, CI, ruff/mypy config.

## [0.1.0] - 2026-06-17

### Added
- Initial client for the six C-SPAN Archives API endpoints: `bills`,
  `mentions`, `people`, `person`, `programs_search`, `program`.
