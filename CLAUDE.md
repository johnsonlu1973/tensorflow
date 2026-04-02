# CLAUDE.md — TensorFlow Codebase Guide

This file provides context for AI assistants (e.g., Claude Code) working in this repository.

---

## Repository Overview

This is the **TensorFlow 1.x** open-source machine learning framework developed by Google. It is a large, multi-language codebase (~4,000+ source files) supporting CPU, GPU, and mobile/embedded targets.

**Primary languages:** C++ (core runtime), Python (API and training), with bindings for Java and Go.

---

## Directory Structure

```
tensorflow/
├── WORKSPACE               # Bazel workspace definition (root of the build)
├── configure               # Interactive configuration script (run before first build)
├── BUILD                   # Top-level Bazel build file
├── tensorflow/             # All TensorFlow source code
│   ├── core/               # C++ runtime (kernels, ops, framework, graph engine)
│   │   ├── common_runtime/ # Session, executor, local device management
│   │   ├── distributed_runtime/ # gRPC-based distributed execution
│   │   ├── framework/      # Op/kernel registration, tensor, dtype, graph defs
│   │   ├── graph/          # Graph construction, optimization passes
│   │   ├── grappler/       # Graph optimization (constant folding, pruning, etc.)
│   │   ├── kernels/        # ~768 op kernel implementations (CPU + GPU)
│   │   ├── ops/            # Op definitions (registered via REGISTER_OP)
│   │   ├── platform/       # Platform abstraction (file I/O, threading, logging)
│   │   ├── lib/            # Low-level libraries (strings, hash, status, etc.)
│   │   ├── protobuf/       # Protocol buffer definitions
│   │   └── public/         # Public C++ session API
│   ├── python/             # Python API (~1,459 .py files)
│   │   ├── framework/      # Graph, ops, dtypes, device, sessions
│   │   ├── ops/            # Python wrappers for ops (array_ops, math_ops, etc.)
│   │   ├── training/       # Optimizers, gradient descent, checkpointing
│   │   ├── client/         # Python session client
│   │   ├── layers/         # High-level layer abstractions
│   │   ├── estimator/      # Estimator API for high-level model training
│   │   ├── saved_model/    # SavedModel format support
│   │   ├── debug/          # TensorFlow debugger (tfdbg)
│   │   ├── summary/        # TensorBoard summary operations
│   │   ├── tools/          # Python developer tools
│   │   └── util/           # Python utilities
│   ├── cc/                 # C++ client API
│   │   ├── client/         # C++ session client
│   │   ├── framework/      # Scope, gradient registration
│   │   ├── ops/            # C++ op wrappers (auto-generated)
│   │   └── training/       # C++ training utilities
│   ├── java/               # Java API bindings
│   ├── go/                 # Go API bindings
│   ├── contrib/            # 59 contributed/experimental packages
│   │   ├── cmake/          # CMake build support (primarily for Windows)
│   │   ├── makefile/       # GNU Make build for mobile/embedded targets
│   │   ├── layers/         # Contributed layer ops
│   │   ├── learn/          # High-level ML estimator API (legacy)
│   │   ├── slim/           # TF-Slim model library
│   │   ├── rnn/            # RNN/LSTM utilities
│   │   ├── distributions/  # Probability distributions
│   │   ├── tensorboard/    # Contributed TensorBoard features
│   │   └── ...             # Many other experimental packages
│   ├── stream_executor/    # GPU abstraction layer (CUDA/OpenCL)
│   ├── compiler/           # XLA ahead-of-time compiler
│   ├── tensorboard/        # TensorBoard visualization tool
│   ├── tools/              # Developer tools
│   │   ├── ci_build/       # CI/CD scripts, Docker configs, pylintrc
│   │   └── benchmark/      # Benchmarking utilities
│   ├── docs_src/           # Documentation source (Markdown, used for tensorflow.org)
│   ├── examples/           # End-to-end example programs
│   └── user_ops/           # Template for user-defined custom ops
├── third_party/            # Vendored external dependencies
│   ├── eigen3/             # Eigen linear algebra library
│   ├── gpus/               # GPU (CUDA/OpenCL) build rules
│   ├── mkl/                # Intel MKL build rules
│   └── ...                 # Other external deps (grpc, protobuf, etc.)
└── tools/                  # Top-level build tooling
    └── bazel.rc.template   # Template for Bazel configuration flags
```

---

## Build System

### Primary Build: Bazel

TensorFlow uses [Bazel](https://bazel.build/) as its primary build system. Requires **Bazel 0.4.2+**.

**First-time setup:**
```bash
# Run the interactive configure script to set Python path, GPU support, etc.
./configure
```
This generates `.bazelrc` with build settings (Python binary, CUDA paths, etc.).

**Common Bazel commands:**
```bash
# Build the Python package
bazel build -c opt //tensorflow/tools/pip_package:build_pip_package

# Run all CPU tests
bazel test //tensorflow/...

# Run a specific test target
bazel test //tensorflow/python/framework:ops_test

# Build with GPU (CUDA) support
bazel build -c opt --config=cuda //tensorflow/...

# Run tests with GPU
bazel test -c opt --config=cuda //tensorflow/...

# Build with MKL support
bazel build --config=mkl //tensorflow/...
```

**Bazel config flags** (set in `.bazelrc` after `./configure`):
- `--config=cuda` — enables CUDA/GPU support
- `--config=mkl` — enables Intel MKL optimizations
- `--config=sycl` — enables OpenCL/SYCL support
- `-c opt` — optimized build (default for tests)
- `-c dbg` — debug build

### Alternative Build: CMake (Windows)
```bash
# See tensorflow/contrib/cmake/README.md for full instructions
cmake ../tensorflow -DCMAKE_BUILD_TYPE=Release
```
CMake is primarily used for Windows builds. Linux/macOS should use Bazel.

### Alternative Build: Makefile (Mobile/Embedded)
```bash
# Download dependencies first
tensorflow/contrib/makefile/download_dependencies.sh

# Build for Linux
make -f tensorflow/contrib/makefile/Makefile
```
Used for iOS, Android, Raspberry Pi builds. Produces a static C++ library only (no Python bindings or GPU support).

---

## Testing

### Running Tests with Bazel
```bash
# Run all tests (CPU)
bazel test //tensorflow/...

# Run a specific test file
bazel test //tensorflow/python/ops:array_ops_test

# Run tests with verbose output
bazel test --test_output=streamed //tensorflow/python/framework:ops_test

# Exclude GPU/NCCL tests (for CPU-only machines)
bazel test //tensorflow/... -//tensorflow/contrib/nccl/...
```

### Running Python Tests Directly
Some Python tests can be run directly after building:
```bash
python tensorflow/python/framework/ops_test.py
```

### CI/CD
Tests run via Jenkins at [ci.tensorflow.org](https://ci.tensorflow.org) using Docker containers.

**Running CI builds locally:**
```bash
# CPU build + tests
tensorflow/tools/ci_build/ci_build.sh CPU bazel test //tensorflow/...

# GPU build + tests
tensorflow/tools/ci_build/ci_build.sh GPU bazel test -c opt --config=cuda //tensorflow/...

# Build pip package with GPU support
tensorflow/tools/ci_build/ci_build.sh GPU tensorflow/tools/ci_build/builds/pip.sh GPU -c opt --config=cuda

# Android example build
tensorflow/tools/ci_build/ci_build.sh ANDROID tensorflow/tools/ci_build/builds/android.sh

# Drop into Docker container shell
CI_DOCKER_EXTRA_PARAMS='-it --rm' tensorflow/tools/ci_build/ci_build.sh CPU /bin/bash
```

Docker images available: `CPU`, `GPU`, `ANDROID`, `CMAKE`, `HADOOP`, `TENSORBOARD`.

---

## Code Conventions

### Python Code Style

- **PEP 8** with Google Python Style Guide conventions.
- All Python files use `from __future__ import absolute_import, division, print_function` for Python 2/3 compatibility.
- Lint with **pylint** using the config at `tensorflow/tools/ci_build/pylintrc`.
- PEP 8 formatting checked via `tensorflow/tools/ci_build/pep8/`.
- Imports ordered: standard library → third-party (`six`, `numpy`) → TensorFlow internals (`tensorflow.core.*`, `tensorflow.python.*`).
- Disabled pylint checks: `design`, `similarities`, `no-self-use`, `attribute-defined-outside-init`, `import-error`, `no-member`, and others (see pylintrc).

**File header (required on all source files):**
```python
# Copyright 2015 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# ...
```

### C++ Code Style

- **Google C++ Style Guide**.
- Headers use `#ifndef TENSORFLOW_<PATH>_<FILE>_H_` include guards.
- All code in `namespace tensorflow { ... }`.
- Copyright header required on all files.
- Use `TF_DISALLOW_COPY_AND_ASSIGN` macro instead of `= delete` for copy constructors.
- Prefer `Status` return values over exceptions.

### Bazel BUILD Files

- Every directory with source files has a `BUILD` file.
- Use `tf_cc_test`, `tf_py_test`, `tf_kernel_library` macros from `tensorflow/tensorflow.bzl` instead of raw Bazel rules.
- Target visibility: most targets are `//tensorflow:internal`; public API targets are explicitly marked.
- Test files follow the naming convention: `<component>_test.cc` or `<component>_test.py`.

### Op and Kernel Registration

**C++ Op definition** (in `tensorflow/core/ops/`):
```cpp
REGISTER_OP("MyOp")
    .Input("input: float")
    .Output("output: float")
    .SetShapeFn(...)
    .Doc("...");
```

**C++ Kernel implementation** (in `tensorflow/core/kernels/`):
```cpp
REGISTER_KERNEL_BUILDER(Name("MyOp").Device(DEVICE_CPU), MyOpKernel);
```

**Python wrapper** (in `tensorflow/python/ops/`): Auto-generated via SWIG or manually wrapped using `gen_<module>_ops.py`.

---

## Key Architectural Concepts

### Graph Execution Model
TensorFlow 1.x uses a **define-then-run** model:
1. Build a computation graph using Python API (`tf.Graph`)
2. Execute the graph in a `tf.Session`
3. Data flows as `Tensor` objects along graph edges

### Tensor and Op Terminology
- **Op**: A node in the computation graph (defined in `core/ops/`)
- **Kernel**: The device-specific implementation of an Op (in `core/kernels/`)
- **Tensor**: The N-dimensional array flowing between ops
- **Variable**: A mutable tensor persisted across session runs

### Key Public Python API Modules
```
tensorflow.python.framework.ops        # Graph, Tensor, Operation classes
tensorflow.python.framework.dtypes     # tf.float32, tf.int64, etc.
tensorflow.python.ops.array_ops        # tf.reshape, tf.concat, etc.
tensorflow.python.ops.math_ops         # tf.matmul, tf.reduce_sum, etc.
tensorflow.python.ops.nn_ops           # tf.nn.relu, tf.nn.softmax, etc.
tensorflow.python.training             # Optimizers, gradient descent
tensorflow.python.client.session       # tf.Session
```

### contrib/ Packages
The `tensorflow/contrib/` directory contains **experimental and contributed code** that has not yet been integrated into core TensorFlow. It includes:
- `contrib.layers` — Higher-level layer building blocks
- `contrib.learn` — High-level Estimator API (predecessor to `tf.estimator`)
- `contrib.slim` — Lightweight model definition library
- `contrib.rnn` — Advanced RNN cells (LSTM, GRU variants)
- `contrib.distributions` — Probability distributions
- `contrib.bayesflow` — Bayesian inference tools

**Note**: `contrib` code may change APIs without deprecation warnings.

---

## Working With the Codebase

### Adding a New Op
1. Define the op in `tensorflow/core/ops/<category>_ops.cc` using `REGISTER_OP`.
2. Implement the kernel in `tensorflow/core/kernels/<name>_op.cc` using `REGISTER_KERNEL_BUILDER`.
3. Add the kernel to the BUILD file using `tf_kernel_library`.
4. Create Python wrapper in `tensorflow/python/ops/` (often auto-generated).
5. Write tests in `tensorflow/python/kernel_tests/`.

### Adding Python API
- Add to `tensorflow/python/ops/<category>_ops.py`
- Export via `tensorflow/python/framework/framework_lib.py` or the appropriate `__init__.py`
- Write tests with `unittest.TestCase` in the corresponding `*_test.py` file

### Modifying Protos
Protocol buffer definitions are in `tensorflow/core/framework/` and `tensorflow/core/protobuf/`. After changing a `.proto` file, Bazel regenerates the `.pb.h`/`_pb2.py` files automatically.

### Running Lint
```bash
# Python lint
pylint --rcfile=tensorflow/tools/ci_build/pylintrc <file.py>

# PEP8 check
tensorflow/tools/ci_build/pep8/run_pep8.sh
```

---

## Contribution Requirements

All contributors must sign a **Contributor License Agreement (CLA)**:
- Individual CLA: for personal contributions
- Corporate CLA: if contributing on behalf of an employer

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details.

---

## Platform Support

| Platform | Primary Build | Notes |
|----------|--------------|-------|
| Linux    | Bazel        | Fully supported (Ubuntu 14.04+) |
| macOS    | Bazel        | Fully supported |
| Windows  | CMake        | Limited op support, no custom ops |
| Android  | Makefile/Bazel | C++ static lib only |
| iOS      | Makefile     | C++ static lib only |
| Raspberry Pi | Makefile | C++ static lib only |

### GPU Requirements (CUDA)
- CUDA Toolkit 8.0
- cuDNN v5.1
- CUDA Compute Capability 3.0+ GPU
- `libcupti-dev` for profiling

---

## Useful Files for Navigation

| File | Purpose |
|------|---------|
| `tensorflow/tensorflow.bzl` | Central Bazel macros for TF build rules |
| `tensorflow/core/BUILD` | Core C++ library build targets (well-documented) |
| `tensorflow/python/framework/ops.py` | Graph, Tensor, Operation Python classes |
| `tensorflow/python/framework/dtypes.py` | TensorFlow dtype definitions |
| `tensorflow/tools/ci_build/pylintrc` | Python lint configuration |
| `tools/bazel.rc.template` | Template for Bazel flags |
| `WORKSPACE` | External dependency declarations |
| `configure` | Build configuration script |
