# Contributing (backend)

## Formatting & linting

`ruff` and `black` are configured in `pyproject.toml` (line-length 110,
matching this codebase's existing style) but have **not** been applied
repo-wide yet. This was a deliberate decision made during the
`backend/final-hardening` pass, not an oversight:

- `black` at line-length 110 (and even 120) still reformats ~48 of 67
  files, because most of the diff isn't about line length - it's blank-line
  and trailing-comma normalization scattered across files that were
  clearly touched by several different contributors/tools over four
  phases. Mixed into a hardening PR, that diff would dwarf and obscure the
  actual correctness fixes.
- `ruff`'s default rule set flags 442 issues, but ~75% of them
  (`UP006`/`UP045`/`UP035`) are pyupgrade-style modernizations
  (`Dict[str, Any]` -> `dict[str, Any]`, `Optional[X]` -> `X | None`) that
  the codebase already applies consistently today via `typing` imports -
  adopting them is a style preference, not a bug fix, and would touch
  nearly every file with a type hint.
- `B008` (function-call-in-default-argument) fires 66 times on FastAPI's
  `Depends(...)` pattern, which is correct, required usage - not a real
  issue. It's disabled in `pyproject.toml` for this reason.

**What was fixed anyway, without a blanket formatting pass:** the small
number of genuinely broken import statements ruff's `I001` caught (two
separate `from app.api.deps import ...` / `from app.repositories.base
import ...` statements in `app/api/v1/farmers.py` that should have been
one each), and dead code (an unused `PaymentRepository.create()` method,
an unused `ErrorDetail`/`ErrorResponse` schema, a never-called `utcnow()`
in `app/schemas/centre.py`, an unused `httpx2` dependency, and six
near-duplicate `utcnow()` definitions consolidated into `app/core/time.py`).
These went into the normal cleanup commits alongside the code they were
touching, not a separate mechanical pass.

**When the team is ready to adopt full formatting** (e.g. after the
hackathon submission, when a large one-time diff is less disruptive):

```bash
pip install ruff black
black .
ruff check --fix .
```

Do this as its own PR/commit, with no logic changes mixed in, so the diff
stays reviewable.

## Running tests

See the main `README.md`. Use `requirements-dev.txt` (not
`requirements.txt`) locally - it adds `pytest`/`pytest-asyncio` on top of
the runtime dependencies. The production Docker image installs only
`requirements.txt`.
