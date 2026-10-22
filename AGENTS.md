# Working in this app

Read [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md), [docs/DECISIONS.md](docs/DECISIONS.md), and [docs/PROGRESS.md](docs/PROGRESS.md) before changing the rental workflow. Use the current code and [README.md](README.md) for exact behavior.

- This is an existing Frappe/ERPNext app. Keep changes in this app and use Frappe DocType JSON, controllers, patches, and tests as appropriate.
- Follow the user's latest request when older specifications conflict. `CODEX_CRANE_RENTAL_APPROVED_IMPLEMENTATION.md` describes an earlier design and is not the current workflow.
- Preserve historical data through migration patches. Do not recreate the removed custom `Crane Project` DocType; ERPNext's native `Project` remains independent.
- Check `git status` before editing and preserve unrelated work in progress. This is a shared workspace.
- For schema changes, migrate a development site and run the relevant rental workflow test. Update these short docs when a decision or completed milestone changes.
- Update the files indside docs folder if needed 