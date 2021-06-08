#! /bin/bash

set -euo pipefail

EXPDIR="$1"

grep -l "Found plan file" "$EXPDIR"/runs-00001-00100/00004/smac-*/run_*/plan/*/*/run.log | xargs grep "Singularity runtime" | sort -n -k3
