# OpenSWMM Benchmarks manual: Sphinx configuration.
#
# Build from the repository root (the same command CI runs):
#   pip install -r docs/manual/requirements.txt
#   sphinx-build -b html -W --keep-going docs/manual docs/manual/_build/html
#
# The reference pages import the harness, so the repository root goes on
# sys.path. The harness needs only numpy and PyYAML at import time; nothing
# here runs an engine.

import io
import os
import subprocess
import sys

from docutils import nodes
from docutils.core import publish_doctree
from sphinx.util.docutils import SphinxDirective

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO_ROOT)

# -- Project information ------------------------------------------------------

project = "OpenSWMM Benchmarks"
author = "Caleb Buahin"
# No copyright line: the repository is dedicated to the public domain
# (The Unlicense), so the footer shows none.

# -- General configuration ----------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.extlinks",
    "sphinx.ext.viewcode",
]

# :repo:`path` links a file in the repository on GitHub.
extlinks = {
    "repo": ("https://github.com/HydroCouple/openswmm.engine.benchmarks/blob/dev/%s", "%s"),
}

root_doc = "index"
language = "en"
exclude_patterns = ["_build", "_hydrocouple"]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autodoc_typehints_format = "short"
add_module_names = False

# -- HTML output --------------------------------------------------------------

html_title = "OpenSWMM Benchmarks"
html_theme_options = {
    "show_toc_level": 2,
    "header_links_before_dropdown": 6,
}


# -- CLI help, generated at build time ----------------------------------------

class CliHelp(SphinxDirective):
    """``.. cli-help:: <args>`` runs ``python <args> --help`` from the
    repository root and inserts its output, so the CLI reference always
    matches the code."""

    required_arguments = 1
    final_argument_whitespace = True

    def run(self):
        args = self.arguments[0].split()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", COLUMNS="80")
        proc = subprocess.run([sys.executable, *args, "--help"], cwd=REPO_ROOT,
                              capture_output=True, text=True, encoding="utf-8",
                              env=env, timeout=120)
        if proc.returncode != 0:
            raise self.error(f"python {' '.join(args)} --help exited "
                             f"{proc.returncode}: {proc.stderr.strip()[-300:]}")
        block = nodes.literal_block(proc.stdout, proc.stdout)
        block["language"] = "text"
        return [block]


def plain_text_docstrings(app, what, name, obj, options, lines):
    """Show a docstring that is not valid reStructuredText as preformatted text.

    The harness docstrings are written as plain text (indented examples,
    column layouts). Most parse cleanly as reStructuredText; the few that do
    not are shown verbatim instead of being rewritten for the manual."""
    if not any(line.strip() for line in lines):
        return
    stream = io.StringIO()
    publish_doctree("\n".join(lines), settings_overrides={
        "report_level": 2, "halt_level": 5, "warning_stream": stream})
    if stream.getvalue():
        lines[:] = ["::", ""] + ["   " + line for line in lines] + [""]


def setup(app):
    app.add_directive("cli-help", CliHelp)
    app.connect("autodoc-process-docstring", plain_text_docstrings)


# -- HydroCouple documentation theme ------------------------------------------
sys.path.insert(0, os.path.join(HERE, "_hydrocouple"))
import hydrocouple_theme  # noqa: E402

hydrocouple_theme.configure(
    globals(),
    manual_id="openswmm.engine.benchmarks",
    project_label="OpenSWMM Benchmarks",
    repository="https://github.com/HydroCouple/openswmm.engine.benchmarks",
    hero={
        "kicker": "OpenSWMM Benchmarks",
        "title": "Regression and verification for SWMM-compatible engines",
        "lede": "A tagged corpus of SWMM models and analytical test problems, and the "
                "Python harness that runs them through registered engines, grades parity, "
                "mass balance, stability and exact-solution accuracy, and renders the "
                "results dashboard and badges.",
        "actions": [
            {"label": "Get started", "url": "get-started", "style": "solid"},
            {"label": "CLI and API reference", "url": "reference/index", "style": "ghost"},
            {"label": "Engine manual", "url": "https://www.hydrocouple.org/openswmm.engine/",
             "style": "ghost"},
        ],
    },
)
