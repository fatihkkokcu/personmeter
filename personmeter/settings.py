import os


environment = os.getenv("PERSONMETER_ENV", "development").strip().lower()

if environment in {"production", "prod"}:
    from .settings_production import *  # noqa: F403,F401
elif environment in {"development", "dev"}:
    from .settings_development import *  # noqa: F403,F401
else:
    raise RuntimeError(
        "Unsupported PERSONMETER_ENV value. Use 'development' or 'production'."
    )
