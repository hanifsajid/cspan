# API reference

Generated from the package docstrings.

## Client

::: cspan.CSpanClient

## Formats

::: cspan.formats.to_records
::: cspan.formats.to_csv
::: cspan.formats.to_jsonl
::: cspan.formats.to_dataframe
::: cspan.formats.SUPPORTED_FORMATS
::: cspan.formats.SAVE_FORMATS

## Exceptions

```
CSpanError                  # base — catch this to catch everything
├── ValidationError         # invalid input, raised before any request
└── APIError                # the API returned an error response
    ├── AuthenticationError # missing/invalid API key (HTTP 401/403)
    ├── NotFoundError       # resource does not exist (HTTP 404)
    └── RateLimitError      # quota/throttle exceeded (HTTP 429)
```

::: cspan.exceptions
    options:
      show_root_heading: false
      show_docstring_description: false
      members:
        - CSpanError
        - ValidationError
        - APIError
        - AuthenticationError
        - NotFoundError
        - RateLimitError

## Constants

::: cspan.client.BASE_URL
::: cspan.client.ENV_API_KEY
