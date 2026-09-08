# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

Only the latest release line receives security patches. The `main` branch is under active development and may be unstable — pin to a released tag for production use.

## Reporting a Vulnerability

To report a security vulnerability in `agent_factory`:

1. **Do not** open a public GitHub issue for the vulnerability itself.
2. Email the maintainers directly with:
   - A description of the vulnerability
   - Steps to reproduce (or a proof-of-concept)
   - The affected version/commit
   - Any suggested fix (optional)
3. You should receive an acknowledgment within 48 hours. If you do not, please follow up once.

The maintainers will:
- Confirm receipt and assess severity
- Work on a fix and coordinate a release
- Credit you in the advisory (unless you prefer anonymity)

## Security Considerations

### Provider API Keys

`agent_factory` reads API keys from environment variables (`OPENAI_API_KEY`, `OLLAMA_BASE_URL`, etc.) or a `.env` file. **Never commit `.env` files** — they are gitignored by default. Rotate any key that is accidentally exposed.

### Tool Surface

The runtime includes a tool system (`src/agent_factory/runtime/tools.py`) with:

- **Filesystem confinement**: tools operate within the working directory and cannot escape it
- **SSRF protection**: `web_fetch` uses an allowlist/blocklist for outbound requests
- **Risk-aware gating**: tools marked `risk="medium"` or higher require approval before execution
- **Prompt injection sanitization**: insights are sanitized before being injected into prompts

When adding new tool adapters (e.g., for third-party services), ensure they:
- Validate and sanitize all inputs
- Do not log or expose credentials
- Respect the `risk` and `requires_approval` flags

### Local Models (Ollama)

When using the Ollama provider with local models, be aware that:
- Model outputs are not filtered — treat them as untrusted content
- The Ollama server should not be exposed to untrusted networks without authentication

## Dependencies

Runtime dependencies are kept minimal (`pydantic`, `pyyaml`, `requests`). Known vulnerabilities in dependencies should be reported through the same process above.
