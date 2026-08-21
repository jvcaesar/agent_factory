"""Bootstrap: turn an interview (or a spec file) into a validated org chart.

This is the generic entry point for going from \"I want a workforce\" to role
files. It never hard-codes a specific person's org — it applies generic rules
(hierarchy, proactivity, approval, model tiering) to whatever domains, risk,
and budget the user selects.
"""

from __future__ import annotations
