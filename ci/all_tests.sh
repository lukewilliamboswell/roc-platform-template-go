#!/usr/bin/env bash
set -euo pipefail

# Build roc from source if not available
if ! command -v roc &> /dev/null; then
  if [ ! -d "roc-src" ]; then
    echo "Building roc from pinned commit..."
    ROC_COMMIT=$(python3 ci/get_roc_commit.py)

    git init roc-src
    cd roc-src
    git remote add origin https://github.com/roc-lang/roc
    git fetch --depth 1 origin "$ROC_COMMIT"
    git checkout --detach "$ROC_COMMIT"

    zig build roc

    cd ..
  fi

  # Add roc to PATH
  export PATH="$(pwd)/roc-src/zig-out/bin:$PATH"
fi

echo "Using roc: $(which roc)"
roc version

echo ""
echo "Building host library..."
make clean
make build

echo ""
echo "Running Go tests..."
cd rocstd && go test ./... && cd ..

echo ""
echo "Checking examples..."
for example in examples/*.roc; do
  echo "Running: roc check $example"
  roc check "$example" --no-cache
done

echo ""
echo "Running examples..."

# Examples that don't require stdin
examples_to_run=("hello-world" "fizzbuzz" "match" "stderr" "sum_fold" "exit")
for example in "${examples_to_run[@]}"; do
  echo ""
  echo "Running: $example"
  # exit.roc returns non-zero, so we handle that
  if [ "$example" = "exit" ]; then
    roc --no-cache "./examples/$example.roc" || true
  else
    roc --no-cache "./examples/$example.roc"
  fi
done

echo ""
echo "Running roc test..."
roc test examples/tests.roc

echo ""
echo "All tests passed!"
