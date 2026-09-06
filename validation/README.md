# Hermes validation package

This package tests Linux permission and container mechanisms proposed for v3.
It is not a substitute implementation of the development engine. A passing
fixture does not certify Hermes tool dispatch, its approval gate, model access,
GitHub publication, or recovery.

## What is tested

- Seven distinct effective Unix UIDs; each role has positive read/write controls.
- Administrator-owned policy and profile configuration, with protected parents.
- Private role scratch, denial of other role scratch, synthetic credential denial.
- Denial of UID switching and modifications of accepted controller-owned records.
- An explicit artifact-reader matrix using actual Linux POSIX ACLs, including ACL masks.
- The limitation that the same role UID can access another task without mount isolation.
- A separate worker container's actual UID, effective capabilities, seccomp,
  no-new-privileges, network isolation, mounts, and cgroup resource limits.
- Process exhaustion: a verified 64-process cgroup limit rejects further forks;
  the probe reaps every child. It makes at most 70 attempts even on failure.
- Memory exhaustion: after Docker and the kernel both show a 512 MiB cap, a
  bounded 600 MiB allocation must produce exit 137 with Docker's OOMKilled flag.
  This tests the kernel boundary, not the absent controller's recovery behavior.

The root permission suite makes files only in its own temporary directory. It
does not create host users or modify host settings. The Docker image contains
seven actual named service accounts; WSL tests use temporary numeric identities
and separately report whether the named service accounts are installed.

## Requirements that remain separate

Cloud execution requires an explicitly selected VM or approval to publish/run
the workflow. Host installation and login-start changes require approval. Live
model and GitHub tests require a real controller and scoped credentials. None
of those are implied by a passing fixture suite.

The same package must be run in a cloud Linux environment and on the selected
WSL installation. Record environment versions and file/image hashes with each
result. Do not label a Docker Desktop run as a cloud run.

No production data or credentials belong in the test image or artifacts.

## Run locally

On Windows, run `windows_acceptance.ps1` in an approved host session. It records
platform evidence and exits nonzero when a required platform check fails. It
does not fix settings or install the engine.

Build the Docker image using `Dockerfile` and the digest in `base-image.txt`.
Run `run_container_validation.py --image IMAGE --output-dir DIRECTORY
--environment windows-docker-desktop` from Windows, or select `cloud-linux`
when actually executing on a cloud host. A label alone is not cloud evidence;
retain the remote job URL, commit identity, and downloaded artifacts.

The workflow under `cloud/` is intended to be copied to
`.github/workflows/hermes-validation.yml` only after publication approval.
Do not publish local `results/`, the source audit documents, or personal data.

See `VALIDATION-REPORT.md` for actual results, limitations, and outstanding tests.
