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
    required_reference_artifacts: tuple[str, ...] = ()
    requires_source_gpkg: bool = False


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
        required_reference_artifacts=("line-atlas-coverage-17248394490.gpkg",),
        requires_source_gpkg=True,
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
        required_reference_artifacts=("line-atlas-coverage-17248394490.gpkg",),
        requires_source_gpkg=True,
    ),
}


def build_run_directory(*, artifacts_root: Path, scenario_name: str, now: dt.datetime | None = None) -> Path:
    timestamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return artifacts_root / scenario_name / timestamp


def build_env(
    *,
    run_dir: Path,
    source_gpkg: Path | None = None,
    reference_artifacts_dir: Path | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["QFIT_VALIDATION_OUTPUT_DIR"] = str(run_dir)
    env["QFIT_VALIDATION_REPO_ROOT"] = str(REPO_ROOT)

    if source_gpkg is not None:
        env["QFIT_VALIDATION_SOURCE_GPKG"] = str(source_gpkg)
    if reference_artifacts_dir is not None:
        env["QFIT_VALIDATION_REFERENCE_ARTIFACTS_DIR"] = str(reference_artifacts_dir)

    pythonpath_entries = [str(REPO_ROOT), str(REPO_ROOT.parent)]
    current_pythonpath = env.get("PYTHONPATH")
    if current_pythonpath:
        pythonpath_entries.append(current_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return env


def describe_scenario_inputs(scenario: AtlasValidationScenario) -> list[str]:
    requirements: list[str] = []
    if scenario.requires_source_gpkg:
        requirements.append("source GeoPackage via --source-gpkg (or QFIT_VALIDATION_SOURCE_GPKG)")
    if scenario.required_reference_artifacts:
        joined = ", ".join(scenario.required_reference_artifacts)
        requirements.append(
            "reference artifacts via --reference-artifacts-dir (or QFIT_VALIDATION_REFERENCE_ARTIFACTS_DIR): "
            + joined
        )
    return requirements


def list_scenarios() -> str:
    lines = []
    for scenario in SCENARIOS.values():
        lines.append(f"- {scenario.name}: {scenario.description}")
        for requirement in describe_scenario_inputs(scenario):
            lines.append(f"    requires: {requirement}")
    return "\n".join(lines)


def resolve_source_gpkg(*, scenario: AtlasValidationScenario, provided_path: str | None) -> Path | None:
    if not scenario.requires_source_gpkg:
        return None
    raw_value = provided_path or os.environ.get("QFIT_VALIDATION_SOURCE_GPKG")
    if not raw_value:
        raise ValueError(
            f"Scenario '{scenario.name}' requires --source-gpkg (or QFIT_VALIDATION_SOURCE_GPKG)."
        )
    source_gpkg = Path(raw_value).expanduser().resolve()
    if not source_gpkg.exists():
        raise ValueError(f"Source GeoPackage not found: {source_gpkg}")
    return source_gpkg


def resolve_reference_artifacts_dir(*, scenario: AtlasValidationScenario, provided_path: str | None) -> Path | None:
    if not scenario.required_reference_artifacts:
        return None
    raw_value = provided_path or os.environ.get("QFIT_VALIDATION_REFERENCE_ARTIFACTS_DIR")
    if not raw_value:
        raise ValueError(
            f"Scenario '{scenario.name}' requires --reference-artifacts-dir "
            "(or QFIT_VALIDATION_REFERENCE_ARTIFACTS_DIR)."
        )
    artifacts_dir = Path(raw_value).expanduser().resolve()
    missing = [name for name in scenario.required_reference_artifacts if not (artifacts_dir / name).exists()]
    if missing:
        raise ValueError(
            f"Reference artifacts missing in {artifacts_dir}: {', '.join(missing)}"
        )
    return artifacts_dir


def run_scenario(
    *,
    scenario: AtlasValidationScenario,
    artifacts_root: Path,
    python_executable: str,
    source_gpkg: Path | None = None,
    reference_artifacts_dir: Path | None = None,
) -> int:
    run_dir = build_run_directory(artifacts_root=artifacts_root, scenario_name=scenario.name)
    run_dir.mkdir(parents=True, exist_ok=True)
    env = build_env(
        run_dir=run_dir,
        source_gpkg=source_gpkg,
        reference_artifacts_dir=reference_artifacts_dir,
    )

    print(f"Scenario: {scenario.name}")
    print(f"Description: {scenario.description}")
    print(f"Run directory: {run_dir}")
    print(f"Script: {scenario.script_path}")
    if source_gpkg is not None:
        print(f"Source GeoPackage: {source_gpkg}")
    if reference_artifacts_dir is not None:
        print(f"Reference artifacts dir: {reference_artifacts_dir}")
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
        "--source-gpkg",
        help="Required real-data source GeoPackage for scenarios that depend on local activity data.",
    )
    parser.add_argument(
        "--reference-artifacts-dir",
        help="Directory containing required reference input artifacts for curated scenarios.",
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
    source_gpkg = resolve_source_gpkg(scenario=scenario, provided_path=args.source_gpkg)
    reference_artifacts_dir = resolve_reference_artifacts_dir(
        scenario=scenario,
        provided_path=args.reference_artifacts_dir,
    )
    return run_scenario(
        scenario=scenario,
        artifacts_root=artifacts_root,
        python_executable=args.python,
        source_gpkg=source_gpkg,
        reference_artifacts_dir=reference_artifacts_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
