# Makefile for building the Go Roc platform host
# Supports native builds and cross-compilation via zig cc

# ============================================================================
# Platform Detection
# ============================================================================

UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

# Determine native target
ifeq ($(UNAME_S),Darwin)
    ifeq ($(UNAME_M),arm64)
        NATIVE_TARGET := arm64mac
    else
        NATIVE_TARGET := x64mac
    endif
else ifeq ($(UNAME_S),Linux)
    ifeq ($(UNAME_M),aarch64)
        # Check for musl vs glibc
        ifeq ($(shell ldd --version 2>&1 | grep -c musl),1)
            NATIVE_TARGET := arm64musl
        else
            NATIVE_TARGET := arm64glibc
        endif
    else
        ifeq ($(shell ldd --version 2>&1 | grep -c musl),1)
            NATIVE_TARGET := x64musl
        else
            NATIVE_TARGET := x64glibc
        endif
    endif
else
    # Windows
    ifeq ($(UNAME_M),arm64)
        NATIVE_TARGET := arm64win
    else
        NATIVE_TARGET := x64win
    endif
endif

# ============================================================================
# All Supported Targets
# ============================================================================

ALL_TARGETS := arm64mac x64mac arm64glibc x64glibc arm64musl x64musl arm64win x64win

# Target to Zig triple mapping
ZIG_TARGET_arm64mac   := aarch64-macos
ZIG_TARGET_x64mac     := x86_64-macos
ZIG_TARGET_arm64glibc := aarch64-linux-gnu
ZIG_TARGET_x64glibc   := x86_64-linux-gnu
ZIG_TARGET_arm64musl  := aarch64-linux-musl
ZIG_TARGET_x64musl    := x86_64-linux-musl
ZIG_TARGET_arm64win   := aarch64-windows-gnu
ZIG_TARGET_x64win     := x86_64-windows-gnu

# Target to Go OS mapping
GOOS_arm64mac   := darwin
GOOS_x64mac     := darwin
GOOS_arm64glibc := linux
GOOS_x64glibc   := linux
GOOS_arm64musl  := linux
GOOS_x64musl    := linux
GOOS_arm64win   := windows
GOOS_x64win     := windows

# Target to Go arch mapping
GOARCH_arm64mac   := arm64
GOARCH_x64mac     := amd64
GOARCH_arm64glibc := arm64
GOARCH_x64glibc   := amd64
GOARCH_arm64musl  := arm64
GOARCH_x64musl    := amd64
GOARCH_arm64win   := arm64
GOARCH_x64win     := amd64

# Library name per target
LIB_NAME_arm64mac   := libhost.a
LIB_NAME_x64mac     := libhost.a
LIB_NAME_arm64glibc := libhost.a
LIB_NAME_x64glibc   := libhost.a
LIB_NAME_arm64musl  := libhost.a
LIB_NAME_x64musl    := libhost.a
LIB_NAME_arm64win   := host.lib
LIB_NAME_x64win     := host.lib

# ============================================================================
# Paths
# ============================================================================

HOST_DIR := host
CHOST_DIR := chost
PLATFORM_DIR := platform
TARGETS_DIR := $(PLATFORM_DIR)/targets

# ============================================================================
# Tools
# ============================================================================

AR := ar
ZIG := zig

# ============================================================================
# Phony Targets
# ============================================================================

.PHONY: all build native clean info test bundle
.PHONY: all-targets $(ALL_TARGETS)
.PHONY: run-hello run-echo run-exit run-fizzbuzz run-stderr run-match run-sum run-tests

# ============================================================================
# Default Target - Native Build
# ============================================================================

all: build

build: native

native: $(TARGETS_DIR)/$(NATIVE_TARGET)/$(LIB_NAME_$(NATIVE_TARGET))
	@echo "Built $(TARGETS_DIR)/$(NATIVE_TARGET)/$(LIB_NAME_$(NATIVE_TARGET))"
	cp $(TARGETS_DIR)/$(NATIVE_TARGET)/$(LIB_NAME_$(NATIVE_TARGET)) $(PLATFORM_DIR)/libhost.a

# ============================================================================
# Cross-Compilation Targets
# ============================================================================

all-targets: $(ALL_TARGETS)
	@echo "Built all targets"

# Cross-compile targets (excludes native target to avoid duplicate rules)
CROSS_TARGETS := $(filter-out $(NATIVE_TARGET),$(ALL_TARGETS))

# Generate rules for cross-compile targets only
define TARGET_RULES

$(1): $(TARGETS_DIR)/$(1)/$(LIB_NAME_$(1))
	@echo "Built $(1)"

$(TARGETS_DIR)/$(1)/$(LIB_NAME_$(1)): $(HOST_DIR)/host.go $(CHOST_DIR)/roc_host.c $(CHOST_DIR)/roc_abi.h
	@mkdir -p $(TARGETS_DIR)/$(1)
	@mkdir -p $(HOST_DIR)/tmp_$(1)
	@echo "Building $(1)..."
	# Build Go as c-archive with zig cc
	cd $(HOST_DIR) && \
		CGO_ENABLED=1 \
		GOOS=$(GOOS_$(1)) \
		GOARCH=$(GOARCH_$(1)) \
		CC="$(ZIG) cc -target $(ZIG_TARGET_$(1))" \
		go build -buildmode=c-archive -o tmp_$(1)/libgo.a .
	# Compile C code with zig cc
	# -fno-stack-protector: See native build comment for rationale
	$(ZIG) cc -c $(CHOST_DIR)/roc_host.c \
		-o $(HOST_DIR)/tmp_$(1)/roc_host.o \
		-I$(CHOST_DIR) -I$(HOST_DIR)/tmp_$(1) \
		-target $(ZIG_TARGET_$(1)) \
		-fno-stack-protector
	# Extract Go archive and combine
	cd $(HOST_DIR)/tmp_$(1) && $(ZIG) ar x libgo.a
	$(ZIG) ar rcs $(TARGETS_DIR)/$(1)/$(LIB_NAME_$(1)) \
		$(HOST_DIR)/tmp_$(1)/roc_host.o \
		$(HOST_DIR)/tmp_$(1)/*.o
	rm -rf $(HOST_DIR)/tmp_$(1)

endef

# Apply rules for cross-compile targets (not native)
$(foreach target,$(CROSS_TARGETS),$(eval $(call TARGET_RULES,$(target))))

# Native target uses system cc (defined below)

# ============================================================================
# Native Build (faster, uses system cc)
# ============================================================================

# Alias for native target by name (e.g., "make arm64mac" on arm64 mac)
$(NATIVE_TARGET): native

# For native builds, use system compiler (faster than zig)
$(TARGETS_DIR)/$(NATIVE_TARGET)/$(LIB_NAME_$(NATIVE_TARGET)): $(HOST_DIR)/host.go $(CHOST_DIR)/roc_host.c $(CHOST_DIR)/roc_abi.h
	@mkdir -p $(TARGETS_DIR)/$(NATIVE_TARGET)
	@mkdir -p $(HOST_DIR)/tmp_native
	# Build Go as c-archive
	cd $(HOST_DIR) && CGO_ENABLED=1 go build -buildmode=c-archive -o tmp_native/libgo.a .
	# Compile C code
	# -fno-stack-protector: Disabled because Go manages its own stack and
	# stack protector can conflict when linking Go c-archive with C code.
	# This is safe because the final Roc executable handles its own security.
	cc -c $(CHOST_DIR)/roc_host.c \
		-o $(HOST_DIR)/tmp_native/roc_host.o \
		-I$(CHOST_DIR) -I$(HOST_DIR)/tmp_native \
		-fno-stack-protector
	# Extract Go archive and combine
	cd $(HOST_DIR)/tmp_native && $(AR) x libgo.a
	$(AR) rcs $(TARGETS_DIR)/$(NATIVE_TARGET)/$(LIB_NAME_$(NATIVE_TARGET)) \
		$(HOST_DIR)/tmp_native/roc_host.o \
		$(HOST_DIR)/tmp_native/*.o
	rm -rf $(HOST_DIR)/tmp_native

# ============================================================================
# Clean
# ============================================================================

clean:
	rm -rf $(HOST_DIR)/tmp_*
	rm -f $(HOST_DIR)/libgo.a $(HOST_DIR)/libgo.h
	rm -f $(PLATFORM_DIR)/libhost.a $(PLATFORM_DIR)/host.lib
	rm -rf $(TARGETS_DIR)

# ============================================================================
# Bundle Platform
# ============================================================================

# Bundle platform for distribution (requires all targets to be built first)
bundle:
	@echo "Bundling platform..."
	@cd $(PLATFORM_DIR) && roc bundle \
		$$(ls *.roc) \
		$$(ls targets/*/*.a targets/*/*.lib 2>/dev/null || true) \
		--output-dir ..

# ============================================================================
# Run Examples
# ============================================================================

run-hello:
	roc --no-cache examples/hello-world.roc

run-echo:
	roc --no-cache examples/echo.roc

run-exit:
	roc --no-cache examples/exit.roc

run-fizzbuzz:
	roc --no-cache examples/fizzbuzz.roc

run-stderr:
	roc --no-cache examples/stderr.roc

run-match:
	roc --no-cache examples/match.roc

run-sum:
	roc --no-cache examples/sum_fold.roc

run-tests:
	roc test examples/tests.roc

# ============================================================================
# Tests
# ============================================================================

test: native
	@echo "Running Go tests..."
	cd rocstd && go test ./...
	@echo ""
	@echo "Running all examples..."
	roc --no-cache examples/hello-world.roc
	roc --no-cache examples/fizzbuzz.roc
	roc --no-cache examples/match.roc
	roc --no-cache examples/stderr.roc
	roc --no-cache examples/sum_fold.roc
	-roc --no-cache examples/exit.roc
	@echo ""
	@echo "Running roc test..."
	roc test examples/tests.roc
	@echo ""
	@echo "All tests passed!"

# ============================================================================
# Info
# ============================================================================

info:
	@echo "Native target: $(NATIVE_TARGET)"
	@echo "All targets: $(ALL_TARGETS)"
	@echo ""
	@echo "Usage:"
	@echo "  make              - Build for native platform"
	@echo "  make native       - Build for native platform"
	@echo "  make all-targets  - Build for all platforms (requires zig)"
	@echo "  make bundle       - Bundle platform for distribution"
	@echo "  make <target>     - Build for specific target"
	@echo ""
	@echo "Available targets:"
	@echo "  arm64mac    - macOS ARM64"
	@echo "  x64mac      - macOS x86_64"
	@echo "  arm64glibc  - Linux ARM64 (glibc)"
	@echo "  x64glibc    - Linux x86_64 (glibc)"
	@echo "  arm64musl   - Linux ARM64 (musl)"
	@echo "  x64musl     - Linux x86_64 (musl)"
	@echo "  arm64win    - Windows ARM64"
	@echo "  x64win      - Windows x86_64"
