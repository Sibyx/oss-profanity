# Proposals

Welcome to the proposals archive. This is where all technical decisions, feature designs, and architectural
changes are documented before implementation.

## Proposals Index

**IMPORTANT**: When creating or updating a proposal's status, always update this table to reflect the current state.

| ID | Title | Status | Last Updated |
|----|-------|--------|--------------|
| [IP-001](posts/ip-001-foundations.md) | Foundations — config, MongoDB access, and document schema | ✅ Implemented | 2026-04-23 |
| [IP-002](posts/ip-002-profanity-detection.md) | Profanity detection — text-level profanity scoring | ✅ Implemented | 2026-04-23 |
| [IP-003](posts/ip-003-emoji-detection.md) | Emoji detection — text-level emoji extraction | ✅ Implemented | 2026-04-23 |
| [IP-004](posts/ip-004-static-analyzers.md) | Static analyzers — single-walk source scanning + language-dispatched linters | ✅ Implemented | 2026-04-24 |
| [IP-005](posts/ip-005-gh-archive-ingest.md) | GH Archive ingest — Stage 1+2 streaming + scoring pipeline | ✅ Implemented | 2026-04-24 |
| [IP-006](posts/ip-006-cohort-sampling.md) | Cohort sampling — Stage 3 stratified cohort promotion | ✅ Implemented | 2026-04-24 |
| [IP-007](posts/ip-007-repo-worker.md) | Repo worker — Stage 4 claim-clone-analyze loop + GitHub metadata enrichment | ✅ Implemented | 2026-04-24 |
| [IP-008](posts/ip-008-aggregation-and-plots.md) | Aggregation, statistics, and plots — Jupyter notebook for the OpenCamp deck | ✅ Implemented | 2026-04-25 |
| [IP-009](posts/ip-009-docker-test-harness.md) | Docker test harness — green-gate before OpenStack deployment | ✅ Implemented | 2026-04-24 |
| [IP-010](posts/ip-010-deployment.md) | Faculty deployment — GHCR image + per-host compose | ✅ Implemented | 2026-04-25 |
| [IP-011](posts/ip-011-initial-presentation.md) | Initial OpenCamp presentation — "Vulgarizmy, otvorený kód a jeho kvalita" | ✅ Implemented | 2026-04-25 |



**Status Key**:
- 📝 **Draft**: Initial proposal, work in progress
- 🔍 **Under Review**: Proposal complete, awaiting feedback/approval
- ✅ **Accepted**: Approved for implementation
- ✅ **Implemented**: Implementation complete
- ❌ **Rejected**: Proposal declined
- ⏭️ **Superseded**: Replaced by another proposal

## What are Proposals?

Proposals are detailed documents that outline:

- **Problem**: What challenge or need are we addressing?
- **Solution**: Proposed approach to solve the problem
- **Implementation**: Technical details and plan
- **Alternatives**: Other approaches considered
- **Open Questions**: Unresolved issues or decisions needed

## Proposal Lifecycle

1. **Draft**: Initial proposal is written
2. **Under Review**: Team reviews and provides feedback
3. **Accepted**: Proposal is approved for implementation
4. **Implemented**: Solution is built according to proposal

## Writing a Proposal

To write a new proposal:

1. Copy `proposals/.template.md` to `proposals/posts/ip-XXX-title.md`
2. Fill in all sections of the template
3. Add relevant tags and categories
4. **Update this index** with the new proposal entry
5. Submit for review

**Important**: See `CLAUDE.md` for detailed proposal writing guidelines including:
- No time estimates required
- Always update proposal changelog
- Update this index when changing proposal status
