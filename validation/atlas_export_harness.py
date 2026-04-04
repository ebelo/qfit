from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS_ROOT = REPO_ROOT / "validation_artifacts" / "atlas-harness"


@dataclass(frozen=True)
class AtlasValidationScenario:
    """Supported atlas validation scenario.

    The harness is intentionally explicit: curated scenarios are supported and
    documented here, while older one-off scripts remain historical artifacts in
    ``validation_artifacts/``.
    """

    name: str
    description: str
    script_path: Path
    expected_artifacts: tuple[str, ...] = ()


SCENARIOS: dict[str, AtlasValidationScenario] = {
    "native-profile-final": AtlasValidationScenario(
        name="native-profile-final",
        description=(
            "Headless real-data validation comparing atlas-driven native profile "
            "rendering with the renderer-image workaround for activity 17248394490."
        ),
        script_path=REPO_ROOT / "validation_artifacts" / "validate_line_atlas_final.py",
        expected_artifacts=(
            "FINAL-A-layout-item-atlas-driven.png",
            "FINAL-B-renderer-profile-image.png",
            "FINAL-C-composite-renderer-profile.png",
            "FINAL-C-composite-renderer-profile.pdf",
        ),
    ),
    "native-profile-renderer": AtlasValidationScenario(
        name="native-profile-renderer",
        description=(
            "Headless real-data validation of the QgsProfilePlotRenderer image workaround."
        ),
        script_path=REPO_ROOT / "validation_artifacts" / "validate_line_atlas_native_profile_v8.py",
        expected_artifacts=(
            "native-renderer-profile-17248394490.png",
            "line-atlas-native-renderer-page-17248394490.png",
            "line-atlas-native-renderer-17248394490.pdf",
        ),
    ),
}


def build_run_directory(*, artifacts_root: Path, scenario_name: str, now: dt.datetime | None = None) -> Path:
    timestamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return artifacts_root / scenario_name / timestamp


def build_env(*, run_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["QFIT_VALIDATION_OUTPUT_DIR"] = str(run_dir)
    env["QFIT_VALIDATION_REPO_ROOT"] = str(REPO_ROOT)
    return env


def list_scenarios() -> str:
    lines = []
    for scenario in SCENARIOS.values():
        lines.append(f"- {scenario.name}: {scenario.description}")
    return "\n".join(lines)


def run_scenario(*, scenario: AtlasValidationScenario, artifacts_root: Path, python_executable: str) -> int:
    run_dir = build_run_directory(artifacts_root=artifacts_root, scenario_name=scenario.name)
    run_dir.mkdir(parents=True, exist_ok=True)
    env = build_env(run_dir=run_dir)

    print(f"Scenario: {scenario.name}")
    print(f"Description: {scenario.description}")
    print(f"Run directory: {run_dir}")
    print(f"Script: {scenario.script_path}")
    print("Expected artifacts:")
    for artifact in scenario.expected_artifacts:
        print(f"  - {artifact}")
    print()

    result = subprocess.run(
        [python_executable, str(scenario.script_path)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run curated atlas export validation scenarios.",
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        choices=sorted(SCENARIOS.keys()),
        help="Scenario name to run.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List supported scenarios and exit.",
    )
    parser.add_argument(
        "--artifacts-root",
        default=str(DEFAULT_ARTIFACTS_ROOT),
        help="Root directory for predictable harness run outputs.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for the QGIS/headless validation run.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print(list_scenarios())
        return 0

    if not args.scenario:
        parser.error("scenario is required unless --list is used")

    scenario = SCENARIOS[args.scenario]
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    return run_scenario(
        scenario=scenario,
        artifacts_root=artifacts_root,
        python_executable=args.python,
    )


if __name__ == "__main__":
    raise SystemExit(main())
