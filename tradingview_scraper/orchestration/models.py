from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class StageContext:
    """
    Minimal context object for passing runtime arguments to top-level CLI commands.

    WARNING: Do not pass this object deep into business logic services.
    Services should declare explicit arguments (e.g. `service(date, symbols)`).
    This context is ONLY for the orchestration layer to parse arguments and resolve paths.
    """

    run_id: str
    profile: str
    params: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_production(self) -> bool:
        return self.profile == "production" or self.profile.startswith("meta_production")
