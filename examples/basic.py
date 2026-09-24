"""Minimal usage example for the C-SPAN Archives API.

Calls all six documented endpoints once each. Set your API key, then run:

    export CSPAN_API_KEY="your-api-key"
    python examples/basic.py

For richer examples see the notebooks in this directory:
``notebook.ipynb`` (basics) and ``advanced.ipynb`` (every parameter,
Lucene recipes, cross-endpoint workflows).
"""

from cspan import APIError, CSpanClient, RateLimitError

client = CSpanClient()  # reads CSPAN_API_KEY

try:
    # GET /mentions — words or phrases spoken on C-SPAN.
    mentions = client.mentions("artificial intelligence", limit=3, mindate="2024-01-01")
    for row in mentions["mentions"]:
        print(row["begintime"][:10], "|", row["text"][:70], "...")

    # GET /bills — Congressional bill information.
    bills = client.bills("infrastructure")
    for row in bills["bills"][:3]:
        print(row["congress"], row["billnumber"], row["billtitle"][:60])

    # GET /people — search people, then GET /people/{personId} for one record.
    people = client.people(last="Pelosi")
    first_id = people["people"][0]["id"]
    person = client.person(first_id)
    print(person["people"][0]["name"], "-", person["people"][0]["title"])

    # GET /programs/search — Lucene syntax; sort needs a direction.
    programs = client.programs_search("text:climate", sort="date desc")
    top_id = programs["programs"][0]["id"]

    # GET /programs/{videoId} — full detail for one program (numeric id).
    program = client.program(top_id)
    print(program["date"][:10], "|", program["title"][:60])

    # Per-call output formats: json (default), records, csv, dataframe.
    print(client.people(last="Pelosi", format="csv")[:200])

    # Auto-paginate across pages, capped at 200 rows.
    rows = list(client.iter_records(client.bills, query="budget", max_items=200))
    print(f"paginated {len(rows)} bill rows")
except RateLimitError as exc:
    print("Rate limited; retry after:", exc.retry_after)
except APIError as exc:
    print("API error:", exc, "status:", exc.status_code)
