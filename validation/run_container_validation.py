#!/usr/bin/env python3
"""Run the same disposable Docker tests on Windows or cloud Linux.

Never mounts a Docker socket into a container. Only removes containers whose
unique validation label matches this invocation. Outputs are evidence of the
fixture, not of a running v3 controller.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import time
import uuid


def run(args, *, timeout=120, check=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"{args[0:3]} failed ({result.returncode}): {result.stderr[-3000:]}")
    return result


def inspect(container):
    return json.loads(run(["docker", "inspect", container]).stdout)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--environment", choices=["windows-docker-desktop", "cloud-linux"], required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    session = uuid.uuid4().hex
    image = json.loads(run(["docker", "image", "inspect", args.image]).stdout)[0]
    image_id = image["Id"]
    summary = {"schema_version": 1, "environment": args.environment,
               "host_platform": platform.platform(), "run_id": session,
               "image_id": image_id, "image_repo_digests": image.get("RepoDigests", []),
               "engine": json.loads(run(["docker", "version", "--format", "{{json .Server}}"]).stdout),
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "runs": [], "engine_acceptance": "NOT_RUN_NO_V3_IMPLEMENTATION"}
    failures = 0
    with tempfile.TemporaryDirectory(prefix="hermes-validation-input-") as temporary:
        approved = Path(temporary)
        (approved / "marker").write_text("approved-input\n")
        # Linux TemporaryDirectory defaults to 0700. The container worker has a
        # different UID and needs to read this synthetic input through the bind.
        # The mount remains read-only, and no credentials are stored here.
        approved.chmod(0o755)
        (approved / "marker").chmod(0o444)
        for suite, language in [("permissions", None), ("worker", None), ("repository", "python"), ("repository", "javascript"), ("pids", None), ("oom", None)]:
            key = suite + ("-" + language if language else "")
            name = "hermes-validation-" + session[:12] + "-" + key
            label = "hermes.validation.run=" + session
            common = ["docker", "create", "--name", name, "--label", label,
                      "--network", "none", "--read-only", "--memory", "512m", "--memory-swap", "512m",
                      "--pids-limit", "64", "--cpus", "1", "--security-opt", "no-new-privileges",
                      "--log-driver", "local", "--log-opt", "max-size=5m", "--log-opt", "max-file=2",
                      "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m,mode=1777"]
            if suite != "permissions":
                common += ["--user", "21005:21005", "--cap-drop", "ALL",
                           "--tmpfs", "/workspace:rw,nosuid,nodev,size=64m,uid=21005,gid=21005,mode=0700",
                           "--mount", "type=bind,source=" + str(approved) + ",target=/approved,readonly"]
            else:
                common += ["--user", "0:0"]  # Trusted fixture setup; children drop UID and privileges.
            common += [image_id, "--suite", suite]
            if language:
                common += ["--language", language]
            container = None
            receipt = {"suite": key, "phase": "create", "passed": False}
            try:
                container = run(common).stdout.strip()
                actual = inspect(container)
                host = actual["HostConfig"]
                guards = {
                    "image": actual["Image"] == image_id,
                    "network": host["NetworkMode"] == "none",
                    "readonly_root": host["ReadonlyRootfs"] is True,
                    "memory": host["Memory"] == 536870912,
                    "memory_swap": host["MemorySwap"] == 536870912,
                    "pids": host["PidsLimit"] == 64,
                    "cpu": host["NanoCpus"] == 1000000000,
                    "no_new_privileges": "no-new-privileges" in host["SecurityOpt"],
                    "no_privileged": host["Privileged"] is False,
                    "expected_label": actual["Config"]["Labels"].get("hermes.validation.run") == session,
                }
                if suite != "permissions":
                    guards.update({"uid": actual["Config"]["User"] == "21005:21005",
                                   "drop_all": "ALL" in host["CapDrop"],
                                   "only_approved_bind": len(actual["Mounts"]) == 1
                                   and actual["Mounts"][0]["Destination"] == "/approved"
                                   and not actual["Mounts"][0]["RW"]})
                receipt["admission_guards"] = guards
                receipt["container_id"] = container
                receipt["actual_configuration"] = {"Image": actual["Image"], "User": actual["Config"]["User"],
                                                   "HostConfig": host, "Mounts": actual["Mounts"]}
                if not all(guards.values()):
                    raise RuntimeError("Actual container configuration differs from the test envelope")
                receipt["phase"] = "run"
                started = time.time()
                result = run(["docker", "start", "--attach", container], check=False)
                after = inspect(container)
                receipt["elapsed_seconds"] = round(time.time() - started, 3)
                receipt["exit_code"] = after["State"]["ExitCode"]
                receipt["running_after_attach"] = after["State"]["Running"]
                receipt["oom_killed"] = after["State"]["OOMKilled"]
                receipt["stderr"] = result.stderr
                receipt["runtime_error"] = after["State"].get("Error")
                if not result.stdout.strip():
                    raise RuntimeError("Container returned no test report: " + result.stderr[-2000:])
                if suite == "oom":
                    # An OOM-killed process cannot write its own final receipt.
                    # Bind the startup marker to independently inspected runtime state.
                    marker = json.loads(result.stdout)
                    oom_passed = (marker.get("event") == "bounded_oom_probe_started"
                                  and marker.get("memory_max") == host["Memory"]
                                  and marker.get("allocation_bytes") == 600 * 1024 * 1024
                                  and result.returncode == 137 and receipt["exit_code"] == 137
                                  and receipt["oom_killed"] is True and not receipt["running_after_attach"])
                    report = {"schema_version": 1, "suite": "oom",
                              "scope": "Bounded container memory-exhaustion test, not controller recovery",
                              "script_sha256": marker.get("script_sha256"),
                              "counts": {"passed": int(oom_passed), "failed": int(not oom_passed)},
                              "startup_marker": marker, "docker_state": after["State"],
                              "engine_acceptance": "NOT_RUN_NO_V3_IMPLEMENTATION"}
                else:
                    report = json.loads(result.stdout)
                (output / (key + ".json")).write_text(json.dumps(report, indent=2) + "\n")
                receipt["counts"] = report["counts"]
                receipt["passed"] = (result.returncode == 0 and receipt["exit_code"] == 0
                                     and not receipt["running_after_attach"] and not receipt["oom_killed"]
                                     and report["counts"]["failed"] == 0)
                if suite == "oom":
                    receipt["passed"] = oom_passed
                if suite == "permissions":
                    accounts = report["observations"]["accounts"]
                    receipt["named_accounts_valid"] = all(a.get("present") and a["uid"] == a["expected_uid"]
                                                          and a["shell"] == "/usr/sbin/nologin" for a in accounts.values())
                    receipt["passed"] = receipt["passed"] and receipt["named_accounts_valid"]
                receipt["phase"] = "finished"
            except Exception as exc:
                receipt["error"] = repr(exc)
            finally:
                if container:
                    current = inspect(container)
                    if current["Config"]["Labels"].get("hermes.validation.run") != session:
                        raise RuntimeError("Refusing cleanup of a container not owned by this validation run")
                    run(["docker", "rm", "--force", container])
                    receipt["container_removed"] = True
            if not receipt["passed"]:
                failures += 1
            summary["runs"].append(receipt)
            (output / "container-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps({"suite": key, "passed": receipt["passed"], "error": receipt.get("error"),
                              "counts": receipt.get("counts"), "container_removed": receipt.get("container_removed")}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
