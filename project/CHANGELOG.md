# Changelog

All notable changes to `issabel_client` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] — 2026-08-08

### Added

- **`BatchContext` / `client.batch()`** — context manager that suppresses per-operation reloads and fires a single `manager/reload` at the end. Designed for bulk provisioning scenarios (create N extensions → 0 individual reloads → 1 reload at exit).
- **`ManagerProxy` / `client.manager`** — namespace exposing all 18 Asterisk Manager Interface (AMI) commands: `originate`, `queuestatus`, `status`, `extensionstate`, `dbget`, `dbput`, `dbdel`, `dbdeltree`, `dbshow`, `queueadd`, `queueremove`, `queuepause`, `queueunpause`, `queuelog`, `reload`, `hangup`, `getvar`, `userevent`.
- **`check_auth_status()`** — `GET /pbxapi/authenticate` to check current session state without re-authenticating.
- **`upload_moh_file(category, file_path, reload=True)`** — multipart upload of audio files to Music-on-Hold categories (avoids JSON content-type limitation of `_request`).
- **`AuthenticationError`** — new exception raised when token renewal fails, replacing silent failure.
- **`READ_ONLY_RESOURCES`** / **`GET_PUT_ONLY_RESOURCES`** — client-side guard rails in `__getattr__`; raises `NotImplementedError` with a clear message instead of letting a 405 bubble up from the server.
- **`timeout`** parameter in `__init__` (default `30s`) — propagated to all HTTP calls.
- **Context manager** (`__enter__` / `__exit__`) — closes the underlying `requests.Session` on exit.
- **`py.typed` marker** — PEP 561 compliance for type-checking tools (`mypy`, `pyright`).
- **`.gitlab-ci.yml`** — CI pipeline with `pytest` (Python 3.10/3.11/3.12 matrix), `flake8`, and `black --check`.

### Fixed

- **`reload=False` bug** — Previously, passing `reload=False` omitted the `reload` key from the request body. Because the Issabel API defaults to `reload=1` when the field is absent, this made `reload=False` a no-op. Fixed by using `data.setdefault("reload", "true" if effective_reload else "false")` — the field is now always explicitly set.
- **`reload` ignored on DELETE** — The `reload` parameter was silently discarded for `DELETE` requests. Fixed: `DELETE` now sends the `reload` flag in the JSON body (same as `POST`/`PUT`).
- **Network errors not caught** — `ConnectionError` and `Timeout` now return `{"error": "..."}` (consistent with `HTTPError` handling) instead of raising uncaught exceptions from `_request`.
- **`authenticate()` 403 not caught clearly** — HTTP 403 now raises `ValueError("Authentication failed: invalid credentials")` instead of a generic `HTTPError`.
- **`renew_token()` silent failure** — Renewal failures now raise `AuthenticationError` with a clear message asking the caller to re-authenticate.

### Changed

- **`params` is now `None` (not `{}`) when no query parameters are provided** — avoids sending an empty `?` in GET URLs.
- **`requires-python`** bumped from `>=3.7` to `>=3.10` — Python 3.7/3.8/3.9 are EOL.
- Classifier list updated to 3.10, 3.11, 3.12.

---

## [0.1.0] — 2026-08-01

### Added

- Initial release.
- Dynamic `__getattr__` CRUD: `get_`, `create_`, `update_`, `delete_` for any PBX resource.
- JWT authentication and automatic token renewal (HTTP 401 and legacy `status=expired`).
- `search()` method: `GET /{resource}/search/{term}`.
- Configurable SSL verification.
- `_safe_json_parse()` helper for non-JSON error responses.
