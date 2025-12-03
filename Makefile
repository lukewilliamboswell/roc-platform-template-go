# Makefile for building the Go Roc platform host

# Detect OS and architecture
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

# Determine target directory name
ifeq ($(UNAME_S),Darwin)
    ifeq ($(UNAME_M),arm64)
        TARGET_DIR := arm64mac
    else
        TARGET_DIR := x64mac
    endif
    LIB_NAME := libhost.a
else ifeq ($(UNAME_S),Linux)
    ifeq ($(UNAME_M),aarch64)
        TARGET_DIR := arm64glibc
    else
        TARGET_DIR := x64glibc
    endif
    LIB_NAME := libhost.a
else
    # Windows
    ifeq ($(UNAME_M),arm64)
        TARGET_DIR := arm64win
    else
        TARGET_DIR := x64win
    endif
    LIB_NAME := host.lib
endif

# Paths
HOST_DIR := host
PLATFORM_DIR := platform
TARGET_PATH := $(PLATFORM_DIR)/targets/$(TARGET_DIR)

# Output files
HOST_OBJ := $(HOST_DIR)/roc_host.o
FINAL_LIB := $(TARGET_PATH)/$(LIB_NAME)

# Compiler
CC := cc
AR := ar

.PHONY: all clean build native info test run-hello run-echo run-exit run-fizzbuzz run-stderr run-match run-sum run-tests

all: build

# Build the host library
build: $(FINAL_LIB)
	@echo "Built $(FINAL_LIB)"

# Create target directory
$(TARGET_PATH):
	mkdir -p $(TARGET_PATH)

# Compile roc_host.c (pure C, no Go)
$(HOST_OBJ): $(HOST_DIR)/roc_host.c $(HOST_DIR)/roc_abi.h
	$(CC) -c $(HOST_DIR)/roc_host.c -o $(HOST_OBJ) -I$(HOST_DIR) -fno-stack-protector

# Create library from just the C object
$(FINAL_LIB): $(TARGET_PATH) $(HOST_OBJ)
	$(AR) rcs $(FINAL_LIB) $(HOST_OBJ)
	# Copy to platform root for convenience
	cp $(FINAL_LIB) $(PLATFORM_DIR)/$(LIB_NAME)

native: build

clean:
	rm -f $(HOST_OBJ)
	rm -f $(PLATFORM_DIR)/libhost.a $(PLATFORM_DIR)/host.lib
	rm -f $(TARGET_PATH)/$(LIB_NAME)
	rm -f $(HOST_DIR)/libgo.a $(HOST_DIR)/libgo.h
	rm -rf $(HOST_DIR)/tmp_objs

# Run examples
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

# Run all tests (used by CI)
test: build
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

info:
	@echo "OS: $(UNAME_S)"
	@echo "Arch: $(UNAME_M)"
	@echo "Target: $(TARGET_DIR)"
	@echo "Library: $(LIB_NAME)"
