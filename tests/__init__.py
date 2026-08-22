"""Harness test suite.

This file makes `tests` a regular package rather than a PEP-420 namespace
package. Without it, an environment that has the engine's Python bindings
installed (which ship their own top-level `tests` package) shadows this
directory, and `from tests.outfixture import ...` fails at collection: a
regular package anywhere on sys.path beats a namespace package at sys.path[0].
"""
