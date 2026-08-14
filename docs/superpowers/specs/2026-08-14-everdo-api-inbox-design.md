# Everdo API Inbox Support Design

## Goal

Add one explicit write operation to the existing CLI: create an Everdo Inbox item through Everdo's documented HTTP API. Existing query commands continue to read the local SQLite database in read-only mode.

The implementation must use only the Python standard library. It must not invoke `curl` or require packages installed with `pip`.

## Scope

The initial API support consists of a new command:

```text
everdo inbox-add TITLE [--note NOTE] [--focused] [--api-url URL] [--api-key KEY]
```

It calls the only operation described in the public Everdo API documentation: `POST /api/items/`. Reading through HTTP, updating items, deleting items, and adding a general API command hierarchy are out of scope.

## Configuration

The API URL is resolved in this order:

1. `--api-url`
2. `EVERDO_API_URL`
3. `https://localhost:11111`

The API key is resolved in this order:

1. `--api-key`
2. `EVERDO_API_KEY`

The command exits with an actionable error before making a request when no API key is available. The HTTP timeout is fixed at 30 seconds and is not exposed as a command-line option.

## Architecture

Add `src/everdo/api.py` containing a small `EverdoAPI` client. It owns URL construction, JSON serialization, HTTP transport, TLS configuration, response validation, and conversion of transport failures into a domain-specific exception. It uses `urllib.request`, `urllib.parse`, `json`, and `ssl` from the Python standard library.

The module exposes a typed result containing the item `id` and `created_on` timestamp. This keeps raw response dictionaries out of CLI code and gives the documented response a clear contract.

`build_parser()` in `src/everdo/main.py` defines the `inbox-add` arguments. `main()` handles this command before constructing `EverdoDB`, so adding an item does not require a local database or a valid `--db` path. All existing command paths and SQLite behavior remain unchanged.

## Request Flow

The command validates the title and resolves configuration. It then constructs an `EverdoAPI` client and sends:

```text
POST {base_url}/api/items/?key={url-encoded-api-key}
Content-Type: application/json
```

The UTF-8 JSON body always includes `title`. It includes `note` when supplied and `isFocused` when requested. URL joining must tolerate a trailing slash in the configured base URL without producing a malformed path.

Everdo commonly uses a self-signed certificate for its local HTTPS endpoint. The client therefore uses an SSL context that does not verify the certificate. Documentation must state that the URL and key should only target a trusted Everdo instance.

On a valid response, the client requires both documented fields, `id` and `createdOn`. The CLI prints the ID and converts `createdOn` from Unix seconds to a human-readable UTC date and time.

## Error Handling

The API module defines one public client exception for expected failures. It covers connection and DNS errors, the fixed 30-second timeout, non-success HTTP responses, invalid JSON, and missing or invalid response fields.

The CLI catches this exception, writes an error beginning with `Cannot create inbox item:` to stderr, and exits with status 1. Success exits with status 0. Error messages must not include the API key, including when an HTTP exception contains the request URL.

An empty title and a missing API key are rejected before network access. Unexpected programming errors are not folded into the client exception.

## Testing

Tests use `unittest`, matching the existing suite. HTTP tests mock `urllib.request.urlopen`; they never require a running Everdo instance or external network access.

Client tests cover:

- method, URL, encoded key, headers, and UTF-8 JSON body
- optional `note` and `isFocused` fields
- base URLs with and without a trailing slash
- the 30-second timeout and non-verifying SSL context
- valid response conversion
- connection, timeout, HTTP status, malformed JSON, and response-schema failures
- API key redaction from errors

CLI tests cover:

- parser arguments and the default API URL
- flag precedence over environment variables
- environment variable fallback
- missing key and empty title errors
- successful ID and UTC timestamp output
- client failures on stderr with exit status 1
- operation without opening SQLite, even when `--db` points to a missing file

Existing database and CLI tests remain unchanged and must continue to pass.

## Documentation

Update README feature, usage, and architecture descriptions so they no longer claim every operation is read-only. State precisely that existing query commands open SQLite read-only and `inbox-add` performs the sole write through Everdo's official API. Include examples for flags and environment variables, the default URL, API enablement, the 30-second timeout, and the trusted-instance warning for disabled certificate verification.

## Acceptance Criteria

- `python -m everdo inbox-add "New item" --api-key KEY` targets `https://localhost:11111/api/items/?key=KEY` without opening SQLite.
- `--note` and `--focused` produce the documented request fields.
- API URL and key resolution follow the documented precedence.
- No `curl` process, third-party package, or `pip` dependency is used.
- The request times out after 30 seconds and accepts Everdo's self-signed certificate.
- Successful output contains the returned ID and a UTC representation of `createdOn`.
- Expected configuration, transport, HTTP, and response errors produce safe stderr messages and status 1 without leaking the key.
- The complete `unittest` suite passes.
