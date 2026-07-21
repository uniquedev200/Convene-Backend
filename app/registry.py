"""
DebateStack — Domain Registry (Person B)
==========================================
Single source of truth: DOMAIN_REGISTRY is defined in contracts_v2.py.
This module re-exports it for convenience so existing imports keep working.
"""

from .contracts import DOMAIN_REGISTRY, PresetId, PresetConfig, PersonaConfig

__all__ = ["DOMAIN_REGISTRY", "PresetId", "PresetConfig", "PersonaConfig"]
