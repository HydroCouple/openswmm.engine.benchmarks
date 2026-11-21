=============
Suite modules
=============

Every suite is a ``suites/<name>/suite.py`` module with ``run(argv)`` and
``report(argv)`` (see :doc:`../concepts/architecture`). This page documents
the protocol template and the suites that need nothing beyond the harness to
import. The other suites are described, with their options, in their READMEs
(:doc:`../suites`).

.. contents:: Modules
   :local:
   :depth: 1

Protocol template
=================

.. automodule:: suites._suite_template

parity
======

.. automodule:: suites.parity.suite

analytical/manufactured
=======================

.. automodule:: suites.analytical.manufactured.suite

analytical/swashes
==================

.. automodule:: suites.analytical.swashes.suite

analytical/transitions
======================

.. automodule:: suites.analytical.transitions.suite
