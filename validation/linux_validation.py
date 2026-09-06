#!/usr/bin/env python3
"""Disposable Linux permission probes. This is a test harness, not the v3 engine.

The account/ACL suite requires root and creates files only beneath a temporary
directory. It never creates host accounts or changes host policy/configuration.
The worker suite runs as an unprivileged user in a separately constrained container.
"""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import time

ROLES = {name: 21001 + i for i, name in enumerate([
    "scout", "analyst", "strategist", "guardian", "executor", "observer", "orchestrator"
])}
CONTROLLER = 21008
POLICY_GROUP = 22000
READERS = {
    "tickets": set(ROLES),
    "inbox": {"scout", "analyst", "guardian", "orchestrator"},
    "context": {"analyst", "strategist", "guardian", "orchestrator"},
    "plans": {"strategist", "executor", "guardian", "orchestrator"},
    "actions": {"executor", "guardian", "observer", "orchestrator"},
    "verdicts": {"guardian", "executor", "observer", "orchestrator"},
    "outcomes": {"observer", "orchestrator"},
}
RESULTS = []


def record(name, passed, **evidence):
    RESULTS.append({"name": name, "passed": bool(passed), "evidence": evidence})


def identity(uid):
    os.setgroups([POLICY_GROUP])
    os.setgid(uid)
    os.setuid(uid)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "prctl failed")


def as_user(uid, operation):
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            identity(uid)
            value = operation()
            result = {"ok": True, "value": value, "uid": os.geteuid()}
        except OSError as exc:
            result = {"ok": False, "errno": exc.errno, "error": str(exc), "uid": os.geteuid()}
        except BaseException as exc:
            result = {"ok": False, "error": repr(exc), "uid": os.geteuid()}
        data = json.dumps(result).encode()
        os.write(write_fd, data)
        os.close(write_fd)
        os._exit(0)
    os.close(write_fd)
    with os.fdopen(read_fd, "rb") as stream:
        data = stream.read()
    _, status = os.waitpid(pid, 0)
    if status != 0 or not data:
        raise RuntimeError(f"Probe child failed: {pid}, {status}")
    return json.loads(data)


def access(name, uid, operation, allowed):
    result = as_user(uid, operation)
    passed = result["ok"] if allowed else (
        not result["ok"] and result.get("errno") in (errno.EACCES, errno.EPERM, errno.EROFS)
    )
    record(name, passed, expected_allowed=allowed, actual=result)


def directory(path, uid=0, gid=0, mode=0o755):
    path.mkdir()
    os.chown(path, uid, gid)
    path.chmod(mode)


def file(path, content, uid=0, gid=0, mode=0o600):
    path.write_text(content)
    os.chown(path, uid, gid)
    path.chmod(mode)


def acl(path, readers, is_directory=False, mask=None):
    """Linux POSIX access ACL, applied without installing a host ACL utility."""
    undefined = 0xFFFFFFFF
    read = 5 if is_directory else 4
    entries = [(1, 7 if is_directory else 6, undefined)]
    entries += [(2, read, uid) for uid in sorted(set(readers))]
    entries += [(4, 0, undefined), (16, read if mask is None else mask, undefined), (32, 0, undefined)]
    value = struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *entry) for entry in entries)
    os.setxattr(path, "system.posix_acl_access", value)


def append(path):
    with path.open("a") as stream:
        stream.write("probe\n")
    return True


def permission_suite():
    if os.geteuid() != 0:
        raise RuntimeError("Permission probes require root to drop to each test UID")
    base = Path(tempfile.mkdtemp(prefix="hermes-permission-validation-"))
    base.chmod(0o755)
    observations = {}
    try:
        directory(base / "policy", gid=POLICY_GROUP, mode=0o750)
        file(base / "policy" / "policy.json", '{"version":1}', gid=POLICY_GROUP, mode=0o640)
        directory(base / "profiles")
        directory(base / "private", mode=0o700)
        file(base / "private" / "credentials", "SYNTHETIC-NOT-A-REAL-CREDENTIAL")
        directory(base / "accepted", uid=CONTROLLER, gid=CONTROLLER)
        policy_before = hashlib.sha256((base / "policy" / "policy.json").read_bytes()).hexdigest()
        for role, uid in ROLES.items():
            profile = base / "profiles" / role
            directory(profile, gid=uid, mode=0o750)
            file(profile / "config.json", '{"role":"' + role + '"}', gid=uid, mode=0o640)
            directory(profile / "state", uid, uid, 0o700)
            file(profile / "state" / "scratch", "private scratch", uid, uid)

        for role, uid in ROLES.items():
            profile = base / "profiles" / role
            policy = base / "policy" / "policy.json"
            access(f"{role}:policy_read", uid, policy.read_text, True)
            access(f"{role}:policy_write_denied", uid, lambda p=policy: append(p), False)
            access(f"{role}:policy_chmod_denied", uid, lambda p=policy: p.chmod(0o666), False)
            access(f"{role}:policy_replace_denied", uid, policy.unlink, False)
            access(f"{role}:own_config_read", uid, (profile / "config.json").read_text, True)
            access(f"{role}:own_config_write_denied", uid, lambda p=profile: append(p / "config.json"), False)
            access(f"{role}:own_config_replace_denied", uid, (profile / "config.json").unlink, False)
            access(f"{role}:private_scratch_write", uid, lambda p=profile: append(p / "state" / "scratch"), True)
            access(f"{role}:credential_read_denied", uid, (base / "private" / "credentials").read_text, False)
            access(f"{role}:become_root_denied", uid, lambda: os.setuid(0), False)
            other_uid = ROLES["guardian"] if role != "guardian" else ROLES["executor"]
            access(f"{role}:impersonate_role_denied", uid, lambda u=other_uid: os.setuid(u), False)
            for other in ROLES:
                if other != role:
                    target = base / "profiles" / other / "state" / "scratch"
                    access(f"{role}:read_{other}_scratch_denied", uid, target.read_text, False)

        for lane, readers in READERS.items():
            lane_path = base / "accepted" / lane
            directory(lane_path, CONTROLLER, CONTROLLER, 0o700)
            acl(lane_path, [ROLES[r] for r in readers], is_directory=True)
            record_path = lane_path / "record.json"
            file(record_path, '{"synthetic":true}', CONTROLLER, CONTROLLER)
            acl(record_path, [ROLES[r] for r in readers])
            access(f"controller:{lane}_write", CONTROLLER, lambda p=record_path: append(p), True)
            for role, uid in ROLES.items():
                access(f"{role}:{lane}_read", uid, record_path.read_text, role in readers)
                access(f"{role}:{lane}_accepted_write_denied", uid, lambda p=record_path: append(p), False)

        mask_file = base / "acl-mask"
        file(mask_file, "ACL-mask-positive-and-negative-control")
        acl(mask_file, [ROLES["executor"]])
        access("acl_mask:read_enabled", ROLES["executor"], mask_file.read_text, True)
        acl(mask_file, [ROLES["executor"]], mask=0)
        access("acl_mask:read_disabled", ROLES["executor"], mask_file.read_text, False)

        # Show the limitation instead of claiming per-role UIDs isolate repositories.
        for repo in ("repo-a", "repo-b"):
            directory(base / repo, ROLES["executor"], ROLES["executor"], 0o700)
            file(base / repo / "source", repo, ROLES["executor"], ROLES["executor"])
        same_uid = as_user(ROLES["executor"], lambda: (base / "repo-b" / "source").read_text())
        observations["same_uid_can_read_second_task_without_mount_isolation"] = same_uid["ok"]
        record("same_uid_limitation_control", same_uid["ok"], explanation="Separate task mounts/namespaces are required; role UIDs alone do not isolate tasks")
        policy_after = hashlib.sha256((base / "policy" / "policy.json").read_bytes()).hexdigest()
        record("policy_unchanged_after_all_attacks", policy_before == policy_after, before=policy_before, after=policy_after)
        observations["filesystem"] = subprocess.run(["stat", "-f", "-c", "%T", str(base)], capture_output=True, text=True, check=True).stdout.strip()
        observations["accounts"] = {}
        for role, expected_uid in ROLES.items():
            try:
                entry = pwd.getpwnam("hermes-" + role)
                observations["accounts"][role] = {"present": True, "uid": entry.pw_uid, "shell": entry.pw_shell, "expected_uid": expected_uid}
            except KeyError:
                observations["accounts"][role] = {"present": False, "tested_numeric_uid": expected_uid}
        return observations
    finally:
        # Only the directory allocated by this process, never an input path.
        shutil.rmtree(base)


def worker_suite():
    record("worker_uid", os.geteuid() == ROLES["executor"], uid=os.geteuid())
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
    record("no_capabilities", int(status["CapEff"].strip(), 16) == 0, actual=status["CapEff"].strip())
    record("no_new_privileges", status["NoNewPrivs"].strip() == "1", actual=status["NoNewPrivs"].strip())
    record("seccomp_filter", status["Seccomp"].strip() == "2", actual=status["Seccomp"].strip())
    for name, path, allowed in [
        ("root_readonly", "/should-not-write", False),
        ("input_readonly", "/approved/marker", False),
        ("scratch_writable", "/workspace/probe", True),
    ]:
        try:
            Path(path).write_text("probe")
            actual = True
        except OSError as exc:
            actual = False
            record(name, not allowed and exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS), errno=exc.errno)
        else:
            record(name, allowed, actual_allowed=actual)
    record("approved_input_readable", Path("/approved/marker").read_text().strip() == "approved-input")
    for path in ("/unrelated", "/var/run/docker.sock", "/mnt/c", "/mnt/d", "/host-home"):
        record("unmounted:" + path, not Path(path).exists())
    with socket.socket() as sock:
        sock.settimeout(1)
        result = sock.connect_ex(("1.1.1.1", 443))
    record("external_network_denied", result != 0, connect_errno=result)
    for name, path, expected in [
        ("memory_limit", "/sys/fs/cgroup/memory.max", "536870912"),
        ("pids_limit", "/sys/fs/cgroup/pids.max", "64"),
        ("cpu_limit", "/sys/fs/cgroup/cpu.max", "100000 100000"),
    ]:
        value = Path(path).read_text().strip()
        record(name, value == expected, expected=expected, actual=value)
    return {"kernel_limits_checked": True, "resource_exhaustion_stress_test": "see separate pids and oom suites"}


def pids_suite():
    limit = Path("/sys/fs/cgroup/pids.max").read_text().strip()
    if limit != "64":
        raise RuntimeError("Refusing process-exhaustion probe without the verified 64-process kernel limit")
    children = []
    blocked = False
    failure_errno = None
    try:
        # Bounded even if the kernel limit is broken. Children only wait for a signal.
        for _ in range(70):
            try:
                pid = os.fork()
            except OSError as exc:
                failure_errno = exc.errno
                blocked = exc.errno == errno.EAGAIN
                break
            if pid == 0:
                signal.pause()
                os._exit(0)
            children.append(pid)
        record("pids:kernel_denied_fork", blocked, errno=failure_errno, children_created=len(children))
        record("pids:bounded_process_count", 0 < len(children) < 64, children_created=len(children), kernel_limit=64)
    finally:
        for pid in children:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for pid in children:
            os.waitpid(pid, 0)
    remaining = int(Path("/sys/fs/cgroup/pids.current").read_text())
    record("pids:children_reaped", remaining == 1, remaining=remaining)
    return {"maximum_fork_attempts": 70, "kernel_events": Path("/sys/fs/cgroup/pids.events").read_text()}


def oom_suite():
    limit = Path("/sys/fs/cgroup/memory.max").read_text().strip()
    if limit != "536870912":
        raise RuntimeError("Refusing OOM probe without the verified 512 MiB kernel memory limit")
    # The trusted launcher must independently inspect Docker's memory/swap limits
    # before starting this process, then inspect OOMKilled and exit 137 afterward.
    print(json.dumps({"event": "bounded_oom_probe_started", "memory_max": int(limit),
                      "allocation_bytes": 600 * 1024 * 1024,
                      "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}), flush=True)
    allocation = bytearray(600 * 1024 * 1024)
    record("oom:allocation_exceeded_limit", False, allocated_bytes=len(allocation))
    return {"unexpected_allocation_success": True}


def repository_suite(language):
    """Exercise two command adapters, using deterministic synthetic patches.

    No model implementation, controller admission, review, or PR is simulated
    as a success. Those require a later live engine test.
    """
    workspace = Path("/workspace") / ("repo-" + language)
    workspace.mkdir()
    if language == "python":
        source = workspace / "clamp.py"
        source.write_text("def clamp(x):\n    return x\n")
        (workspace / "test_clamp.py").write_text(
            "from clamp import clamp\n"
            "for x, expected in [(-5,0),(0,0),(4,4),(10,10),(11,10)]:\n"
            "    assert clamp(x) == expected, (x, clamp(x), expected)\n"
        )
        command = ["python3", "-B", "test_clamp.py"]
        corrected = "def clamp(x):\n    return max(0, min(10, x))\n"
    else:
        source = workspace / "clamp.cjs"
        source.write_text("module.exports = x => x;\n")
        (workspace / "test_clamp.cjs").write_text(
            "const assert = require('node:assert/strict');\n"
            "const clamp = require('./clamp.cjs');\n"
            "for (const [x, expected] of [[-5,0],[0,0],[4,4],[10,10],[11,10]])\n"
            "  assert.equal(clamp(x), expected);\n"
        )
        command = ["node", "test_clamp.cjs"]
        corrected = "module.exports = x => Math.max(0, Math.min(10, x));\n"
    baseline = subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=10)
    record(language + ":baseline_regression_fails", baseline.returncode != 0,
           exit_code=baseline.returncode, stderr=baseline.stderr)
    source.write_text(corrected)
    fixed = subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=10)
    record(language + ":candidate_regression_passes", fixed.returncode == 0,
           exit_code=fixed.returncode, stderr=fixed.stderr)
    return {"fixture": "synthetic", "patch_author": "test harness, not an AI agent",
            "command": command, "live_development_cycle": "NOT_TESTED"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["permissions", "worker", "repository", "pids", "oom"], default="permissions")
    parser.add_argument("--language", choices=["python", "javascript"], default="python")
    parser.add_argument("--output")
    args = parser.parse_args()
    started = time.time()
    observations = {}
    error = None
    try:
        if args.suite == "permissions":
            observations = permission_suite()
        elif args.suite == "worker":
            observations = worker_suite()
        elif args.suite == "pids":
            observations = pids_suite()
        elif args.suite == "oom":
            observations = oom_suite()
        else:
            observations = repository_suite(args.language)
    except BaseException as exc:
        error = repr(exc)
        record("harness_completed", False, error=error)
    report = {
        "schema_version": 1, "suite": args.suite,
        "scope": "Linux enforcement primitives in a disposable fixture; not live Hermes engine acceptance",
        "platform": platform.platform(), "python": platform.python_version(),
        "elapsed_seconds": round(time.time() - started, 3),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "counts": {"passed": sum(r["passed"] for r in RESULTS), "failed": sum(not r["passed"] for r in RESULTS)},
        "results": RESULTS, "observations": observations, "error": error,
        "engine_acceptance": "NOT_RUN_NO_V3_IMPLEMENTATION",
    }
    encoded = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(encoded + "\n")
    else:
        print(encoded)
    return 1 if report["counts"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
