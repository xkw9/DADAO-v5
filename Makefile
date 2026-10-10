# DADAO-v5 top-level orchestration.
#
# Make is the stable user interface (ADR-0002: .tao/knowledge/adr-0002-build-orchestration.md); the actual manifest/fetch/patch
# logic is delegated to Python standard-library scripts under tools/infra/. All
# disposable data lives under .work/ (gitignored); persistent upstream mirrors
# live under .cache/ and are never touched by clean-work.

PYTHON ?= python3

# Component source/build trees (all under the disposable .work/ root). The
# llvm source is the monorepo checkout with its `llvm/` project subdirectory.
QEMU_SRC   ?= .work/source/qemu
QEMU_BUILD ?= .work/build/qemu
LLVM_SRC   ?= .work/source/llvm-project/llvm
LLVM_BUILD ?= .work/build/llvm
GEM5_SRC   ?= .work/source/gem5
GEM5_BUILD ?= .work/build/gem5

DOCKER_TAG ?= dadao-v5-dev:local

.DEFAULT_GOAL := help

.PHONY: help manifest-check doctor status fetch fetch-refs apply-series prepare \
        clean-work build-mc build-qemu build-gem5 docker-image docker-shell check \
        validate-vectors check-spec-refs check-spec-drift

# $(call component-enabled,<name>) exits 0 only when <name> is enabled in
# manifests/components.lock.toml. Build targets use it to refuse to pretend
# they built a component whose upstream commit is still pending.
component-enabled = $(PYTHON) -c "import tomllib,sys;m=tomllib.load(open('manifests/components.lock.toml','rb'));sys.exit(0 if any(c['name']=='$(1)' and c.get('enabled') for c in m.get('component',[])) else 1)"

help:
	@echo "DADAO-v5 orchestration"
	@echo ""
	@echo "  make help            Show this help"
	@echo "  make manifest-check  Validate specification/component/reference locks"
	@echo "  make doctor          Check host or container build prerequisites"
	@echo "  make status          Show locked components and references"
	@echo "  make fetch           Fetch enabled components at exact commits"
	@echo "  make fetch-refs      Fetch locked reference repositories"
	@echo "  make apply-series    Apply ordered patch series to fetched sources"
	@echo "  make prepare         Fetch enabled components and apply their patch series"
	@echo "  make build-mc        Build LLVM MC tools (requires llvm-project enabled)"
	@echo "  make build-qemu      Configure and compile QEMU (requires qemu enabled)"
	@echo "  make build-gem5      Build gem5 (stub; command owned by the gem5 module)"
	@echo "  make docker-image    Build the development image ($(DOCKER_TAG))"
	@echo "  make docker-shell    Open a shell in the development image"
	@echo "  make clean-work      Remove generated .work content only"
	@echo "  make validate-vectors  Validate tests/vectors schema/inventory/coverage"
	@echo "  make check           Run repository-level structural checks"
	@echo "  make check-spec-drift  Audit contract provenance against README versions"
	@echo "  make check-spec-refs Audit spec references in contract-*.md (standalone)"

manifest-check:
	@$(PYTHON) tools/infra/manifest_check.py

doctor:
	@$(PYTHON) tools/infra/doctor.py

status:
	@$(PYTHON) tools/infra/status.py

fetch: manifest-check
	@$(PYTHON) tools/infra/fetch.py

fetch-refs: manifest-check
	@$(PYTHON) tools/infra/fetch_refs.py

apply-series: manifest-check
	@$(PYTHON) tools/infra/apply_series.py

prepare: fetch apply-series

# DADAO is registered by adding it to LLVM_ALL_TARGETS in llvm/CMakeLists.txt
# (see ADR-0007).
build-mc: manifest-check
	@$(call component-enabled,llvm-project) || { \
	  echo "build-mc: component 'llvm-project' is not enabled / commit pending (manifests/components.lock.toml); refusing to fake success"; \
	  exit 1; \
	}
	cmake -G Ninja -B $(LLVM_BUILD) -S $(LLVM_SRC) \
	  -DLLVM_TARGETS_TO_BUILD=DADAO \
	  -DLLVM_ENABLE_PROJECTS="" \
	  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
	  -DLLVM_ENABLE_ASSERTIONS=ON
	ninja -C $(LLVM_BUILD) llvm-mc llvm-objdump llvm-objcopy llvm-readobj FileCheck not LLVMDADAOCodeGen
	@echo "build-mc: PASS"

build-qemu: manifest-check
	@$(call component-enabled,qemu) || { \
	  echo "build-qemu: component 'qemu' is not enabled / commit pending (manifests/components.lock.toml); refusing to fake success"; \
	  exit 1; \
	}
	mkdir -p $(QEMU_BUILD)
	cd $(QEMU_BUILD) && $(CURDIR)/$(QEMU_SRC)/configure \
	  --target-list=dadao-softmmu \
	  --enable-tcg \
	  --disable-werror
	$(MAKE) -C $(QEMU_BUILD) -j$$(nproc)
	@echo "build-qemu: PASS"

# gem5 is a v5 addition and has no build command yet (the gem5 module owns it).
# This target is a deliberate skeleton: even once the component is enabled it
# must not claim success until a real recipe exists.
build-gem5: manifest-check
	@$(call component-enabled,gem5) || { \
	  echo "build-gem5: component 'gem5' is not enabled / commit pending (manifests/components.lock.toml); refusing to fake success"; \
	  exit 1; \
	}
	@echo "build-gem5: gem5 build command is not defined yet (owned by the gem5 module); refusing to fake success"
	@exit 1

docker-image:
	docker build -t $(DOCKER_TAG) containers/dev

docker-shell:
	docker run --rm -it -v "$(PWD):/workspace" $(DOCKER_TAG) /bin/bash

clean-work:
	@$(PYTHON) tools/infra/clean_work.py

check: manifest-check validate-vectors check-spec-drift
	@$(PYTHON) tools/infra/check_issues.py
	@$(PYTHON) -m compileall -q tools
	@echo "repository checks: PASS"

# Vector schema/inventory/coverage gate (TESTCASES-002t). Requires the M1
# encoding table (contracts/opcodes.yaml) to exist.
validate-vectors: contracts/opcodes.yaml
	@$(PYTHON) tools/testcases/validate_vectors.py

# spec drift check (INFRA-012t): fail-closed provenance audit for contract-*.md.
check-spec-drift:
	@$(PYTHON) tools/infra/check_spec_drift.py

# spec 引用审计 (INFRA-011t): Check 1 引用有效性 + Check 2 无引用规范断言.
# Standalone target, not part of `make check`.
check-spec-refs:
	@$(PYTHON) tools/infra/check_spec_refs.py

# ---------------------------------------------------------------------------
# F1 phase entrypoints (INFRA-108t, ADR-1004 D6/D9).
#
# Everything above this line is the M1 baseline and is intentionally left
# byte-identical: the only Makefile change is the addition of the block below
# plus the separate .PHONY line, and `make check-m1-entrypoints` enforces that
# mechanically (the M1 part of the Makefile diff must contain no removed line).
#
# F1 never writes into .work/source or .work/build.  It has its own isolated
# source trees under .work/f1/source, its own build roots under .work/f1/build,
# and appends only 0009+ to the existing per-component series.  F1 is *not* part
# of `make check` or `make prepare`: a missing or half-built F1 must never change
# the meaning of the M1 entrypoints.
F1_WORK        ?= .work/f1
F1_SRC_RAW     ?= $(F1_WORK)/source
F1_BUILD_RAW   ?= $(F1_WORK)/build
F1_LOG_DIR     ?= .work/log/infra
F1_QEMU_SRC    ?= $(F1_SRC_RAW)/qemu
F1_QEMU_BUILD  ?= $(F1_BUILD_RAW)/qemu
F1_LLVM_SRC    ?= $(F1_SRC_RAW)/llvm-project/llvm
F1_LLVM_BUILD  ?= $(F1_BUILD_RAW)/llvm

.PHONY: f1-status f1-prepare f1-apply-series f1-make-patch f1-check \
        f1-build-mc f1-build-qemu f1-replay-check f1-baseline-snapshot \
        f1-baseline-check check-m1-entrypoints

f1-status:
	@$(PYTHON) tools/infra/f1_prepare.py --dry-run
	@$(PYTHON) tools/infra/f1_series.py --list

# Create .work/f1/source/{llvm-project,qemu} at the recorded M1 8-patch head.
# Idempotent: an existing F1 tree is verified and then left alone, never reset.
f1-prepare:
	@$(PYTHON) tools/infra/f1_prepare.py

# Apply the 0009+ series entries to the F1 trees.  Refuses an invalid series, a
# dirty tree, or a tree that does not contain the M1 head as an ancestor.
f1-apply-series:
	@$(PYTHON) tools/infra/f1_apply.py

# Append-only export of the F1 commits as 0009+ patches; refuses to overwrite any
# existing patch file and preserves the frozen M1 series prefix byte for byte.
f1-make-patch:
	@$(PYTHON) tools/infra/f1_make_patch.py
	@$(PYTHON) tools/infra/f1_prepare.py

# Isolation + series + F1/M1 separation gates (acceptance criteria 1 and 3).
f1-check:
	@$(PYTHON) tools/infra/f1_series.py
	@$(PYTHON) tools/infra/check_f1_isolation.py --require-m1 --require-idle

# Offline replay of 0001-0008 (+0009+) from the local bare mirror only.  The
# replay trees are throw-away and never live inside the repository.
F1_REPLAY_DIR ?= /tmp/opencode/INFRA-108t/f1-replay
f1-replay-check:
	@$(PYTHON) tools/infra/f1_replay_check.py --work-dir $(F1_REPLAY_DIR)

# F1 build entrypoints.  Serialised through <work>/f1/.build.lock with a
# concurrent-build probe, because this host's memory headroom is too small for
# two configure/build/link runs at once (INFRA-105t measured 45 MiB MemAvailable
# at the worst point).  The LLVM flags mirror `build-mc` and add the lld
# single-link-job settings the M1 build actually used.
f1-build-mc: manifest-check
	@$(call component-enabled,llvm-project) || { \
	  echo "f1-build-mc: component 'llvm-project' is not enabled / commit pending (manifests/components.lock.toml); refusing to fake success"; \
	  exit 1; \
	}
	$(PYTHON) tools/infra/f1_build_lock.py --label f1-build-mc \
	  --log $(F1_LOG_DIR)/INFRA-108t-f1-build-mc-serial.log -- \
	  cmake -G Ninja -B $(F1_LLVM_BUILD) -S $(F1_LLVM_SRC) \
	    -DLLVM_TARGETS_TO_BUILD=DADAO \
	    -DLLVM_ENABLE_PROJECTS="" \
	    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
	    -DLLVM_ENABLE_ASSERTIONS=ON \
	    -DLLVM_USE_LINKER=lld \
	    -DLLVM_PARALLEL_LINK_JOBS=1 -- \
	  ninja -C $(F1_LLVM_BUILD) llvm-mc llvm-objdump llvm-objcopy llvm-readobj FileCheck not LLVMDADAOCodeGen
	@echo "f1-build-mc: PASS"

f1-build-qemu: manifest-check
	@$(call component-enabled,qemu) || { \
	  echo "f1-build-qemu: component 'qemu' is not enabled / commit pending (manifests/components.lock.toml); refusing to fake success"; \
	  exit 1; \
	}
	$(PYTHON) tools/infra/f1_build_lock.py --label f1-build-qemu \
	  --log $(F1_LOG_DIR)/INFRA-108t-f1-build-qemu-serial.log -- \
	  sh -c 'mkdir -p $(F1_QEMU_BUILD) && cd $(F1_QEMU_BUILD) && \
	    $(CURDIR)/$(F1_QEMU_SRC)/configure --target-list=dadao-softmmu \
	      --enable-tcg --disable-werror --disable-download && \
	    $(MAKE) -C $(F1_QEMU_BUILD) -j$$(nproc)'
	@echo "f1-build-qemu: PASS"

# M1 baseline protection: snapshot before F1 work, compare after.
F1_BASELINE ?= $(F1_WORK)/m1-baseline.json
f1-baseline-snapshot:
	@$(PYTHON) tools/infra/check_f1_baseline.py snapshot --out $(F1_BASELINE)

f1-baseline-check:
	@$(PYTHON) tools/infra/check_f1_baseline.py compare --before $(F1_BASELINE)

# Proves the M1 entrypoints are semantically untouched: the Makefile diff may
# only add lines, and `make -n` must still expand the M1 recipes to exactly the
# recorded commands (acceptance criterion 4).
check-m1-entrypoints:
	@$(PYTHON) tools/infra/check_m1_entrypoints.py
