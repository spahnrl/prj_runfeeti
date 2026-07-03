from __future__ import annotations

import pathlib
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TextHygieneTest(unittest.TestCase):
    def test_user_facing_files_do_not_contain_common_mojibake_markers(self) -> None:
        checked = [
            ROOT / "README.md",
            ROOT / "CHANGELOG.md",
            ROOT / "streamlit_app.py",
            *sorted((ROOT / "runfeeti").glob("*.py")),
        ]
        markers = tuple(chr(codepoint) for codepoint in (0x00E2, 0x00C2, 0x00C3))
        offenders: list[str] = []
        for path in checked:
            text = path.read_text(encoding="utf-8")
            for marker in markers:
                if marker in text:
                    offenders.append(f"{path.relative_to(ROOT)} contains {marker!r}")
        self.assertEqual(offenders, [])


class DependencyMetadataTest(unittest.TestCase):
    def test_requirements_and_pyproject_runtime_dependencies_stay_in_sync(self) -> None:
        requirements = {
            line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        with (ROOT / "pyproject.toml").open("rb") as f:
            pyproject = tomllib.load(f)
        project_deps = set(pyproject["project"]["dependencies"])
        self.assertEqual(requirements, project_deps)


if __name__ == "__main__":
    unittest.main()
