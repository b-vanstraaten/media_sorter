import unittest

from marquee.ollama_client import OllamaUnavailableError, ensure_ready


class _FakeModel:
    def __init__(self, name):
        self.model = name


class _FakeListResponse:
    def __init__(self, names):
        self.models = [_FakeModel(n) for n in names]


class _FakeClient:
    def __init__(self, names=(), error=None):
        self._names = names
        self._error = error

    def list(self):
        if self._error:
            raise self._error
        return _FakeListResponse(self._names)


class TestEnsureReady(unittest.TestCase):
    def test_ready_when_model_installed_with_tag(self):
        client = _FakeClient(names=["llama3.2:latest"])
        ensure_ready(client, "llama3.2", "http://localhost:11434")  # no raise

    def test_ready_when_model_installed_exact(self):
        client = _FakeClient(names=["llama3.2"])
        ensure_ready(client, "llama3.2", "http://localhost:11434")  # no raise

    def test_raises_with_available_models_when_missing(self):
        client = _FakeClient(names=["mistral:latest"])
        with self.assertRaises(OllamaUnavailableError) as ctx:
            ensure_ready(client, "llama3.2", "http://localhost:11434")
        self.assertIn("llama3.2", str(ctx.exception))
        self.assertIn("mistral", str(ctx.exception))

    def test_raises_on_connection_error(self):
        client = _FakeClient(error=ConnectionError("refused"))
        with self.assertRaises(OllamaUnavailableError) as ctx:
            ensure_ready(client, "llama3.2", "http://localhost:11434")
        self.assertIn("Could not reach Ollama", str(ctx.exception))

    def test_raises_on_other_errors_too(self):
        client = _FakeClient(error=RuntimeError("boom"))
        with self.assertRaises(OllamaUnavailableError):
            ensure_ready(client, "llama3.2", "http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
