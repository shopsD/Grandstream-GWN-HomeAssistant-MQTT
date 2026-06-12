from dataclasses import dataclass

from gwn.authentication import GwnConfig

@dataclass(slots=True)
class IntegrationConfig:
    gwn_config: GwnConfig
    refresh_period_s: int = 30
