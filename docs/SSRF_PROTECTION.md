# SSRF Protection

## Problem

The `web_fetch` tool accepts a URL supplied by the model and previously passed it directly to `requests.get`. A prompt-injected or compromised model could use that capability to access destinations that are not part of the intended public web workflow.

Examples include:

```text
http://127.0.0.1:5000/admin
http://[::1]/
http://10.0.0.5/internal-api
http://169.254.169.254/metadata/identity
file:///etc/passwd
```

This can expose cloud metadata, managed-identity tokens, internal admin services, databases, local APIs, and network topology. It can also cause resource exhaustion because the old implementation buffered the entire response before truncating the returned text.

Automatic redirects create another bypass. A public URL can redirect to a private address, so validating only the original URL is insufficient.

## Solution Implemented: Option A + host allowlist

The `web_fetch` tool now uses a validated outbound HTTP flow:

1. Parse the URL with `urllib.parse`.
2. Permit only `http` and `https` schemes.
3. Require a hostname and reject embedded username/password credentials.
4. Permit only ports 80 and 443.
5. Resolve hostnames with `socket.getaddrinfo`.
6. Reject loopback, private, link-local, multicast, reserved, unspecified, and other non-global addresses.
7. Explicitly block common cloud metadata addresses.
8. Enforce a configured host allowlist before the request is sent.
9. Disable inherited proxy settings with `Session.trust_env = False`.
10. Disable automatic redirects and validate each redirect destination.
11. Limit redirects to five hops.
12. Stream the response and cap collected content at 1 MiB.
13. Use separate connection and read timeouts of 10 and 30 seconds.
14. Return a stable error containing only the exception type, avoiding raw network details in model-visible output.

The response still returns at most 8,000 characters to the agent, but the 1 MiB transport limit is enforced before decoding and truncation.

For deployments with a narrow research surface, configure one of the following environment variables before enabling outbound fetches:

```powershell
$env:AGENT_FACTORY_WEB_ALLOWED_HOSTS = "example.com,docs.example.com"
# or
$env:WEB_FETCH_ALLOWED_HOSTS = "example.com,docs.example.com"
```

When the allowlist is configured, hosts not on the list are rejected regardless of whether they are public and reachable.

## URL Policy

The following are rejected:

| Category | Example | Reason |
|---|---|---|
| Unsupported scheme | `file:///etc/passwd` | Avoid local-file and non-HTTP handlers |
| Loopback | `127.0.0.1`, `[::1]` | Avoid local services |
| Private address | `10.0.0.5`, `192.168.1.5`, `[fc00::1]` | Avoid internal networks |
| Link-local/metadata | `169.254.169.254` | Avoid cloud metadata services |
| Multicast/reserved | `224.0.0.1` | Not a public web destination |
| Embedded credentials | `https://user:pass@example.com` | Avoid ambiguous or unsafe authorities |
| Non-web port | `example.com:22` | Reduce access to unrelated services |
| Private redirect | Public URL -> `http://127.0.0.1` | Every redirect must pass the same policy |
| Unlisted host | `https://example.net` | Not in the configured allowlist; deny by policy |

IP-aware parsing is used instead of string-prefix checks, covering IPv4, IPv6, and numeric or unusual literal representations handled by Python's address parser.

## Options Considered

| Option | Description | Security | Complexity | Assessment |
|---|---|---:|---:|---|
| **A. Validated outbound HTTP client** | Validate schemes, DNS/IP destinations, redirects, ports, timeouts, proxy behavior, and response size inside `web_fetch`. | Good | Medium | **Implemented and recommended now.** Fits the current synchronous `requests` adapter without requiring another service. |
| **B. Host allowlist** | Permit requests only to explicitly configured domains. | Very good | Low to medium | **Implemented as an enforced policy layer.** This is the strongest app-level control when research sources are known. |
| **C. External fetch proxy** | Route requests through a dedicated service that enforces network and content policy. | Very good | Medium to high | Good for centralized controls, logging, rate limits, and production operations. |
| **D. Network egress isolation** | Run agents in a container, sandbox, or subnet that cannot reach private networks or metadata endpoints. | Excellent | High | Strong infrastructure defense and appropriate for production or multi-tenant workloads. |
| **E. Human approval for every URL** | Ask for approval before each request. | Limited | Low | Useful as a secondary control, but does not reliably prevent SSRF or oversized responses. |

## Design Reasoning

Option A places controls directly next to the dangerous network operation. The agent loop and provider adapters do not need to understand network policy, and all callers of `web_fetch` receive the same behavior.

Redirects are handled manually because `requests` follows them by default. Each `Location` value is resolved against the current URL and passed through the complete validation process before another request is made.

Proxy inheritance is disabled because environment-configured proxies can change the actual network destination and undermine assumptions made by application-level validation.

The response is streamed because truncating `response.text` after `requests` has already downloaded and decoded the complete body does not protect memory usage. The byte cap is applied while reading chunks.

## Remaining Limitations

This is an application-level SSRF defense, not a complete network sandbox. DNS validation and the subsequent HTTP connection are separate operations, so a hostile DNS rebinding race is not fully eliminated. A stronger design would resolve and pin the approved address for the connection and verify the connected peer address.

The host allowlist must be configured for the environment; without it, outbound fetches are denied by policy for safety. Network-level egress restrictions should still be added for production environments, especially where the process has access to cloud identities or private network resources.

## Tests

The runtime tests cover:

- Public URL fetches with bounded request settings
- Rejection of `file://` URLs
- Rejection of loopback and metadata addresses
- Rejection of embedded URL credentials
- Rejection of unlisted hosts via the configured allowlist
- Rejection of redirects to private addresses
- Response-size bounding

Run the suite with:

```powershell
$env:PYTHONPATH = "src"
py -m unittest discover -s tests -v
```
