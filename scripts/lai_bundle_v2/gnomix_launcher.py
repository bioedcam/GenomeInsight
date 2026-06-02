#!/usr/bin/env python
"""Launch gnomix with a pandas>=2 compatibility shim.

gnomix (AI-sandbox/gnomix) was written for pandas<2 and calls the now-removed
``DataFrame.append`` in ``src/laidataset.py`` (the small-population
``include_all`` path, which fires whenever a reference population has very few
single-ancestry samples -- e.g. EUR has only 3 in the v2.0.0 panel). pandas
deprecated ``DataFrame.append`` in 1.4 and *removed* it in 2.0, so gnomix dies
with ``AttributeError: 'DataFrame' object has no attribute 'append'`` under the
cluster's ``gnomix`` conda env (pandas 2.3.3).

Rather than mutate the shared ``gnomix`` env (downgrade pandas) or edit the
third-party gnomix source, this launcher restores ``DataFrame.append`` /
``Series.append`` IN-PROCESS (delegating to ``pd.concat`` -- the documented
migration) and then runs gnomix unchanged. The patch lives only in this
subprocess; the installed env and the gnomix checkout are untouched.
``DataFrame.append`` is the ONLY pandas-2-removed API gnomix uses (verified by
grepping the gnomix tree for ``iteritems``/``.ix``/``lookup``/``pd.np``/
``get_values``/``mad`` and DataFrame ``.append`` -- only laidataset.py:331), so
this single shim is sufficient for gnomix to run to completion.

Usage -- a drop-in for ``python gnomix.py <args...>``:

    python gnomix_launcher.py /path/to/gnomix.py <gnomix arg1> ... <gnomix argN>

Every argument after the gnomix.py path is forwarded to gnomix verbatim, so
gnomix still sees ``len(sys.argv) == 9`` (8 positional + config) and infers
train mode exactly as it would when invoked directly.
"""
import os
import runpy
import sys

import pandas as pd


def _df_append(self, other, ignore_index=False, verify_integrity=False, sort=False):
    """pandas<2 ``DataFrame.append`` reimplemented on ``pd.concat``."""
    others = list(other) if isinstance(other, (list, tuple)) else [other]
    return pd.concat(
        [self, *others],
        ignore_index=ignore_index,
        verify_integrity=verify_integrity,
        sort=sort,
    )


def _series_append(self, to_append, ignore_index=False, verify_integrity=False):
    """pandas<2 ``Series.append`` reimplemented on ``pd.concat``."""
    others = list(to_append) if isinstance(to_append, (list, tuple)) else [to_append]
    return pd.concat(
        [self, *others],
        ignore_index=ignore_index,
        verify_integrity=verify_integrity,
    )


def install_pandas_append_shim():
    """Restore DataFrame/Series.append if the running pandas removed them (>=2.0).

    No-op on pandas<2 (the attribute already exists), so this launcher is safe to
    use regardless of the env's pandas version.
    """
    if not hasattr(pd.DataFrame, "append"):
        pd.DataFrame.append = _df_append
    if not hasattr(pd.Series, "append"):
        pd.Series.append = _series_append


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 2:
        sys.exit("usage: python gnomix_launcher.py /path/to/gnomix.py <gnomix args...>")

    gnomix_path = os.path.abspath(argv[1])
    if not os.path.isfile(gnomix_path):
        sys.exit(f"gnomix_launcher: gnomix entrypoint not found: {gnomix_path}")

    install_pandas_append_shim()

    # gnomix.py does `from src.* import ...`; running `python gnomix.py` puts the
    # gnomix dir on sys.path[0], but runpy.run_path does not -- add it explicitly
    # so the src package resolves against the gnomix checkout, not this launcher's
    # directory.
    gnomix_dir = os.path.dirname(gnomix_path)
    sys.path.insert(0, gnomix_dir)

    # Present gnomix with the argv it expects: argv[0]=gnomix.py, argv[1:]=its args.
    sys.argv = [gnomix_path] + argv[2:]
    runpy.run_path(gnomix_path, run_name="__main__")


if __name__ == "__main__":
    main()
