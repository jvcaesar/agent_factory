"""Tests for generic MODEL_* env resolution in llm.models."""

import os
import unittest

from agent_factory.llm.models import model_for_tier, resolve_role


class _Env:
    """Context manager that sets/clears env vars and restores them after."""

    def __init__(self, **values):
        self._values = values
        self._saved = {}

    def __enter__(self):
        keys = set(self._values) | {
            "MODEL_default", "MODEL_DEFAULT", "MODEL_fast", "MODEL_FAST",
            "MODEL_smart", "MODEL_SMART", "MODEL_big", "MODEL_BIG",
            "OPENAI_MODEL", "OLLAMA_MODEL", "AGENT_FACTORY_PROVIDER",
        }
        for key in keys:
            self._saved[key] = os.environ.get(key)
            os.environ.pop(key, None)
        for key, value in self._values.items():
            if value is not None:
                os.environ[key] = value
        return self

    def __exit__(self, *exc):
        for key, old in self._saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        return False


class TestGenericModelResolution(unittest.TestCase):
    def test_model_default_used_when_nothing_else_set(self):
        with _Env(**{"MODEL_default": "gemma4:12b"}):
            self.assertEqual(model_for_tier("ollama", "fast"), "gemma4:12b")
            self.assertEqual(model_for_tier("openai", "big"), "gemma4:12b")

    def test_tier_var_beats_model_default(self):
        with _Env(**{"MODEL_default": "gemma4:12b", "MODEL_fast": "qwen2.5:0.5b"}):
            self.assertEqual(model_for_tier("ollama", "fast"), "qwen2.5:0.5b")
            # other tiers still fall back to MODEL_default
            self.assertEqual(model_for_tier("ollama", "big"), "gemma4:12b")

    def test_provider_specific_beats_generic(self):
        with _Env(**{"MODEL_default": "gemma4:12b", "OLLAMA_MODEL_SMART": "qwen3:8b"}):
            self.assertEqual(model_for_tier("ollama", "smart"), "qwen3:8b")
            self.assertEqual(model_for_tier("openai", "smart"), "gemma4:12b")

    def test_uppercase_env_name_also_works(self):
        # Windows normalizes env var names to uppercase inside os.environ.
        with _Env(**{"MODEL_DEFAULT": "llava:13b"}):
            self.assertEqual(model_for_tier("ollama", "smart"), "llava:13b")

    def test_built_in_default_when_env_empty(self):
        with _Env():  # everything cleared
            self.assertEqual(model_for_tier("openai", "fast"), "gpt-4o-mini")

    def test_resolve_role_uses_provider_env_and_model_default(self):
        from agent_factory.config import Role

        role = Role(id="worker_x", title="Worker X", display_name="Worker X",
                    charter="Executes research and writing tasks for the org.",
                    sop="sops/worker_x.md",
                    proactivity_level=2, model_tier="fast")
        with _Env(**{"AGENT_FACTORY_PROVIDER": "ollama", "MODEL_default": "gemma4:12b"}):
            provider, model = resolve_role(role)
        self.assertEqual(provider, "ollama")
        self.assertEqual(model, "gemma4:12b")

    def test_per_role_env_override_sets_model(self):
        from agent_factory.config import Role

        role = Role(id="lead_exec", title="Lead", display_name="Lead",
                    charter="Runs the org and routes work.",
                    sop="sops/lead_exec.md",
                    proactivity_level=5, model_tier="big")
        with _Env(**{"AGENT_FACTORY_PROVIDER": "ollama",
                     "MODEL_default": "gemma4:12b",
                     "MODEL_lead_exec": "gpt-4o"}):
            provider, model = resolve_role(role)
        # bare name -> global provider still applies
        self.assertEqual(provider, "ollama")
        self.assertEqual(model, "gpt-4o")

    def test_per_role_env_prefix_forces_provider(self):
        from agent_factory.config import Role

        role = Role(id="lead_exec", title="Lead", display_name="Lead",
                    charter="Runs the org and routes work.",
                    sop="sops/lead_exec.md",
                    proactivity_level=5, model_tier="big")
        with _Env(**{"AGENT_FACTORY_PROVIDER": "ollama",
                     "MODEL_default": "gemma4:12b",
                     "MODEL_lead_exec": "openai/gpt-4o"}):
            provider, model = resolve_role(role)
        self.assertEqual(provider, "openai")
        self.assertEqual(model, "gpt-4o")

    def test_cli_provider_override_beats_env_prefix(self):
        from agent_factory.config import Role

        role = Role(id="lead_exec", title="Lead", display_name="Lead",
                    charter="Runs the org and routes work.",
                    sop="sops/lead_exec.md",
                    proactivity_level=5, model_tier="big")
        with _Env(**{"AGENT_FACTORY_PROVIDER": "ollama",
                     "MODEL_lead_exec": "openai/gpt-4o"}):
            provider, model = resolve_role(role, provider_override="ollama")
        self.assertEqual(provider, "ollama")
        self.assertEqual(model, "gpt-4o")  # env model kept, provider overridden

    def test_role_yaml_model_prefix_works(self):
        from agent_factory.config import Role

        role = Role(id="worker_y", title="W", display_name="W",
                    charter="Handles curation of research sources.",
                    sop="sops/worker_y.md",
                    proactivity_level=1, model_tier="fast",
                    model="openai/gpt-4o-mini")
        with _Env(**{"AGENT_FACTORY_PROVIDER": "ollama"}):
            provider, model = resolve_role(role)
        self.assertEqual(provider, "openai")
        self.assertEqual(model, "gpt-4o-mini")

    def test_unknown_prefix_kept_as_model_name(self):
        from agent_factory.llm.models import split_provider_model
        provider, model = split_provider_model("hf/mistral-7b")
        self.assertIsNone(provider)          # 'hf' is not a known provider
        self.assertEqual(model, "hf/mistral-7b")

    def test_tier_value_prefix_overrides_provider(self):
        from agent_factory.config import Role

        role = Role(id="worker_z", title="W", display_name="W",
                    charter="Handles fast classification of research sources.",
                    sop="sops/worker_z.md",
                    proactivity_level=1, model_tier="fast")
        # MODEL_fast carries an explicit provider prefix even though the global
        # provider is ollama — the prefix must win for this role's tier.
        with _Env(**{"AGENT_FACTORY_PROVIDER": "ollama",
                     "MODEL_default": "gemma4:12b",
                     "MODEL_fast": "openai/gpt-4o-mini"}):
            provider, model = resolve_role(role)
        self.assertEqual(provider, "openai")
        self.assertEqual(model, "gpt-4o-mini")

    def test_cli_model_override_wins(self):
        from agent_factory.config import Role

        role = Role(id="worker_cli", title="Worker", display_name="Worker",
                    charter="Handles a task.", sop="", proactivity_level=1,
                    model="ollama/old-model")
        with _Env(**{"AGENT_FACTORY_PROVIDER": "ollama", "MODEL_worker_cli": "old-env"}):
            provider, model = resolve_role(role, model_override="qwen3:8b")
        self.assertEqual(provider, "ollama")
        self.assertEqual(model, "qwen3:8b")

    def test_cli_model_provider_prefix_is_used(self):
        from agent_factory.config import Role

        role = Role(id="worker_cli", title="Worker", display_name="Worker",
                    charter="Handles a task.", sop="", proactivity_level=1)
        with _Env():
            provider, model = resolve_role(role, model_override="ollama/qwen3:8b")
        self.assertEqual(provider, "ollama")
        self.assertEqual(model, "qwen3:8b")

    def test_conflicting_cli_model_prefix_is_rejected(self):
        from agent_factory.config import Role

        role = Role(id="worker_cli", title="Worker", display_name="Worker",
                    charter="Handles a task.", sop="", proactivity_level=1)
        with self.assertRaisesRegex(ValueError, "conflicts"):
            resolve_role(role, provider_override="ollama", model_override="openai/gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
