# cspan

A Python client for the [C-SPAN Archives API](https://www.c-span.org/api/c-span/).

Typed, tested, and dependency-light. Covers the full documented API
(v2025-06-13) with retries, fast-fail validation, cursor pagination, pluggable
output formats (JSON / records / CSV / DataFrame), and one-call export to disk
(CSV / JSON / JSONL / XLSX / Parquet).

Base URL: `https://api.c-spanarchives.org/2.0`

[![PyPI](https://img.shields.io/pypi/v/cspan?cacheSeconds=3600)](https://pypi.org/project/cspan/)

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

!!! tip "Keep the key out of your code"
    Export `CSPAN_API_KEY` in your shell, or copy `.env.example` to `.env`
    and load it with a tool such as `python-dotenv`. The client reads the
    environment variable directly; it does not load `.env` files itself.

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

## Quick start

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

Continue with the [usage guide](usage.md) for output formats, pagination,
saving to disk, and error handling, or jump to the
[API reference](reference.md).

## Examples in the repository

- `examples/basic.py` — one call per endpoint, runnable.
- `examples/notebook.ipynb` — basics tour: every endpoint, output formats,
  pagination, saving, errors.
- `examples/advanced.ipynb` — every optional parameter, Lucene recipes, manual
  cursors, cross-endpoint joins, exports, quota handling.

## Author & maintainer

**Hanif Sajid** &middot; [hanifwrites@gmail.com](mailto:hanifwrites@gmail.com)
&middot; [hanifsajid.com](https://hanifsajid.com)
&middot; [GitHub](https://github.com/hanifsajid)

Bug reports and feature requests go to the
[issue tracker](https://github.com/hanifsajid/cspan/issues). Pull requests are
welcome; run `ruff check src tests`, `mypy`, and `pytest` before opening one.

## Scope and disclaimer

This is a client for C-SPAN's **REST API** only. Website/account features
(creating clips, free downloads, bookmarks, the ORGANIZATION search tab) are not
part of the API and are out of scope.

Unofficial. Not affiliated with or endorsed by C-SPAN. Use in accordance with
C-SPAN's terms and your API access agreement.
