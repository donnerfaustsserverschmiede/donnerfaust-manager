"""List feature modules to load.

Each feature lives in its own package and exposes async setup(bot).
To temporarily disable a feature, remove/comment its entry here; other modules
remain independent.
"""

EXTENSIONS: tuple[str, ...] = (
    "app.modules.logging_module",
    "app.modules.tickets",
    "app.modules.moderation",
    "app.modules.platform_audit",
)
