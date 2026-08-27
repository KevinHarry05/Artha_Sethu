# Auth (signup / login) -- connected to FronteEnd's actual build

This replaces the first draft of this doc. That draft (and the routes it
described -- POST /signup, POST /login, a separate `username` field, an
8-character password minimum) was written before FronteEnd's sign-up/login
pages existed. Once FronteEnd was built, its actual request shape didn't
match that draft in several places, so the backend was updated to match
what FronteEnd really sends -- not the other way around, since FronteEnd's
UI/UX decisions (field names, copy, validation) are the settled reference
now.

## What changed from the first draft, and why

| | First draft | Now (matches FronteEnd) |
|---|---|---|
| Routes | `POST /signup`, `POST /login` | `POST /auth/signup`, `POST /auth/login` (FronteEnd calls `${API}/auth/${mode}`) |
| Login field | separate `username` | `name` -- FronteEnd's own copy is "Your name becomes your login handle"; there's no separate username input anywhere in the UI |
| Signup fields | `name, age, business_category, size, username, password` | `name, age, business_category, company_size, password` (`size` renamed `company_size` to match FronteEnd's field name exactly) |
| Password minimum | 8 characters | 4 characters -- matches FronteEnd's own hint text ("Minimum 4 characters.") exactly, so a signup that passes the frontend's own check never gets rejected by the server |
| Response shape | flat profile object | `{access_token, user: {...}}` -- FronteEnd does `onAuth(data.access_token, data.user)` and stores both in `localStorage` |

The 4-character password minimum is worth a second look if this goes
anywhere near real users -- it's weak by normal standards. It was matched
here specifically so the two sides don't disagree, not because it's a
recommended value. If you want it raised, raise it in both places at once
(the hint text in FronteEnd's `Auth` component and `MIN_PASSWORD_LENGTH` in
`modules/auth/__init__.py`) so they stay in sync.

## Endpoints

Both use `Form(...)` fields (`FormData`, not JSON) -- same as `/assess`.

### `POST /auth/signup`
Fields: `name, age, business_category, company_size, password`.
- `200` -- `{"access_token": "...", "user": {"user_id", "name", "age", "business_category", "company_size"}}`
- `400` -- validation failed -- `{"error": "..."}`
- `409` -- an account with that name already exists -- `{"error": "..."}`

### `POST /auth/login`
Fields: `name, password`.
- `200` -- same shape as signup
- `401` -- `{"error": "Incorrect name or password."}` (deliberately identical whether the name doesn't exist or the password is wrong)

No endpoint currently requires `access_token` on subsequent requests
(`/assess` doesn't check it) -- it's issued and stored (see `sessions`
table below) so it's real and revocable, but nothing enforces it yet.

## Schema

`db/auth_schema.sql` (separate file, `schema.sql` untouched):

**`users`** -- `user_id` (UUID PK), `name` (UNIQUE -- doubles as the login
handle), `password_hash`, `password_salt`, `age` (CHECK 18-100),
`business_category` (must be Dairy/Retail/Textiles), `company_size` (free
text -- matches FronteEnd's select: Solo / 2-5 people / 6-20 people / 20+
people), `created_at`.

**`sessions`** -- `token` (PK), `user_id` (FK), `created_at`. One row per
issued token.

Apply both with:
```
python3 -m db.init_db          # core schema (villages, population, ...)
python3 -m db.init_auth_db      # this file
```

## Dashboard summary (also new)

FronteEnd's Dashboard/Overview tab expects `report.dashboard` on the
`/assess` response -- an object `{overall_readiness_score, note,
component_scores, opportunity_class}`. This didn't exist in the API before
FronteEnd was built expecting it, so it was added: `pipeline.py`'s
`_compute_dashboard_summary()` derives three 0-100 component scores
(`market_opportunity` from `demand_gap_pct`, `financial_viability` from
the scenario pass rate `repayable_count/n_scenarios`, `risk_safety` from
inverting `risk_severity_score`), averages them into
`overall_readiness_score`, and writes a one-line `note` naming whichever
component scored lowest. Deterministic, code-computed, no LLM -- same rule
as everything else in this pipeline.

## Repayment schedule (also new)

FronteEnd's Financial Calculator renders a full per-installment table from
`repayment_viability.schedule` -- an array of `{installment_number, phase,
opening_balance, interest_charged, principal_component,
installment_amount, seasonality_factor, adjusted_installment_amount,
closing_balance}`. The pipeline always computed this internally
(`build_amortisation_schedule()`) but `/assess` previously only returned
the aggregate (`schedule_length`, `total_repayment`, etc.) -- the full row
list is now included too (`pipeline.py`, one line: `"schedule": [asdict(r)
for r in schedule]`).

## Verified

- `/auth/signup`, `/auth/login`, and `/assess` are all correctly
  registered (confirmed via `TestClient` + `/openapi.json`).
- CORS: a request with `Origin: http://localhost:3000` gets back
  `access-control-allow-origin: http://localhost:3000` -- FronteEnd's
  actual dev server origin.
- Password validation matches FronteEnd's stated policy exactly: length 2
  is rejected (`400`), length 4 passes validation (fails only on the
  missing Postgres connection in this environment, which is the correct,
  clean-error behavior -- same as `/assess` already had).
- Full test suite: 35 passed, 25 failed -- the 25 failures are all
  pre-existing Postgres-connection errors (no DB available in this
  environment), identical in count/name to the failures before this
  round of changes. `tests/test_auth_security.py` (5 tests, no DB needed)
  passes.
