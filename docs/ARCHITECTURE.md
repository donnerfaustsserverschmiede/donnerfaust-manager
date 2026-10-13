# Architecture: Donnerfaust Manager „Schubladensystem“

## Product rule
The website is the primary control panel, inspired by established Discord bot dashboards. Server administrators should be able to invite the bot and configure features in the browser. Chat commands are optional fallbacks/diagnostics, not the main setup experience.

## Components
- `bot.py`: starts the Discord bot and loads extensions.
- `app/core/`: shared infrastructure and configuration, not feature behavior.
- `app/modules/<feature>/`: independent feature modules.
- `dashboard/`: separate web application for Discord OAuth login, server selection, bot invitation, and per-server configuration.
- Shared persistent storage/service layer: dashboard and bot must read/write the same per-guild settings.

## Rules
- Each feature is an independent package under `app/modules/`.
- Each extension exposes `async setup(bot)` and registers its own Cog.
- Per-server settings must be keyed by Discord guild ID; never hardcode one server.
- Dashboard API must verify the current Discord user's `MANAGE_GUILD` permission before reading or writing settings for a guild.
- Never trust a guild ID supplied by the browser without server-side authorization.
- Never expose bot tokens or OAuth client secrets to browser code or commit them to GitHub.
- Use environment variables for secrets and a persistent database for hosted deployments.
- Feature-specific changes should stay inside that feature's package where possible.
- Add tests for authorization and settings isolation before deploying dashboard changes.

## Current feature drawers
- `logging_module`: initial event logging and legacy command configuration.
- `tickets`: initial ticket creation/closing commands and views; requires live tests.
- `moderation`: initial slash moderation commands; requires live tests.
- `dashboard/`: specification only; web application not implemented yet.

## Implementation order
1. Persistent shared settings store and schema.
2. Discord OAuth2 login and verified guild permissions.
3. Invite button and guild selector.
4. Dashboard API with per-guild authorization.
5. Logging settings page.
6. Ticket settings page.
7. Moderation settings page.
8. Audit, tests, deployment and monitoring.
