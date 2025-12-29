# Incident Postmortem: 2024-01-15 - Authentication Failure After Deployment

## Meta

- **Date**: January 15, 2024
- **Incident Duration**: 37 minutes (03:12 - 03:49 UTC)
- **Detection Time**: 2 minutes (alert fired at 03:14 UTC)
- **Time to Mitigation**: 15 minutes (rollback complete at 03:27 UTC)
- **Time to Full Resolution**: 22 minutes additional monitoring
- **Severity**: SEV2 (Major degradation)
- **Status**: Resolved
- **Incident Commander**: Alex Chen
- **Responders**:
  - Primary: Alex Chen (on-call SRE)
  - Secondary: Jordan Kim (backup on-call)
  - Escalation: Sam Rodriguez (Engineering Lead)
- **Status Page**: https://status.company.com/incidents/2024-01-15-auth-failure

## Executive Summary

On January 15, 2024 at 03:12 UTC, deployment of version 1.5.2 introduced a bug in the authentication middleware that caused 45% of agent requests to fail. The issue affected approximately 3,000 users and resulted in 4,500 failed requests before a rollback to version 1.5.1 resolved the incident. The root cause was uncaught exception handling for expired refresh tokens, which was not covered by integration tests.

## Impact

### Users
- **Users affected**: ~3,000 unique users
- **Failed requests**: 4,500 total
- **Success rate during incident**: 55% (normal: 99.9%)
- **Peak error rate**: 45% at 03:15 UTC

### Business
- **Revenue impact**: Estimated $2,000 (failed transactions + customer support)
- **Support tickets**: 47 tickets created
- **Customer sentiment**: 23 complaints on social media

### SLA
- **SLO**: 99.9% monthly availability
- **Actual**: 99.7% for January 15th
- **Error budget consumed**: 12.3% of monthly budget
- **SLA breach**: Yes (daily availability fell below 99.9%)

### Engineering
- **Engineering hours**: 2.5 hours (1.5h incident response + 1h postmortem)
- **Deployment freeze**: 6 hours (until postmortem complete)

## Timeline

All times in UTC (Pacific: UTC-8)

| Time (UTC) | Time (PT) | Event | Responder |
|------------|-----------|-------|-----------|
| 03:00 | 19:00 | On-call shift change. Alex Chen now primary on-call. | Alex |
| 03:10 | 19:10 | Deployment of v1.5.2 begins via CI/CD (auto-deploy after tests pass) | CI/CD |
| 03:10 | 19:10 | Canary deployment starts (5% of traffic for 5 minutes) | CI/CD |
| 03:11 | 19:11 | Canary health checks passing | CI/CD |
| 03:12 | 19:12 | Canary complete. Rolling update to all pods begins. | CI/CD |
| 03:12 | 19:12 | **Error rate starts increasing** (0.1% → 5%) | - |
| 03:13 | 19:13 | Error rate climbs to 15% as more pods update to v1.5.2 | - |
| 03:13 | 19:13 | Rolling update 40% complete (4/10 pods on v1.5.2) | CI/CD |
| 03:14 | 19:14 | **Alert fires**: "High error rate >10%" | Prometheus |
| 03:14 | 19:14 | **Alex acknowledges alert** (2 min after errors started) | Alex |
| 03:14 | 19:14 | Rolling update 70% complete (7/10 pods on v1.5.2) | CI/CD |
| 03:15 | 19:15 | **Error rate peaks at 45%** (rolling update 100% complete) | - |
| 03:15 | 19:15 | Alex opens incident in Slack #incidents | Alex |
| 03:16 | 19:16 | Alex checks Grafana dashboard, sees errors = "AuthenticationError" | Alex |
| 03:17 | 19:17 | **Alex identifies pattern**: All errors are auth failures for expired tokens | Alex |
| 03:18 | 19:18 | Alex checks `kubectl rollout history`, sees v1.5.2 deployed 6 min ago | Alex |
| 03:19 | 19:19 | Alex makes decision: Rollback to v1.5.1 | Alex |
| 03:20 | 19:20 | **Rollback initiated**: `kubectl rollout undo` | Alex |
| 03:20 | 19:20 | Status page updated: "Investigating authentication errors" | Alex |
| 03:22 | 19:22 | First rollback pod becomes Ready (2/10 on v1.5.1) | Kubernetes |
| 03:23 | 19:23 | Error rate decreasing (45% → 30%) | - |
| 03:25 | 19:25 | Rollback 70% complete (7/10 on v1.5.1) | Kubernetes |
| 03:26 | 19:26 | Error rate now 10% | - |
| 03:27 | 19:27 | **Rollback complete**: All pods on v1.5.1 | Kubernetes |
| 03:28 | 19:28 | Error rate decreasing rapidly (10% → 2%) | - |
| 03:30 | 19:30 | **Error rate returns to normal** (<0.1%) | - |
| 03:30 | 19:30 | Alex updates #incidents: "Rollback complete, monitoring" | Alex |
| 03:35 | 19:35 | No new errors. Service stable. | Alex |
| 03:40 | 19:40 | Status page updated: "Issue resolved" | Alex |
| 03:45 | 19:45 | Final monitoring check. All metrics normal. | Alex |
| 03:49 | 19:49 | **Incident declared resolved** | Alex |
| 03:50 | 19:50 | Deployment pipeline blocked for v1.5.2 pending investigation | Sam |
| 09:00 | 01:00 | Postmortem meeting scheduled for 10:00 PT | Sam |

## Root Cause

### What Happened

Deployment v1.5.2 introduced a bug in the authentication middleware that caused the service to crash when processing expired refresh tokens.

### Why It Happened

**Code Change**:
A refactoring of the JWT token validation logic removed a try/except block that was handling expired tokens gracefully.

**Before (v1.5.1 - working)**:
```python
def validate_token(token: str) -> Optional[dict]:
    """Validate JWT token."""
    try:
        decoded = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"],
            verify=True
        )
        return decoded
    except jwt.ExpiredSignatureError:
        logger.warning("expired_token_rejected")
        return None  # Graceful handling - user needs to re-auth
    except jwt.InvalidTokenError as e:
        logger.error("invalid_token", error=str(e))
        return None
```

**After (v1.5.2 - broken)**:
```python
def validate_token(token: str) -> dict:
    """Validate JWT token."""
    # BUG: Removed try/except - now crashes on expired tokens
    decoded = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=["HS256"],
        verify=True
    )
    return decoded
```

**Why the Bug Was Introduced**:
1. Developer refactored authentication code for clarity
2. Accidentally removed error handling during refactoring
3. Type hint changed from `Optional[dict]` to `dict`, hiding the removed None return

**Why Tests Didn't Catch It**:
1. Integration tests only used fresh, valid tokens
2. No test cases for expired tokens
3. Token expiration not considered in test data generation

**Why Canary Didn't Catch It**:
1. Canary duration was only 5 minutes
2. Most users have valid tokens (tokens expire after 1 hour)
3. Only ~2% of requests during canary had expired tokens
4. 2% of 5% (canary traffic) = 0.1% overall → below alert threshold
5. Alert threshold is >5% error rate

### Contributing Factors

1. **Insufficient test coverage**: No edge case testing for expired tokens
2. **Short canary period**: 5 minutes not enough to detect low-frequency issues
3. **No canary-specific alerts**: Would have caught 2% error rate in canary
4. **Auto-deploy on green tests**: No manual approval gate before production
5. **Code review missed it**: Reviewers didn't notice removed error handling

## What Went Well ✅

1. **Fast detection**: Alert fired 2 minutes after errors started
2. **Quick response**: On-call acknowledged within 2 minutes of alert
3. **Clear diagnosis**: Error logs made it obvious (auth failures)
4. **Decisive action**: Rollback decision made in 6 minutes
5. **Fast rollback**: Rollback executed in 7 minutes (well-practiced)
6. **Clear communication**: Status updates every 5-10 minutes
7. **Monitoring worked**: Metrics clearly showed the problem and recovery
8. **Runbook helped**: "High Error Rate" runbook guided investigation
9. **No data loss**: All failed requests logged, users could retry

## What Went Wrong ❌

1. **Bug in production**: Code with missing error handling deployed
2. **Tests didn't catch it**: Integration tests had gap (expired tokens)
3. **Canary too short**: 5 min not enough for low-frequency edge cases
4. **No canary alerts**: Error rate during canary went unnoticed
5. **Auto-deploy too aggressive**: No manual review before prod rollout
6. **Code review gap**: Reviewers missed the removed try/except
7. **Type hint misleading**: Changing `Optional[dict]` to `dict` hid the issue
8. **User impact significant**: 4,500 failed requests, 3,000 users affected

## Action Items

### P0 - Critical (Complete within 48 hours)

| Action | Owner | Status | Completed |
|--------|-------|--------|-----------|
| Add integration test for expired tokens | Jordan | ✅ Done | 2024-01-16 |
| Add integration test for invalid tokens | Jordan | ✅ Done | 2024-01-16 |
| Add integration test for malformed tokens | Jordan | ✅ Done | 2024-01-16 |
| Extend canary period from 5 min to 30 min | Sam | ✅ Done | 2024-01-16 |
| Deploy fixed v1.5.3 with proper error handling | Alex | ✅ Done | 2024-01-17 |

### P1 - High (Complete within 1 week)

| Action | Owner | Status | Due Date |
|--------|-------|--------|----------|
| Add canary-specific alerts (>1% error rate in canary = stop rollout) | Alex | ✅ Done | 2024-01-18 |
| Review all auth edge cases and add tests | Team | ✅ Done | 2024-01-19 |
| Update "High Error Rate" runbook with auth debugging steps | Alex | ✅ Done | 2024-01-19 |
| Add pre-commit hook to check for missing try/except in auth code | Jordan | ✅ Done | 2024-01-20 |
| Enable manual approval for prod deployments | Sam | ✅ Done | 2024-01-21 |

### P2 - Medium (Complete within 1 month)

| Action | Owner | Status | Due Date |
|--------|-------|--------|----------|
| Implement automated edge case generation for testing | Jordan | 🏗️ In Progress | 2024-02-15 |
| Add linting rule to detect Optional→non-Optional type changes | Jordan | ✅ Done | 2024-02-01 |
| Chaos engineering: Inject expired tokens in staging | Alex | 📋 Planned | 2024-02-20 |
| Training session: "Common auth vulnerabilities" | Sam | 📋 Planned | 2024-02-28 |

### P3 - Low (Complete within 3 months)

| Action | Owner | Status | Due Date |
|--------|-------|--------|----------|
| Investigate automated rollback on high canary error rate | Sam | 📋 Planned | 2024-04-15 |
| Review all other middleware for missing error handling | Team | 📋 Planned | 2024-04-30 |

## Lessons Learned

### 1. Edge Cases Matter
**Lesson**: Integration tests must cover edge cases, not just happy paths.

**Action**: Implement edge case test generation for all critical paths.

**Impact**: Prevents similar bugs from reaching production.

### 2. Canary Duration Matters
**Lesson**: 5 minutes is too short to catch low-frequency issues (e.g., expired tokens).

**Action**: Extended to 30 minutes, added canary-specific alerts.

**Impact**: Will catch issues affecting <5% of requests.

### 3. Type Hints Can Be Misleading
**Lesson**: Changing `Optional[T]` to `T` hides intentional None returns.

**Action**: Linting rule to flag such changes + code review checklist.

**Impact**: Prevents accidental removal of null handling.

### 4. Auto-Deploy Needs Guardrails
**Lesson**: Auto-deploying to production after tests pass is risky without manual review.

**Action**: Manual approval required for prod (canary remains auto).

**Impact**: Adds human review before production rollout.

### 5. Error Handling Is Not Optional
**Lesson**: Authentication code is critical and must handle all edge cases gracefully.

**Action**: Pre-commit hook + team training on auth security.

**Impact**: Raises awareness and adds automated checks.

## Prevention

### Immediate (Already implemented)
- ✅ Tests for expired/invalid/malformed tokens
- ✅ Extended canary period (30 min)
- ✅ Canary-specific alerts
- ✅ Manual approval for prod deploys

### Medium-term (In progress)
- 🏗️ Automated edge case generation
- 🏗️ Chaos engineering in staging
- 📋 Team training on auth security

### Long-term (Planned)
- 📋 Automated rollback on canary failures
- 📋 Comprehensive middleware review

## Appendix

### Related Incidents
- 2023-11-20: Similar auth issue (different cause)
- 2023-09-15: Canary caught Redis connection issue

### References
- [High Error Rate Runbook](../runbooks/high-error-rate.md)
- [JWT Best Practices](https://wiki.company.com/auth/jwt-best-practices)
- [Canary Deployment Guide](https://wiki.company.com/deployment/canary)

### Code Changes
- **Broken commit**: `a1b2c3d` (v1.5.2)
- **Fix commit**: `e4f5g6h` (v1.5.3)
- **Test additions**: `i7j8k9l` (integration tests)
- **Pull Request**: #1234 (postmortem action items)

### Metrics

**Error Rate During Incident**:
```
03:12: 0.1% (normal)
03:13: 5.0% (↑ 50x)
03:14: 15.0% (↑ 150x)
03:15: 45.0% (↑ 450x) ← Peak
03:23: 30.0% (↓ rollback in progress)
03:26: 10.0%
03:30: 0.1% (← resolved)
```

**Affected Requests**:
```
Total requests during incident: 10,000
Failed requests: 4,500 (45%)
Successful requests: 5,500 (55%)
```

### Customer Impact Analysis

**User complaints by channel**:
- Email support: 28 tickets
- Live chat: 12 tickets
- Twitter: 15 mentions
- In-app feedback: 7 reports

**Most common complaint**: "Can't log in" or "Session expired"

**Resolution**: Users successfully retried after incident resolved

---

## Sign-Off

**Postmortem prepared by**: Alex Chen (Incident Commander)

**Reviewed by**:
- ✅ Jordan Kim (Engineering)
- ✅ Sam Rodriguez (Engineering Lead)
- ✅ Morgan Lee (Engineering Manager)
- ✅ Taylor Swift (Product Manager)

**Approved by**: Morgan Lee (Engineering Manager)

**Date**: January 16, 2024

**Next Review**: March 15, 2024 (verify all action items completed)

---

**Classification**: Internal
**Retention**: 7 years (compliance requirement)
**Location**: https://docs.company.com/postmortems/2024-01-15-auth-failure

---

*This postmortem follows our blameless postmortem culture. The goal is to learn and improve, not to assign blame.*
