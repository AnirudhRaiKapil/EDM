# ADR-0004: Defer WSL2/Docker infrastructure on the current dev laptop

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
[ADR-0003](0003-trimmed-phase-1-stack.md) deferred Postgres/MinIO/Kafka behind lightweight
substitutes until Docker was available. WSL2 + Docker Engine were subsequently installed
(Ubuntu-24.04, Docker Engine via get.docker.com, both verified working individually — `docker run
hello-world` succeeded).

When the full `infrastructure/docker/docker-compose.yml` stack (Postgres + MinIO + Kafka) was
brought up, the entire WSL2 VM crash-looped: a full systemd boot sequence
(`sysinit.target` → `multi-user.target`) repeated every 30-40 seconds, taking every container
down with it. Five independent `.wslconfig` mitigations were tried and none resolved it:
`vmIdleTimeout=-1`, `memory=8GB`, `networkingMode=nat`, `guiApplications=false`,
`nestedVirtualization=false`, `processors=2`.

Windows System event log at the time of the crashes showed:
- `Service Control Manager` (event 7000): "The VMSP service failed to start... Insufficient
  system resources exist to complete the requested service."
- `Service Control Manager` (event 7000): "The Nested Network Virtualization service failed to
  start... A hypervisor feature is not available to the user."

The machine (ASUS ROG Strix GL503GE, 2018 hardware, BIOS from 2020) has Windows
Virtualization-Based Security (VBS) reported as `Running`. This is a known class of conflict:
VBS/Credential Guard and WSL2's nested Hyper-V virtualization both want exclusive control of the
same CPU virtualization extensions, and on some hardware/firmware combinations they cannot
stably coexist.

## Decision
Do not pursue Docker-based infrastructure on this laptop for now. Remaining mitigations
(disabling Memory Integrity/Core Isolation, or changing BIOS virtualization settings) involve a
real security tradeoff or require physical reboot-into-BIOS access — both are the user's call,
not a default action. The user chose to continue on the ADR-0003 lightweight stack rather than
make that tradeoff.

`infrastructure/docker/docker-compose.yml` is left in place, unchanged and untested-in-practice
on this machine. It remains the target for Postgres/MinIO/Kafka whenever Docker infrastructure
becomes available (different machine, a cloud VM, or after a BIOS/driver update that resolves
the VBS conflict).

## Consequences
- `services/edm-platform` continues to run on SQLite + local disk + DuckDB + in-process events
  (per ADR-0003) for an indefinite period, not just until "Docker is installed."
- No code changes result from this — the module/adapter boundaries already assumed this swap
  might be deferred.
- If revisiting this: check `Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2,3}` for
  recurring `VMSP`/`Nested Network Virtualization` event-id-7000 entries around any future WSL2
  crash before re-diagnosing from scratch.
