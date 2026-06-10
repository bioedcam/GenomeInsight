# Contributing

This repository keeps a few conventions that make the test suite honest — a test
should fail when the behavior it describes breaks. The most load-bearing
conventions are below; see `docs/test-suite-audit-and-ci-tiering.md` and
`docs/test-suite-debt-remediation-plan.md` for the history and rationale.

## Test assertion standards

Two anti-patterns defeat a test's purpose, because they pass for almost any
non-crashing code:

- **`assert x is not None` as the _only_ assertion** on a value-producing
  function. Most functions return a non-`None` object for any input, so this
  asserts "it ran," not "it produced the right answer." Assert the _value_: the
  field, the rendered string, the returned set, the computed number.
- **`assert response.status_code == 200` as the _only_ assertion** on an
  endpoint that returns data. A `200` with a wrong, empty, or duplicated body
  still passes. Assert the body too — the specific fields, counts, or rows you
  expect.

Both are fine as a _first_ line (a precondition) when followed by assertions on
the actual value. They are insufficient _alone_.

Concretely:

- For a value-producing function, assert the value — and where a SQL/text/JSON
  artifact is produced, assert its content (compile a query with `literal_binds`
  and assert the rendered SQL; assert VCF `REF`/`ALT`/`GT`; assert the exact
  diplotype, not `'3' in str(genotype)`).
- Prefer two-sided checks for filters: assert the excluded row is _absent_, not
  only that the returned rows match.
- Don't guard a loop with no membership check — `for item in items: assert ...`
  passes vacuously when `items` is empty. Assert `items` is non-empty first.
- Don't hand-overwrite the column under test in an "end-to-end" fixture; drive
  the production path so the test fails if that path regresses.
- Keep timing/perf assertions self-documenting: if a relaxed regression ceiling
  differs from the product target, inline the real target next to the assertion.

## hom_ref negative controls (carriage-gated modules)

A genotyping chip reports a call at _every_ probe regardless of whether the
person carries the variant, so a ClinVar-Pathogenic record at a
homozygous-reference position must **not** surface as a clinical finding. Every
analysis module that emits carriage-dependent findings should have at least one
test that seeds a non-carrier (`hom_ref`) Pathogenic variant and asserts it is
_absent_ from findings.

Shared builders live in `tests/backend/_carriage_fixtures.py`
(`hom_ref_pathogenic_row` / `het_pathogenic_row`). Risk-genotype (dosage-based)
modules use the equivalent "all-reference genotype → no finding" control rather
than a ClinVar-significance seed.

## Enforcement

These standards are **advisory**, surfaced as review comments by CodeRabbit via
`.coderabbit.yaml` (path-scoped to `tests/**`). They are intentionally _not_
CI-blocking: the existing suite predates the convention, so a blocking lint
would flag hundreds of legacy lines. The goal is to stop _new_ vacuous
assertions at review time, and to migrate legacy ones opportunistically.
