"""TTrades Fractal Model style. The specification is ``rules.md`` in this folder."""

from companion.styles.ttrades.config import TTradesConfig, describe_config, load_config
from companion.styles.ttrades.style import STYLE_NAME, TTradesStyle, create_style

__all__ = ["STYLE_NAME", "TTradesConfig", "TTradesStyle", "create_style", "describe_config", "load_config"]
