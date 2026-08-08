"""Executable adapters for the canonical records CLI domain.

Each action delegates persistence to :mod:`brain.application.records` and owns
only CLI rendering. Parser aliases resolve to these canonical handlers, so no
parallel policy action layer exists.
"""
