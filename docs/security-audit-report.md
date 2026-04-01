# GenomeInsight Security Audit Report (P4-24)

**Date:** 2026-03-31
**Scope:** Full application security audit per PRD P4-24
**Tests:** T4-24 (no outbound variant data), T4-25 (localhost-only binding)

---

## Executive Summary

GenomeInsight passes all security audit criteria. The application:
- Binds exclusively to `127.0.0.1` in all native deployment configurations
- Sends zero variant/genotype/sample data to external services
- Contains no telemetry, analytics, or tracking code
- Enforces localhost-only CORS
- Uses read-only SQLite connections for the SQL console
- Implements bcrypt password hashing with session-based auth

---

## 1. Network Binding (T4-25)

| Deployment | Binding | Status |
|-----------|---------|--------|
| Default config (`Settings.host`) | `127.0.0.1` | PASS |
| systemd service | `--host 127.0.0.1` (hardcoded) | PASS |
| launchd plist | `127.0.0.1` (hardcoded) | PASS |
| Docker Compose (host mapping) | `127.0.0.1:8000:8000` | PASS |
| Docker container (internal) | `0.0.0.0` | EXPECTED |

**Note:** The Docker container binds to `0.0.0.0` internally, which is standard Docker practice. The host-side port mapping in `docker-compose.yml` restricts external access to `127.0.0.1:8000`.

## 2. Outbound Data Flow (T4-24)

### 2.1 Outbound HTTP Requests (14 files)

All outbound requests download **public reference databases** or query public APIs with **non-sensitive metadata only**:

| Module | Destination | Data Sent Outbound |
|--------|------------|-------------------|
| `annotation/clinvar.py` | ftp.ncbi.nlm.nih.gov | None (GET download) |
| `annotation/dbnsfp.py` | Release archive | None (GET download) |
| `annotation/dbsnp.py` | ftp.ncbi.nlm.nih.gov | None (GET download) |
| `annotation/encode_ccres.py` | wenglab.org | None (GET download) |
| `annotation/gnomad.py` | googleapis.com | None (GET download) |
| `annotation/gwas.py` | ebi.ac.uk | None (GET download) |
| `annotation/mondo_hpo.py` | monarchinitiative.org | None (GET download) |
| `annotation/omim.py` | data.omim.org | API key only |
| `api/routes/genes.py` | rest.uniprot.org | Gene symbol only |
| `db/download_manager.py` | (generic) | None (GET download) |
| `db/update_manager.py` | ftp.ncbi.nlm.nih.gov | None (HEAD check) |
| `utils/pubmed.py` | NCBI Entrez | Gene symbol + PMIDs only |
| `utils/uniprot.py` | rest.uniprot.org | Gene symbol only |
| `utils/update_checker.py` | api.github.com | User-Agent header only |

### 2.2 Variant Data Isolation

- No `rsid`, `chrom`, `pos`, `genotype`, `zygosity`, or sample identifier is transmitted in any outbound request
- All variant data stays in local SQLite databases
- Frontend uses only relative `/api/` paths (no external fetch calls)

## 3. Telemetry

- **Backend:** Zero telemetry packages in `pyproject.toml`. No Sentry, Datadog, New Relic, or analytics imports.
- **Frontend:** Zero analytics packages in `package.json`. No Google Analytics, Mixpanel, Amplitude, Posthog, or tracking pixels.
- **Logging:** Local-only via `structlog` to `{data_dir}/logs/`. No log shipping to external services.

## 4. CORS Policy

Allowed origins (hardcoded in `main.py`):
- `http://localhost:5173`
- `http://localhost:8000`
- `http://127.0.0.1:5173`
- `http://127.0.0.1:8000`

Requests from external origins are rejected.

## 5. Authentication & Session Security

| Feature | Implementation | Status |
|---------|---------------|--------|
| Password hashing | bcrypt with salt | PASS |
| Session storage | Server-side in-memory dict | PASS |
| Session timeout | 4h inactivity (configurable) | PASS |
| Rate limiting | 5 attempts / 10-min window, 5-min lockout | PASS |
| Auth exemptions | `/api/health`, `/api/auth/login`, `/api/auth/status` only | PASS |
| Cookie security | `gi_session` with `credentials: include` | PASS |

## 6. SQL Console Security

| Defense Layer | Mechanism | Status |
|--------------|-----------|--------|
| Regex validation | Blocks INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, etc. | PASS |
| SQLite read-only mode | `file:{path}?mode=ro` URI | PASS |
| Query timeout | 30-second max execution | PASS |
| Row limit | 1,000 max rows per query | PASS |
| Character limit | 10,000 max query length | PASS |

## 7. Deployment Security

- Docker runs as non-root user (`appuser`)
- No secrets in Dockerfile
- No debug/reload mode in deployment configs
- Huey worker service depends on API service

## 8. Test Coverage

All security assertions are automated in `tests/backend/test_security_audit.py`:
- `TestLocalhostBinding` — T4-25 binding verification
- `TestCORSLocalhostOnly` — CORS origin enforcement
- `TestNoOutboundVariantData` — T4-24 static analysis
- `TestNoTelemetry` — Zero analytics verification
- `TestSQLConsoleReadOnly` — Write operation blocking
- `TestAuthSecurity` — Auth middleware, bcrypt, sessions, rate limiting
- `TestDeploymentSecurity` — Docker, systemd, deployment configs

---

## Conclusion

GenomeInsight meets all PRD security requirements for P4-24. The application maintains strict data privacy: all genetic/variant data remains local, all outbound communication is limited to downloading public reference databases and querying public APIs with non-sensitive metadata.
