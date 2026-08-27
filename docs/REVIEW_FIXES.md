# Review Fixes

This document records the medium- and low-severity review fixes implemented after the runtime review.

## Configuration and validation

- The CLI loads the repository `.env` file at startup. Existing process environment variables retain precedence.
- Org validation accepts an optional root directory and checks that referenced SOP files exist beneath it. The CLI passes the org root for `validate`, `run`, and `ambition`.
- Boolean YAML values for tool approvals must be actual booleans. Text such as `"false"` is rejected instead of being silently converted to `True`.

## Runtime robustness

- Malformed tool-input payloads are converted into a recoverable invalid-tool action instead of raising during parsing.
- Non-numeric ambition proposal priorities use the default priority rather than terminating the ambition loop.
- Queue claims use a conditional `UPDATE ... RETURNING` statement so the exact oldest queued job is claimed atomically by SQLite.
- Runtime approval is derived from the org and role policies as well as each grant, so hand-authored YAML cannot disable required approval gates.
- Provider failures and agent step-limit failures mark their durable jobs as `error` before the exception is re-raised.

## Packaging and documentation

- Added the `agent_factory` console-script entry point.
- Updated provider documentation to describe modern OpenAI SDK support only.
- Updated documented test counts to the current 87-test suite.

Filesystem confinement and SSRF protection are documented and implemented separately in `FILESYSTEM_CONFINEMENT.md` and `SSRF_PROTECTION.md`. Other high-severity findings remain outside the scope of these changes.
