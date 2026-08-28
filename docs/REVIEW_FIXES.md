# Review Fixes Summary

This document captures the fixes implemented after the code review, including the M4 insights review and the broader runtime hardening work.

## M4 review fixes

- Guarded observer/brief prompt injection by sanitizing context before it is embedded in LLM prompts.
- Fixed deduplication for insights so similar findings with different details are not incorrectly collapsed into one record.
- Added validation for insight status, level, and kind values so invalid data is rejected instead of silently persisted.
- Strengthened the SQLite schema with CHECK constraints for insight status and enum fields.
- Improved mission-control output to show empty job and approval lists clearly instead of implying a broken state.
- Added regression tests covering invalid insight status updates and multi-item observation deduplication.

## Additional runtime and validation fixes

- The CLI loads the repository `.env` file at startup while preserving environment precedence.
- Org validation accepts an optional root directory and ensures referenced SOP files exist under the org tree.
- Boolean YAML values for tool approvals must be actual booleans; string values like `"false"` are rejected.
- Malformed tool-input payloads are converted into a recoverable invalid-tool action instead of crashing.
- Non-numeric ambition proposal priorities fall back to the default priority instead of aborting the loop.
- Queue claims use an atomic SQLite `UPDATE ... RETURNING` pattern so the oldest queued job is claimed reliably.
- Runtime approval decisions derive from org/role policy plus role grants so hand-edited YAML cannot bypass required gates.
- Provider and step-limit failures mark durable jobs as `error` before re-raising the exception.

## Packaging and documentation

- Added the `agent_factory` console-script entry point.
- Updated provider documentation for the current OpenAI SDK pattern.
- Updated the recorded suite size to the currently verified 97-test suite.

## Verification

The fixes were validated with the project’s standard unittest discovery command:

```bash
python -m unittest discover -s tests
```

Result: 97 tests ran and all passed (`OK`).

Filesystem confinement and SSRF protection are covered separately in the project documentation if needed. Other high-severity findings remain outside this review-fix scope.
