# CI Workflow Code Review

**File:** `.github/workflows/ci.yml`
**Reviewer:** code-reviewer
**Date:** 2026-02-10
**Context:** VN Stock Tracker monorepo CI/CD implementation

---

## Code Review Summary

### Scope
- Files reviewed: `.github/workflows/ci.yml`, `backend/requirements.txt`, `frontend/package.json`, `docker-compose.prod.yml`
- Lines of code analyzed: 77 (workflow) + supporting config files
- Review focus: New CI workflow implementation
- Updated plans: None (no plan file provided)

### Overall Assessment
**STRONG** - Workflow is well-structured, follows GitHub Actions best practices, and meets all stated requirements. Minor issues exist around dependency caching, test detection, and error handling. No security vulnerabilities detected.

---

## Critical Issues

**None found.**

---

## High Priority Findings

### 1. Pip Cache Missing Hash Validation
**Location:** Lines 18-22 (backend job)
**Issue:** `cache: pip` uses `requirements.txt` but doesn't hash the file content for cache invalidation.

**Problem:** If `requirements.txt` changes between runs, stale cache may persist until GitHub's 7-day expiry.

**Fix:**
```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
    cache: pip
    cache-dependency-path: backend/requirements.txt
```

**Status:** Currently implemented correctly, but...

**Additional recommendation:** Add explicit `pip install --upgrade pip` before installing dependencies to ensure latest pip version:
```yaml
- name: Install dependencies
  run: |
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install pytest pytest-cov pytest-asyncio httpx
```

### 2. Test Dependencies Not in requirements.txt
**Location:** Lines 24-27
**Issue:** `pytest`, `pytest-cov`, `pytest-asyncio`, `httpx` installed separately in CI, not tracked in project dependencies.

**Problem:**
- Developers may use different pytest versions locally
- No version pinning for test tools → CI can break if pytest releases breaking change
- `httpx` already in `requirements.txt` (line 9) → redundant install

**Fix:** Create `backend/requirements-dev.txt`:
```txt
-r requirements.txt
pytest==8.0.0
pytest-cov==4.1.0
pytest-asyncio==0.23.0
```

Update workflow:
```yaml
- name: Install dependencies
  run: |
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
```

---

## Medium Priority Improvements

### 3. Frontend Test Detection Logic Too Permissive
**Location:** Lines 56-62
**Issue:** `--if-present` flag + `2>/dev/null` suppresses errors, making debugging difficult.

**Current behavior:**
```bash
if npm run --silent test --if-present 2>/dev/null; then
  echo "Tests passed"
else
  echo "No test script found, skipping"
fi
```

**Problems:**
- `--if-present` returns exit 0 even if tests fail
- Error suppression hides configuration issues
- "Tests passed" message misleading when no tests exist

**Better approach:**
```yaml
- name: Run tests (if configured)
  run: |
    if grep -q '"test":' package.json; then
      npm run test
    else
      echo "No test script in package.json, skipping tests"
    fi
  continue-on-error: false
```

**Alternative (stricter):**
```yaml
- name: Check for test script
  id: check-tests
  run: echo "has_tests=$(jq -r '.scripts.test != null' package.json)" >> $GITHUB_OUTPUT

- name: Run tests
  if: steps.check-tests.outputs.has_tests == 'true'
  run: npm run test
```

### 4. Docker Build Verification Weak
**Location:** Lines 74-76
**Issue:** `grep -q 'stock-tracker'` matches ANY image with "stock-tracker" in name, including old/cached images.

**Current code:**
```bash
docker images --format '{{.Repository}}:{{.Tag}}' | grep -q 'stock-tracker'
```

**Problems:**
- Doesn't verify images were BUILT in this run
- Doesn't check all 3 expected images (backend, frontend, nginx)
- Silent failure if grep returns 0 from old images

**Recommended fix:**
```bash
- name: Verify images exist
  run: |
    images=(
      "stock-tracker-backend:latest"
      "stock-tracker-frontend:latest"
      "nginx:alpine"
    )

    for image in "${images[@]}"; do
      if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -qx "$image"; then
        echo "ERROR: Image $image not found"
        exit 1
      fi
      echo "✓ Verified: $image"
    done
```

**Note:** Adjust image names based on actual `docker-compose.prod.yml` naming (service names may differ from image names).

### 5. Missing Job Dependencies
**Location:** Lines 8-76
**Issue:** All 3 jobs run in parallel with no `needs:` declarations.

**Implication:**
- Docker build runs even if backend/frontend tests fail
- Wastes CI minutes building broken code
- No fail-fast mechanism

**Recommended structure:**
```yaml
jobs:
  backend:
    # ... existing config

  frontend:
    # ... existing config

  docker-build:
    needs: [backend, frontend]  # Only run after tests pass
    runs-on: ubuntu-latest
    # ... rest of config
```

### 6. No Workflow Timeout Protection
**Issue:** Jobs may hang indefinitely if SSI connection stalls during tests.

**Fix:** Add job-level timeouts:
```yaml
jobs:
  backend:
    runs-on: ubuntu-latest
    timeout-minutes: 15  # Add this
    # ...

  frontend:
    runs-on: ubuntu-latest
    timeout-minutes: 10  # Add this
    # ...

  docker-build:
    runs-on: ubuntu-latest
    timeout-minutes: 20  # Docker builds can be slow
    # ...
```

---

## Low Priority Suggestions

### 7. PR Branch Restriction Missing
**Location:** Lines 3-7
**Current:**
```yaml
on:
  push:
    branches: [master, main]
  pull_request:
```

**Suggestion:** Explicitly limit PR triggers to avoid CI spam:
```yaml
on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]
```

### 8. Coverage Report Artifact Upload
**Enhancement:** Store coverage reports for historical analysis:
```yaml
- name: Run tests with coverage
  run: pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80

- name: Upload coverage reports
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: coverage-reports
    path: backend/coverage.xml
    retention-days: 30
```

### 9. Node/Python Version Matrix Testing
**Suggestion:** Test against multiple versions to catch compatibility issues:
```yaml
backend:
  strategy:
    matrix:
      python-version: ["3.12", "3.13"]
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
```

**Trade-off:** Doubles CI time, only needed if multi-version support required.

### 10. Cache Key Optimization
**Current:** Default cache keys use `hashFiles()` automatically.
**Enhancement:** Manually specify for clarity:
```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
    cache: pip
    cache-dependency-path: |
      backend/requirements.txt
      backend/requirements-dev.txt  # If created
```

---

## Positive Observations

### Strengths
1. **Clean job separation** - Backend, frontend, Docker isolated properly
2. **Working directory defaults** - Smart use of `defaults.run.working-directory`
3. **Latest action versions** - `@v4`, `@v5` are current as of 2026
4. **Environment setup** - `.env.example` copy prevents missing config errors
5. **Coverage enforcement** - `--cov-fail-under=80` blocks merging low-coverage PRs
6. **Modern Python version** - 3.12 specified (matches project memory)
7. **Proper caching** - Both pip and npm caches configured
8. **npm ci usage** - Correct deterministic install vs `npm install`

### Best Practices Followed
- Action pinning to major versions (secure but not brittle)
- Separate jobs for different concerns
- Cache paths explicitly specified
- Coverage reports in multiple formats (terminal + XML)

---

## Security Considerations

### Reviewed Items
✓ **No secrets in workflow** - Uses env_file reference, not inline secrets
✓ **No sudo usage** - All operations userspace
✓ **No arbitrary code execution** - No `eval`, `curl | bash`, etc.
✓ **Action sources verified** - All actions from `actions/*` org (GitHub official)
✓ **Dependency sources** - npm/pip standard registries only

### Recommendations
1. **Add Dependabot** for auto-updating actions:
   ```yaml
   # .github/dependabot.yml
   version: 2
   updates:
     - package-ecosystem: github-actions
       directory: /
       schedule:
         interval: weekly
   ```

2. **Pin actions to SHA** (optional, for max security):
   ```yaml
   - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4
   ```

---

## Recommended Actions

### Immediate (Before Merge)
1. **Create `backend/requirements-dev.txt`** with pinned test dependencies
2. **Update pip install step** to use dev requirements
3. **Add `needs: [backend, frontend]`** to docker-build job
4. **Add job timeouts** (15min backend, 10min frontend, 20min docker)
5. **Fix Docker image verification** to check specific images
6. **Improve frontend test detection** logic (use `jq` or `grep -q` on package.json)

### Short-term (Next Sprint)
7. Add coverage artifact upload
8. Add PR branch restriction
9. Create Dependabot config for action updates
10. Document CI requirements in `docs/deployment-guide.md`

### Long-term (Optional)
11. Add Python/Node version matrix if multi-version support needed
12. Integrate SonarQube or similar code quality scanner
13. Add deployment job for master/main pushes (if applicable)

---

## Metrics

- **Type Coverage:** N/A (YAML workflow)
- **Test Coverage:** Enforced at 80% minimum (backend)
- **Linting Issues:** 0 (YAML syntax valid)
- **Security Issues:** 0 critical, 0 high, 0 medium

---

## Syntax Validation

✓ YAML syntax valid (verified with Python yaml parser)
✓ GitHub Actions schema compliance (manual review)
✓ Docker Compose syntax valid (verified via file read)

---

## Unresolved Questions

1. **Image naming:** Confirm exact Docker image names from `docker-compose.prod.yml` build tags - current verification assumes "stock-tracker-*" pattern
2. **Coverage XML path:** Does pytest write to `backend/coverage.xml` by default, or is `--cov-report=xml:coverage.xml` needed?
3. **npm test command:** Will frontend eventually have tests? If yes, prefer strict test enforcement over `--if-present`
4. **Environment variables:** Does Docker build need `.env` file in CI? Currently only referenced in `docker-compose.prod.yml` runtime
5. **CI environment:** Should SSI_CONSUMER_ID/SECRET be mocked in CI, or are tests isolated from external APIs?
