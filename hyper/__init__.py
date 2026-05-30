"""Hyper-Intelligence Layer package for JOSEPH.

The package stays intentionally lightweight so importing `hyper.bootstrap`
does not eagerly load every optional subsystem.
"""

from hyper.engine import HyperIntelligenceEngine

__all__ = ["HyperIntelligenceEngine"]
