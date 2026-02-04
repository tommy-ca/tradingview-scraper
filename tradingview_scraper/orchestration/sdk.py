"""
Compatibility Shim for QuantSDK.

This module provides backward compatibility for external components and agents
that still reference the legacy `QuantSDK` class. It aliases `QuantLib` to `QuantSDK`.
"""

from tradingview_scraper.lib.common import QuantLib

# Shim for backward compatibility
QuantSDK = QuantLib
