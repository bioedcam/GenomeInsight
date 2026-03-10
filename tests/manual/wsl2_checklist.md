# WSL2 Manual Testing Checklist

## Pre-release WSL2 Verification

Run these checks on a WSL2 environment before each release.

### Environment Setup

- [ ] Python 3.12+ available
- [ ] Node 20+ available
- [ ] `pip install -e ".[dev]"` succeeds
- [ ] `cd frontend && npm install` succeeds

### Backend

- [ ] `make test-backend` passes
- [ ] `make run-api` starts without errors
- [ ] Health endpoint responds: `curl http://localhost:8000/api/health`

### Frontend

- [ ] `make test-frontend` passes
- [ ] `make run-frontend` starts without errors
- [ ] Browser can access http://localhost:5173

### E2E

- [ ] `make test-e2e` passes (Chromium)

### Services

- [ ] systemd units install: `systemctl --user enable genomeinsight-api`
- [ ] systemd units start: `systemctl --user start genomeinsight-api`
