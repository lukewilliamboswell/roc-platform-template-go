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
CHOST_DIR := chost
PLATFORM_DIR := platform
TARGET_PATH := $(PLATFORM_DIR)/targets/$(TARGET_DIR)

# Output files
GO_ARCHIVE := $(HOST_DIR)/libgo.a
GO_HEADER := $(HOST_DIR)/libgo.h
HOST_OBJ := $(CHOST_DIR)/roc_host.o
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

# Build Go code as C-archive
$(GO_ARCHIVE): $(HOST_DIR)/host.go
	cd $(HOST_DIR) && CGO_ENABLED=1 go build -buildmode=c-archive -o libgo.a .

# Compile roc_host.c with Go header
$(HOST_OBJ): $(CHOST_DIR)/roc_host.c $(CHOST_DIR)/roc_abi.h $(GO_ARCHIVE)
	$(CC) -c $(CHOST_DIR)/roc_host.c -o $(HOST_OBJ) -I$(CHOST_DIR) -I$(HOST_DIR) -fno-stack-protector

# Create final library by combining C and Go objects
$(FINAL_LIB): $(TARGET_PATH) $(HOST_OBJ) $(GO_ARCHIVE)
	# Extract Go archive objects
	mkdir -p $(HOST_DIR)/tmp_objs
	cd $(HOST_DIR)/tmp_objs && $(AR) x ../libgo.a
	# Create final archive with all objects
	$(AR) rcs $(FINAL_LIB) $(HOST_OBJ) $(HOST_DIR)/tmp_objs/*.o
	rm -rf $(HOST_DIR)/tmp_objs
	# Copy to platform root for convenience
	cp $(FINAL_LIB) $(PLATFORM_DIR)/$(LIB_NAME)

native: build

clean:
	rm -f $(HOST_OBJ)
	rm -f $(GO_ARCHIVE) $(GO_HEADER)
	rm -f $(PLATFORM_DIR)/libhost.a $(PLATFORM_DIR)/host.lib
	rm -f $(TARGET_PATH)/$(LIB_NAME)
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
