"""Optional and compatibility adapters for the V3 compiler.

Modules in this package must not import heavyweight ML dependencies at module
import time. Model runtimes are loaded lazily by the concrete adapter.
"""
