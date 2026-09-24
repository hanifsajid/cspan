# cspan

A Python client for the [C-SPAN Archives API](https://www.c-span.org/api/c-span/).

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![PyPI](https://img.shields.io/pypi/v/cspan)

Typed, tested, and dependency-light. Covers the full documented API
(v2025-06-13) with retries, fast-fail validation, cursor pagination, pluggable
output formats (JSON / records / CSV / DataFrame), and one-call export to disk
(CSV / JSON / JSONL / XLSX / Parquet).

> Base URL: `https://api.c-spanarchives.org/2.0`

## Access (API key only)

Access is **only** through an API key. Request one by emailing
**api@c-spanarchives.org**. The key rides on every request in the `x-api-key`
header (this is required by C-SPAN's API Gateway; there is no token-exchange
flow). Over HTTPS this is the standard, secure pattern.

Provide the key directly **or** via the `CSPAN_API_KEY` environment variable:

```python
from cspan import CSpanClient

client = CSpanClient()                 # reads CSPAN_API_KEY
client = CSpanClient("your-api-key")   # or pass it explicitly
```

## Install

```bash
pip install cspan               # core
pip install "cspan[pandas]"     # + DataFrame output
```

For development, from a clone of the repo:

```bash
git clone https://github.com/hanifsajid/cspan
cd cspan
pip install -e ".[dev]"         # + test/lint/type tooling
```

Requires Python 3.8+ and `requests`.

## Usage

```python
from cspan import CSpanClient

client = CSpanClient()

# Search spoken mentions across C-SPAN programming
client.mentions("artificial intelligence", limit=5, mindate="2024-01-01")

# Find people, then fetch one in detail
client.people(last="Pelosi")
client.person("some-person-id")

# Bills, program search, and a single program
client.bills("infrastructure")
client.programs_search("category:Senate", sort="date desc")
client.program("some-video-id")
```

### Output formats

The API returns JSON; the client converts it for you. Choose a format once on
the client (`output_format=`) or per call (`format=`):

| `format` | Returns |
| --- | --- |
| `"json"` *(default)* | Decoded JSON (`dict`/`list`), exactly as sent. |
| `"records"` | A flat `list[dict]` of result rows. |
| `"csv"` | A CSV string (nested values become JSON text). |
| `"dataframe"` | A `pandas.DataFrame` (`pip install "cspan[pandas]"`). |

```python
client.people(last="Pelosi", format="csv")
client.bills("budget", format="records")
CSpanClient(output_format="dataframe").mentions("ai")
```

Standalone converters are exported too: `to_records`, `to_csv`, `to_jsonl`,
`to_dataframe`.

### Pagination

`iter_records` follows the `cursor` automatically and yields rows:

```python
for row in client.iter_records(client.mentions, query="climate", max_items=500):
    print(row)
```

Works with the cursor-based methods: `bills`, `mentions`, `people`,
`programs_search`.

### Saving to disk

`save()` fetches and writes results in one call. It can paginate the **full**
result set, write several file formats, and take a file **or** a directory path
(a directory auto-names the file `<endpoint>.<ext>` and is created if missing):

```python
# Full result set -> CSV in ./out/ (created if needed), file named bills.csv
client.save(client.bills, "out/", query="budget", format="csv")

# A specific file; only the first page; pretty JSON
client.save("mentions", "data/ai.json", query="ai", format="json", paginate=False)

# Cap the rows; Excel or Parquet (needs pandas + openpyxl/pyarrow)
client.save(client.people, "out/", last="Pelosi", format="xlsx", max_items=500)
```

File formats: `csv`, `json`, `jsonl`, `xlsx`, `parquet`. Returns the written path.

### Senators' speeches on a bill

The API has no structured bill-to-speech link, so `speeches_on_bill` searches
the spoken-word transcript (`/mentions`) for the bill's title and number, keeps
floor `Speech` / `Debate` segments, and groups them by senator (speakers whose
`/people/{personId}` record has "Senator" in its title):

```python
result = client.speeches_on_bill(
    title="Inflation Reduction Act", number="H.R. 5376", congress=117
)
for senator in result["senators"]:
    print(senator["name"], "-", len(senator["speeches"]), "segments")
```

Pass `title` and/or `number`. `congress` sets the date window (or give
`mindate` / `maxdate` explicitly). `videotypes` and `max_items` (a cap per
search variant) tune recall against your quota; each unique speaker costs one
extra `/people/{id}` call.

### Reliability

- **Retries**: transient failures (HTTP 429 and 5xx) are retried with
  exponential backoff, honoring `Retry-After`. Tune with
  `CSpanClient(max_retries=..., backoff_factor=...)`.
- **Timeouts**: every request uses `timeout` (default 30s).
- **Fast-fail validation**: malformed dates, a `sort` missing its direction,
  non-positive `limit`/`page`, empty required `query`, or an unknown `format`
  raise `ValidationError` *before* any network call.

### Errors

```python
from cspan import (
    CSpanError, ValidationError, APIError,
    AuthenticationError, NotFoundError, RateLimitError,
)
```

```
CSpanError                  # base — catch-all
├── ValidationError         # bad input, before the request (also a ValueError)
└── APIError                # API returned an error (has .status_code, .response)
    ├── AuthenticationError # 401/403 — missing/invalid key
    ├── NotFoundError       # 404 — person/program doesn't exist
    └── RateLimitError      # 429 — has .retry_after
```

## Endpoints

The full documented API (six endpoints, all `GET`):

| Method | Endpoint | Description |
| --- | --- | --- |
| `bills(query, *, cursor=None)` | `GET /bills` | Search Congressional bill information. |
| `mentions(query, *, limit, cursor, personid, date, maxdate, mindate, page, videotype)` | `GET /mentions` | Search programming for spoken words/phrases. |
| `people(query=None, *, first, last, cursor)` | `GET /people` | Search the people database. |
| `person(person_id)` | `GET /people/{personId}` | Fetch one person by internal or public ID. |
| `programs_search(query, *, cursor=None, sort=None)` | `GET /programs/search` | Lucene program search. |
| `program(video_id)` | `GET /programs/{videoId}` | Fetch one program by internal or public ID. |

Every method also accepts `format=` to override the output format for that call.

Built on top of these: `iter_records`, `save`, and `speeches_on_bill` (above).

### `programs_search` query fields

Lucene syntax. Valid fields: `abstract`, `category`, `date`, `format`, `isbn`,
`location`, `person`, `personid`, `series`, `sponsor`, `subject`, `tag`, `text`.
`sort` accepts `popular` or `date` with a direction, e.g. `"date desc"`.

### Live API behavior worth knowing

Verified against the API; these differ from, or aren't stated in, the docs:

- `/programs/{videoId}` rejects public ID strings (e.g. `"556839-1"`) with HTTP
  400 despite the docs listing them. Use the numeric `id` from a search result.
- `/people/{personId}` returns HTTP 200 with an empty payload for an unknown ID
  rather than a 404, so check the payload instead of catching `NotFoundError`.
- Lucene range queries (`date:[2024-01-01 TO 2024-12-31]`) return HTTP 500.
  Sort with `sort="date desc"` and filter client-side, or use `/mentions`, which
  has real `mindate` / `maxdate` parameters.
- A search matching nothing returns only a cursor; the client normalizes this to
  an empty result set (`[]` / `""`), never a phantom row.
- The portal's "Enable Search CSV Exports" setting affects only the portal's own
  web UI. The REST API returns JSON on every endpoint; all CSV/XLSX/Parquet
  output here is produced locally.
- Deep pagination will hit a request quota (HTTP 429). Use `max_items` while
  exploring, and raise `max_retries` / `backoff_factor` for long harvests.

## Documentation

Full docs (guide + generated API reference): https://hanifsajid.com/cspan/

```bash
pip install -e ".[docs]"
mkdocs serve             # live preview at http://127.0.0.1:8000
```

## Examples

- [`examples/basic.py`](examples/basic.py) — one call per endpoint, runnable.
- [`examples/notebook.ipynb`](examples/notebook.ipynb) — basics tour: every
  endpoint, output formats, pagination, saving, errors.
- [`examples/advanced.ipynb`](examples/advanced.ipynb) — every optional
  parameter, Lucene recipes, manual cursors, cross-endpoint joins, exports,
  quota handling.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests      # lint
mypy                      # type-check
pytest --cov=cspan        # test
```

## Scope

This is a client for C-SPAN's **REST API** only. Website/account features
(creating clips, free downloads, bookmarks, the ORGANIZATION search tab) are not
part of the API and are out of scope. See [CHANGELOG.md](CHANGELOG.md) for
release history.

## Author & maintainer

**Hanif Sajid** · [hanifwrites@gmail.com](mailto:hanifwrites@gmail.com) ·
[hanifsajid.com](https://hanifsajid.com) ·
[GitHub](https://github.com/hanifsajid). Issues and pull requests are welcome.

## Disclaimer

Unofficial. Not affiliated with or endorsed by C-SPAN. Use in accordance with
C-SPAN's terms and your API access agreement.
