"""Tests for scripts/ensure-propose-result."""

from __future__ import annotations

import json
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().parent / "ensure-propose-result"


def _load():
    loader = SourceFileLoader("ensure_propose_result", str(SCRIPT))
    spec = spec_from_loader("ensure_propose_result", loader)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ep = _load()


class TestEnsureProposeResult(unittest.TestCase):
    def test_leaves_valid_file_alone(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "result-php.json"
            path.write_text('{"language":"php","status":"updated"}\n')
            self.assertFalse(ep.ensure(path))
            self.assertEqual(json.loads(path.read_text())["status"], "updated")

    def test_rewrites_empty_file(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "result-apex.json"
            path.write_text("")
            self.assertTrue(ep.ensure(path))
            data = json.loads(path.read_text())
            self.assertEqual(data["language"], "apex")
            self.assertEqual(data["status"], "failed")
            self.assertIn("no result JSON", data["detail"])

    def test_rewrites_invalid_json(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "result-ruby.json"
            path.write_text("{nope")
            self.assertTrue(ep.ensure(path))
            self.assertEqual(json.loads(path.read_text())["language"], "ruby")

    def test_language_override(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "odd-name.json"
            path.write_text("")
            ep.ensure(path, language="go")
            self.assertEqual(json.loads(path.read_text())["language"], "go")


if __name__ == "__main__":
    unittest.main()
