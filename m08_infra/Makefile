# Makefile — Module 08: Infrastructure
#
# Invoke from m08_infra/:
#   cd ~/future_prep/m08_infra && make all
#
# Targets:
#   make lint      — ruff (Python) + verible-verilog-lint (SV/Verilog)
#   make build     — build the qprep Docker image (../Dockerfile)
#   make demo      — docker compose up the iontrap-server + client services
#   make ci-local  — run .github/workflows/ci.yml locally via `act`
#   make all       — lint + build + demo
#   make clean     — tear down compose services/volumes, prune the image
#
# Prerequisites:
#   source ~/future_prep/scripts/activate_qprep.sh   (ruff, verible, act)
#   Docker daemon running (`docker ps` should not error)

REPO_ROOT := ..

.PHONY: all lint build demo ci-local clean

all: lint build demo
	@echo ""
	@echo "============================================"
	@echo " M08 ALL TARGETS COMPLETE"
	@echo "============================================"

# ─── Lint ─────────────────────────────────────────────────────────────────────
lint:
	@echo "--- [ruff] Python lint ---"
	cd $(REPO_ROOT) && ruff check .
	@echo "--- [verible] SV/Verilog lint ---"
	cd $(REPO_ROOT) && find m00_toolchain m01_sv_sva m02_cocotb m03_rfsoc_rtl m05_migen_amaranth \
	  -name '*.sv' -o -name '*.v' | xargs verible-verilog-lint --rules_config_search
	@echo ""

# ─── Docker image ─────────────────────────────────────────────────────────────
build:
	@echo "--- [docker build] qprep image ---"
	docker build -t qprep:latest -f Dockerfile $(REPO_ROOT)
	@echo ""

# ─── Compose demo: iontrap-server + client ───────────────────────────────────
demo:
	@echo "--- [docker compose] iontrap-server + client demo ---"
	docker compose up --build --abort-on-container-exit --exit-code-from client
	docker compose down
	@echo ""

# ─── Local CI via act ─────────────────────────────────────────────────────────
ci-local:
	@echo "--- [act] running .github/workflows/ci.yml locally ---"
	cd $(REPO_ROOT) && act push -W .github/workflows/ci.yml
	@echo ""

# ─── Clean ────────────────────────────────────────────────────────────────────
clean:
	-docker compose down -v --remove-orphans
	-docker image rm qprep:latest
	@echo "Cleaned."
