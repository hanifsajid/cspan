# Usage guide

## Output formats

The API returns JSON; the client converts it for you. Choose a format once on
the client (`output_format=`) or per call (`format=`):

| `format` | Returns |
| --- | --- |
| `"json"` *(default)* | Decoded JSON (`dict`/`list`), exactly as sent. |
| `"records"` | A flat `list[dict]` of result rows. |
| `"csv"` | A CSV string (nested values become JSON text). |
| `"dataframe"` | A `pandas.DataFrame` (`pip install -e ".[pandas]"`). |

```python
client.people(last="Pelosi", format="csv")
client.bills("budget", format="records")
CSpanClient(output_format="dataframe").mentions("ai")
```

Standalone converters are exported too: `to_records`, `to_csv`, `to_jsonl`,
`to_dataframe`. See the [formats reference](reference.md#formats).

## Pagination

`iter_records` follows the `cursor` automatically and yields rows:

```python
for row in client.iter_records(client.mentions, query="climate", max_items=500):
    print(row)
```

Works with the cursor-based methods: `bills`, `mentions`, `people`,
`programs_search`.

!!! info "Why it stops on a repeated cursor"
    The API returns a `cursor` on every page, including the last one. The
    client treats a cursor it has already followed as the end of the result
    set; without that guard pagination would loop until rate-limited.

## Saving to disk

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

## Senators' speeches on a bill

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

## Reliability

- **Retries**: transient failures (HTTP 429 and 5xx) are retried with
  exponential backoff, honoring `Retry-After`. Tune with
  `CSpanClient(max_retries=..., backoff_factor=...)`.
- **Timeouts**: every request uses `timeout` (default 30s).
- **Fast-fail validation**: malformed dates, a `sort` missing its direction,
  non-positive `limit`/`page`, empty required `query`, or an unknown `format`
  raise `ValidationError` *before* any network call.

## Errors

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

```python
from cspan import APIError, CSpanClient, RateLimitError

client = CSpanClient()
try:
    rows = list(client.iter_records(client.bills, query="budget", max_items=200))
except RateLimitError as exc:
    print("Rate limited; retry after:", exc.retry_after)
except APIError as exc:
    print("API error:", exc, "status:", exc.status_code)
```

## Lifecycle

The client owns a `requests.Session`. Use it as a context manager or call
`close()` when you are done:

```python
with CSpanClient() as client:
    client.people(last="Pelosi")
```
