# Architecture: Schubladensystem

## Rules
- `bot.py` only starts the bot and loads extensions.
- `app/core/` contains shared infrastructure and configuration, not feature behavior.
- Each feature is an independent package under `app/modules/`.
- Each extension exposes `async setup(bot)` and registers its own Cog.
- Per-server settings must be keyed by Discord guild ID; never hardcode one server.
- Feature-specific changes should stay inside that feature's package where possible.
- Add shared services only when two or more modules genuinely need them.
- Keep secrets in local `.env`; commit only `.env.example`.
- Add tests before changing shared infrastructure.

## Current feature drawers
- `logging_module`: event logging and configurable log destinations.
- `tickets`: panels, categories, ticket lifecycle and transcripts.
- `moderation`: moderation commands and safety controls.
- `dashboard/`: separate browser configuration interface (planned).

## Adding a feature
1. Create `app/modules/<feature>/`.
2. Add a Cog and `async setup(bot)`.
3. Add its extension path to `app/core/extensions.py`.
4. Test loading and failure isolation before adding behavior.
