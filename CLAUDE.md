# LifeTicket — Development Guidelines

## Versioning

- Every prompt that causes code to change should be treated as a **0.0.X feature update**.
- We start at **0.1.0**.
- Only the project owner decides when the first or second version digit is updated.
- The version number must be visible in the footer of the app at all times.
- The current version is defined in `app/version.py`.

## Debugging & Accountability

- If the app breaks after a code change, **assume the code change caused it**. Do not suggest infrastructure issues, container problems, or external factors as the cause. This is a self-contained Docker application — if it worked before the change and doesn't after, the change is the problem.
- When diagnosing a failure, immediately investigate your own changes as the root cause. Check for missing migrations, missing columns on existing databases, import errors, and template rendering errors before considering anything else.
- Never deflect blame or suggest the user check deployment infrastructure when you made the last change.
