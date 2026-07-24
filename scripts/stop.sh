#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
source "$(dirname "$0")/_common.sh"
COFER_ALL_CLIENTS=1
export COFER_ALL_CLIENTS
compose down
