# M08 — Infrastructure

**Author:** Nasir Ali
**Org:** C-DAC Noida
**Goal:** Package the qprep toolchain into a reproducible container, wire up
a GitHub Actions CI pipeline that lints and tests every open-source module
on every push, and gate local commits with the same checks via pre-commit —
so "works on my machine" stops being a risk for this repo.

---

## Why some M08 files live outside `m08_infra/`

Every other module keeps everything under its own directory. Two tools in
this module don't allow that:

| File | Required location | Why |
|------|--------------------|-----|
| `.github/workflows/ci.yml` | repo root `.github/workflows/` | GitHub Actions only discovers workflows there |
| `.pre-commit-config.yaml` | repo root | `pre-commit` only reads this filename from the git root |
| `ruff.toml` | repo root | `ruff check .` walks up from cwd looking for this; keeping it at root means both the CI step and every module's local `ruff check .` see the same rules |
| `.rules.verible_lint` | repo root | `verible-verilog-lint --rules_config_search` walks upward from each linted file to find it |

Everything else (Dockerfile, docker-compose.yml, the demo client, this
README, the Makefile) lives in `m08_infra/` as usual.

---

## Tool table

| Tool | Version | Role |
|------|---------|------|
| Docker | 26.1.3 | Container runtime |
| Docker Compose | v2 plugin | Multi-service orchestration |
| GitHub Actions | — | CI pipeline (`.github/workflows/ci.yml`) |
| `act` | 0.2.89 (conda-forge) | Run the Actions workflow locally without pushing |
| pre-commit | 4.6.0 | Git hook manager |
| ruff | 0.15.16 | Python lint (`ruff.toml`) |
| verible-verilog-lint | conda-forge | SV/Verilog static lint (`.rules.verible_lint`) |

---

## What's containerized, and what isn't

The Docker image (`Dockerfile`) builds `environment.yml` on top of
`condaforge/miniforge3` — iverilog, Verilator, cocotb, QuTiP, Migen,
Amaranth, qiskit, the whole Python/RTL-sim stack.

**Vivado/xsim is deliberately not in the image.** It's a multi-GB
proprietary install gated by an Xilinx license file tied to this
workstation — it can't be redistributed in a public image or pulled into a
GitHub-hosted runner. Practical effect:

- M01's `ex05`–`ex07` and `axi_stream` (SVA needs concurrent-assertion
  support xsim has and iverilog doesn't) and all of M09 (UVM) stay
  workstation-only.
- Every other module — M00, M01 `ex01`–`ex04`, M02, M03, M04, M05, M06,
  M07 — builds and tests identically in the container, in CI, and on bare
  metal, because all three read the same `environment.yml`.

## Exercise ladder

### ex01 — `Dockerfile`: reproducible open-source qprep image
Single-stage build: `condaforge/miniforge3` → `mamba env create -f
environment.yml`. The env spec is copied in before the rest of the repo so
rebuilds that only touch source files hit Docker's layer cache instead of
re-solving conda every time.

**Key concept:** `docker run` doesn't source a login shell, so `conda
activate qprep` silently no-ops across `RUN`/`CMD` layers. `mamba run -n
qprep` is the non-interactive equivalent — it's what both the `SHELL`
directive and the image `ENTRYPOINT` use, so `docker run qprep:latest
python ...` lands in the right env without any extra flags.

### ex02 — `docker-compose.yml` + `demo_client.py`: capstone services
Two containers from the same image:
- `iontrap-server` — M06's existing asyncio TCP/JSON server
  (`iontrap.server.run_server`), bound to `0.0.0.0` so the other container
  can reach it by service name.
- `client` — `demo_client.py`, sends `rabi_scan` and `ms_gate` requests
  over the compose network and prints the results.

**Key concept:** M07's `qpu/node.py` (`QPUNode.connect()`) wires two Python
objects together in one process (`self._peer = other`) — there's no
network protocol to speak, so it can't be split across containers as-is.
The one component in this repo that IS a real network service is M06's
`iontrap.server`. Running it as its own container and hitting it from a
separate client container is the honest version of "capstone services" —
it's the same client/server split a real multi-node deployment would use,
built from what already exists rather than force-fitting an in-process API
across a network boundary.

### ex03 — `.github/workflows/ci.yml`: GitHub Actions
One job, `ubuntu-latest`, `conda-incubator/setup-miniconda` loading
`environment.yml` (so CI and local dev share one source of truth), then:
`ruff check .` → `verible-verilog-lint` over every `.sv`/`.v` file →
`make ex01 ex02 ex03 ex04` in M01 (the iverilog-only exercises) → `make
all`/`make test` in M02–M07.

**Key concept:** the *lint* step needed a real decision, not just wiring.
`ruff check .` cold returned 186 errors and `verible-verilog-lint` returned
66, almost entirely in M04–M07 (Python: routine unused-import/style debt
from three weeks of iterative development) and in the Migen/Amaranth
files (`from migen import *` — idiomatic HDL-DSL style, not an accidental
wildcard import). Retroactively rewriting six already-complete,
DoC-confirmed modules to satisfy a linter introduced in M08 would be scope
creep for an infrastructure task. Instead: `ruff.toml` and
`.rules.verible_lint` waive the specific noisy rules **only** for the
modules that predate this gate (`per-file-ignores` for M04–M07's Python,
a handful of named rules for pre-M08 SV/Verilog), while M00–M03,
`m08_infra`, and M09+ stay on the strict default ruleset. Two genuinely
trivial one-line issues in M02/M03 (`fifo_bfm.py`'s ambiguous `l` variable,
an unused `numpy` import in `test_envelope.py`) were fixed directly instead
of waived — zero behavioral risk, both modules' tests reverified green
after the edit.

### ex04 — `.pre-commit-config.yaml`: local gate
Mirrors the CI lint step so failures show up at `git commit` time instead
of after a push: `ruff` (+`--fix`) and `ruff-format` from
`astral-sh/ruff-pre-commit`, `verible-verilog-lint` as a `language: system`
hook (it's a conda-forge binary, not something pre-commit can vendor),
plus the standard `pre-commit-hooks` hygiene set (trailing whitespace,
EOF newline, YAML syntax, large-file guard).

**Key concept:** `language: system` hooks run whatever binary is on
`$PATH` at hook time — that's why `pre-commit install` (and any manual
`pre-commit run`) needs to happen inside `source
scripts/activate_qprep.sh`, or `verible-verilog-lint` won't resolve.

**Gotcha:** `pre-commit run --all-files` is not a harmless dry run — its
`ruff-format`/`trailing-whitespace` hooks rewrite every matching file in the
repo on the spot, which reformatted all of M02–M07 (and `CLAUDE.md`) well
beyond this module's scope the first time it was run here. `pre-commit
run` (staged files only) is the safe day-to-day command; reach for
`--all-files` deliberately, and expect it to touch every module, not just
the one you're working in.

---

## Module layout

```
m08_infra/
├── Dockerfile           ← qprep image (open-source toolchain only)
├── docker-compose.yml   ← iontrap-server + client demo
├── demo_client.py        ← client half of the compose demo
├── Makefile
└── README.md

(repo root)
├── .github/workflows/ci.yml   ← CI pipeline
├── .pre-commit-config.yaml    ← local git-hook gate
├── ruff.toml                  ← Python lint rules + per-module waivers
└── .rules.verible_lint        ← SV/Verilog lint rules + waivers
```

---

## Quick start

```bash
source ~/future_prep/scripts/activate_qprep.sh
cd m08_infra

# Lint everything (same checks CI and pre-commit run)
make lint

# Build the open-source qprep image
make build

# Run the two-service capstone demo (iontrap-server + client)
make demo

# Run the GitHub Actions workflow locally, without pushing
make ci-local
```

Expected `make demo` output:
```
client-1  | [client] connecting to iontrap-server at iontrap-server:7777
client-1  | [client] rabi_scan  -> t_pi_us=10.000
client-1  | [client] ms_gate    -> fidelity=0.9890
client-1 exited with code 0
```

One-time local setup so `git commit` runs the same lint gate as CI:
```bash
pre-commit install
```

---

## Definition of Command (DoC)

Pass ALL of the following **without references**:

1. **No-xsim rationale**: Explain why Vivado/xsim isn't in the Docker
   image or the CI runner, and name exactly which modules/exercises that
   excludes (M01 `ex05`–`ex07` + `axi_stream`, all of M09).

2. **`mamba run` vs `conda activate`**: Explain why the Dockerfile uses
   `mamba run -n qprep` instead of `conda activate qprep`, and what would
   silently break if it didn't.

3. **Compose service design**: Explain why the docker-compose demo runs
   M06's `iontrap.server` rather than M07's `QPUNode`, tracing the
   difference back to `QPUNode.connect()`'s in-process `self._peer`
   assignment vs. `iontrap.server`'s `asyncio.start_server`.

4. **Lint waiver defense**: Given `ruff.toml`'s `per-file-ignores`, explain
   which modules are waived, which specific rules, and why — and why
   `m05_migen_amaranth/rtl/*.py` gets a *different* waiver (`F403`/`F405`
   for `import *`) than `m04_artiq`/`m06_iontrap_emu`/`m07_capstone`
   (`F401`/`E401`/etc. for accumulated style debt).

5. **File location constraints**: Name the four M08 files that must live
   outside `m08_infra/` and, for each, the specific tool-discovery rule
   that forces its location.

6. **CI vs pre-commit**: Explain the relationship between
   `.github/workflows/ci.yml` and `.pre-commit-config.yaml` — why both
   exist, what runs where, and why `pre-commit install` must happen
   inside `source scripts/activate_qprep.sh`.

7. **Fresh-clone acid test**: From a clean checkout with no Docker cache,
   run `make build && make demo` in `m08_infra/` and get the two-line
   `rabi_scan`/`ms_gate` output — without looking at the Makefile.

8. **`act` run**: Run `make ci-local` and get a green run of every step
   in `ci.yml`, explaining what `act`'s `-P ubuntu-latest=...` mapping in
   `~/.config/act/actrc` is doing.
