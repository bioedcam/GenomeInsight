# VEP Bundle v2.0.0

- **Catalog source**: union of 23andMe v5 + AncestryDNA v2.0 (~840k sites, GRCh37)
- **Catalog SHA-256**: `<filled by Phase D>` (`union_sites_report.json::sha256_output`)
- **Site count**: `<filled by Phase D>` (`union_sites_report.json::union_count`; rs-only slice = `rs_count`)
- **Ensembl version**: 112
- **Build date**: `<YYYY-MM-DD>`
- **Bundle SHA-256**: `<filled by Phase D>`
- **Bundle size**: `<bytes>`
- **min_app_version**: `0.2.0`

## Notes

This release rebuilds the VEP bundle against the union 23andMe v5 ∪ AncestryDNA v2.0 catalog so AncestryDNA uploads achieve ≥95% rsID-bundle coverage at annotation time. The remaining ≤5% falls back to the coordinate-based lookup in `backend/annotation/engine.py` (defense-in-depth for `kgp*` proxies and other non-`rs*` IDs).

`bundle_metadata.bundle_version = "v2.0.0"` is recorded inside the SQLite for audit; the manifest's `version` field is the contract consulted by the runtime staleness gate.
