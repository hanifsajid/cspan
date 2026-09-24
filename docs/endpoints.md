# Endpoints & live API notes

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

Built on top of these: `iter_records`, `save`, and `speeches_on_bill` (see the
[usage guide](usage.md)).

## `programs_search` query fields

Lucene syntax. Valid fields: `abstract`, `category`, `date`, `format`, `isbn`,
`location`, `person`, `personid`, `series`, `sponsor`, `subject`, `tag`, `text`.
`sort` accepts `popular` or `date` with a direction, e.g. `"date desc"`.

## Live API behavior worth knowing

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
