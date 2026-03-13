import sys

if sys.version_info < (3, 12):  # noqa: UP036 — intentional runtime guard
    _v = sys.version_info
    raise SystemExit(
        f"GenomeInsight requires Python >= 3.12. Current: {_v[0]}.{_v[1]}.{_v[2]}. See README."
    )
