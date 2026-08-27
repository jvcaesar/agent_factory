# Filesystem Confinement

## Problem

The `files_read` and `files_write` tools accept a path supplied by the model. Without a boundary, an agent can read or modify any file accessible to the Python process, including credentials, source code, SSH keys, `.env` files, and operating-system configuration.

Examples of unsafe requests include:

```text
C:\Users\user\.env
C:\Users\user\.ssh\id_rsa
..\..\secrets.txt
```

Write approval does not solve this problem by itself. Approval controls whether a write is allowed, but not where the write happens. Reads are not approval-gated. A symlink, junction, or other reparse point can also make a path appear to be inside a workspace while redirecting access outside it.

## Solution Implemented: Option A

The runtime now uses an approved execution root for file tools. The root is passed from `run_agent` into `tools_for_role`, and file tools validate every requested path before accessing it.

The validation rules are:

1. A workspace root is required. File operations without one return an error.
2. The requested path must be a non-empty string.
3. Absolute paths, including Windows drive paths and UNC paths, are rejected.
4. The path is resolved relative to the approved workspace root.
5. The resolved path must remain beneath the resolved workspace root.
6. Symlinks and similar path redirections are evaluated during resolution, so an escape outside the root is rejected.
7. New write targets are allowed only when their resolved parent remains inside the workspace.
8. File writes still retain the existing approval gate.

A valid layout looks like this:

```text
approved root: orgs/Acme

allowed:
  goals/current.md
  outputs/research.txt

rejected:
  C:\Users\user\secret.txt
  ..\..\secret.txt
  link-to-outside\secret.txt
```

The file tools return stable, non-sensitive error messages for rejected paths. Successful writes report the path relative to the workspace rather than exposing an arbitrary absolute path.

## Options Considered

| Option | Description | Security | Complexity | Assessment |
|---|---|---:|---:|---|
| **A. Approved-root validation** | Resolve every file path against an execution root and reject escapes. | Good | Low | **Implemented and recommended now.** Fits the existing `run_agent(root=...)` design and keeps the agent loop provider-independent. |
| **B. Capability-based access** | Give each role an explicit list of readable and writable directories or files. | Very good | Medium | Stronger least privilege, but requires schema, configuration, and role-management changes. |
| **C. Separate read/write roots** | Permit reads from one controlled root and writes only to a separate output root. | Very good | Medium | Useful for artifact-producing agents; can be layered on top of Option A later. |
| **D. OS sandbox or isolated worker** | Execute file operations in a restricted process, container, or operating-system sandbox. | Excellent | High | Best for untrusted models, multi-tenant deployments, or agents with broader capabilities. Requires operational infrastructure. |
| **E. Approval for every filesystem action** | Ask a human before each read and write. | Limited | Low | Not sufficient alone: users can approve an unsafe path, and approval does not provide a filesystem boundary. |

## Design Reasoning

Option A was chosen because the runtime already has an optional `root` used for organization files and SOPs. Passing the same root into file-tool construction keeps the boundary close to the actual filesystem operation and avoids relying on model instructions or CLI behavior.

The path check is centralized so reads and writes cannot drift into different security rules. Resolving the root and candidate path before comparison handles normal traversal and existing symlink escapes more reliably than checking for the literal `..` segment alone.

The root is intentionally not inferred from the current working directory. The working directory can change depending on how the application is launched, so silently using it could grant access to an unintended location. A missing root fails closed for file operations.

Approval remains a second control for writes. Confinement answers "where may the agent operate?" while approval answers "may this write happen?" Both controls are needed.

## Remaining Limitations

This is a path-validation boundary, not a complete operating-system sandbox. A time-of-check/time-of-use race could occur if a directory or link is changed between validation and the filesystem operation. Stronger protection for hostile multi-user environments would require OS-level safe-open primitives, a dedicated restricted worker process, or a container/sandbox.

The current option also grants the whole approved root to a role. More restrictive per-role directories should use Option B or C when the configuration model needs least-privilege access within an organization.

## Tests

The runtime tests cover:

- Normal relative reads and writes inside a temporary workspace
- Missing workspace roots
- Absolute-path rejection
- Parent traversal rejection
- In-workspace writes
- Existing write approval behavior

Run the suite with:

```powershell
$env:PYTHONPATH = "src"
py -m unittest discover -s tests -v
```
