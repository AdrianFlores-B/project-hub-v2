import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "size_calculator_handler",
    Path(__file__).parent.parent / "lambdas" / "size_calculator" / "handler.py",
)
handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler)


def test_project_id_from_key():
    assert handler.project_id_from_key("projects/42/7/report.pdf") == 42
    assert handler.project_id_from_key("projects/42/7/name with spaces.pdf") == 42


def test_project_id_from_key_ignores_foreign_keys():
    assert handler.project_id_from_key("other/42/file.pdf") is None
    assert handler.project_id_from_key("projects/not-a-number/file.pdf") is None
    assert handler.project_id_from_key("stray-file.pdf") is None
