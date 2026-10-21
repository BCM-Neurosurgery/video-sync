"""Submit a CSV sync config to Slurm from a source checkout."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

import yaml


def _git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _load_mapping(path):
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return config


def _prepare_run(repo, config_path, resources):
    config = _load_mapping(config_path)
    if config.get("csv_only") is not True:
        raise ValueError("submit-sync currently requires csv_only: true")
    for key in ("output_dir", "patient_dir"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"Config requires {key}")
    modes = ("jobs", "sessions", "nsp_dir", "flat_dir", "base_dir")
    if sum(key in config for key in modes) != 1:
        raise ValueError("Configure exactly one of " + ", ".join(modes))
    if not Path(config["patient_dir"]).is_dir():
        raise ValueError("patient_dir is not an accessible directory")
    if _git(
        repo,
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        "pyvideosync",
        "pyproject.toml",
        "uv.lock",
    ):
        raise ValueError(
            "Commit source changes before submitting; jobs use committed code"
        )
    revision = _git(repo, "rev-parse", "HEAD")
    parent = Path(config["output_dir"]).resolve() / "runs"
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
    run_dir = Path(tempfile.mkdtemp(prefix=stamp, dir=parent))
    (run_dir / "logs").mkdir()
    (run_dir / "input-config.yaml").write_bytes(config_path.read_bytes())
    config["output_dir"] = str(run_dir / "outputs")
    (run_dir / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))

    # Read committed files so queued jobs are independent of later checkout edits.
    tracked = _git(
        repo, "ls-tree", "-r", "--name-only", revision, "pyvideosync"
    ).splitlines()
    for name in [name for name in tracked if name.endswith(".py")] + [
        "pyproject.toml",
        "uv.lock",
    ]:
        target = run_dir / "code" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            subprocess.check_output(
                ["git", "-C", str(repo), "show", f"{revision}:{name}"]
            )
        )
    (run_dir / "code" / "run.py").write_text(
        "from pyvideosync.main import main\n\nmain()\n"
    )
    # Keep the venv path; resolving this symlink would bypass its environment.
    python = str(Path(sys.executable).absolute())
    command = [
        python,
        str(run_dir / "code" / "run.py"),
        "--config",
        str(run_dir / "config.yaml"),
    ]
    script = "\n".join(
        [
            "#!/bin/bash",
            "set -euo pipefail",
            "umask 077",
            "export PYTHONUNBUFFERED=1",
            "export MPLBACKEND=Agg",
            'export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"',
            'export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"',
            'export MKL_NUM_THREADS="$OMP_NUM_THREADS"',
            "exec " + shlex.join(command),
            "",
        ]
    )
    (run_dir / "job.sh").write_text(script)
    metadata = dict(
        state="prepared",
        commit=revision,
        python=python,
        python_version=sys.version,
        source_config=str(config_path),
        working_directory=str(Path.cwd()),
        resources=resources,
    )
    (run_dir / "submission.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return run_dir, metadata


def main():
    repo = Path(__file__).resolve().parents[1]
    profile_dir = repo / "configs" / "slurm"
    parser = argparse.ArgumentParser(
        description="Submit a CSV sync config to Slurm. Run from a source checkout with its installed Python environment."
    )
    parser.add_argument("--config", "-c", required=True, type=Path)
    parser.add_argument(
        "--cluster",
        default="wrangell",
        choices=sorted(p.stem for p in profile_dir.glob("*.yaml")),
    )
    parser.add_argument("--partition")
    parser.add_argument("--cpus", type=int)
    parser.add_argument("--mem", help="Slurm memory request, e.g. 8G")
    parser.add_argument("--time", help="Slurm time limit, e.g. 08:00:00")
    parser.add_argument("--account")
    parser.add_argument("--qos")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare a run and print its sbatch command without submitting",
    )
    args = parser.parse_args()
    try:
        if not args.dry_run and shutil.which("sbatch") is None:
            raise ValueError("sbatch is unavailable; run this command on the cluster")
        resources = _load_mapping(profile_dir / f"{args.cluster}.yaml")
        for field in ("partition", "cpus", "mem", "time", "account", "qos"):
            value = getattr(args, field)
            if value is not None:
                resources[field] = value
        if not isinstance(resources.get("cpus"), int) or resources["cpus"] < 1:
            raise ValueError("cpus must be a positive integer")
        for field in ("partition", "mem", "time"):
            if (
                not isinstance(resources.get(field), str)
                or not resources[field].strip()
            ):
                raise ValueError(f"Cluster profile requires {field}")
        run_dir, metadata = _prepare_run(repo, args.config.resolve(), resources)
        command = [
            "sbatch",
            "--parsable",
            "--job-name=video-sync",
            "--nodes=1",
            "--ntasks=1",
            f"--partition={resources['partition']}",
            f"--cpus-per-task={resources['cpus']}",
            f"--mem={resources['mem']}",
            f"--time={resources['time']}",
            f"--chdir={Path.cwd()}",
            f"--output={run_dir}/logs/%j.log",
        ]
        for field in ("account", "qos"):
            if resources.get(field):
                command.append(f"--{field}={resources[field]}")
        command.append(str(run_dir / "job.sh"))
        print(f"Run directory: {run_dir}", flush=True)
        if args.dry_run:
            print("Prepared only; no job submitted.\n" + shlex.join(command))
            return
        result = subprocess.run(command, text=True, capture_output=True)
        metadata.update(sbatch_stdout=result.stdout, sbatch_stderr=result.stderr)
        metadata["state"] = (
            "submitted" if result.returncode == 0 else "submission_failed"
        )
        job_id = result.stdout.strip().split(";")[0]
        if result.returncode == 0 and job_id.isdigit():
            metadata["job_id"] = job_id
        (run_dir / "submission.json").write_text(json.dumps(metadata, indent=2) + "\n")
        if result.returncode:
            raise ValueError(f"Slurm rejected the submission: {result.stderr.strip()}")
        if not job_id.isdigit():
            raise ValueError(
                f"Slurm returned an unrecognized job ID; check {run_dir}/submission.json before resubmitting"
            )
        print(f"Submitted Slurm job: {job_id}")
        print(f"Log: {run_dir}/logs/{job_id}.log")
        print(f"Outputs: {run_dir}/outputs")
        print(f"Status: squeue -j {job_id}")
        print(f"Result: sacct -j {job_id} --format=JobID,State,ExitCode,Elapsed,MaxRSS")
    except (OSError, ValueError, yaml.YAMLError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"submit-sync: {exc}\n")


if __name__ == "__main__":
    main()
