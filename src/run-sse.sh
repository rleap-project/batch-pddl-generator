#!/bin/bash

set -euo pipefail

if [[ $# != 3 ]]; then
    echo "usage: $(basename "$0") image domain_file problem_file" 1>&2
    exit 2
fi

SSE="$1"
DOMAIN="$2"
PROBLEM="$3"

export LANG=C

/usr/bin/time -o /dev/stdout -f "SSE runtime: %es real, %Us user, %Ss sys" \
  "$SSE" \
    --workspace /tmp/workspace \
    --domain "$DOMAIN" \
    --instance "$PROBLEM"
