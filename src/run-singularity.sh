#!/bin/bash

set -euo pipefail

if [[ $# != 4 ]]; then
    echo "usage: $(basename "$0") image domain_file problem_file plan_file" 1>&2
    exit 2
fi

if [ -f $PWD/$4 ]; then
    echo "Error: remove $PWD/$4" 1>&2
    exit 2
fi

# Ensure that the strings "CPU time limit exceeded" and "Killed" are in English.
export LANG=C

set +e
# Ignore some "expected" stderr output.
/usr/bin/time -o /dev/stdout -f "Singularity runtime: %es real, %Us user, %Ss sys" \
  singularity run -C -H "$PWD" "$1" "$PWD/$2" "$PWD/$3" "$4" 2> \
  >(grep -v "CPU time limit exceeded\|WARNING: will ignore action costs\|differs from the one in the portfolio file" >&2)
set -e

printf "\nRun VAL\n\n"

if [ -f $PWD/$4 ]; then
    echo "Found plan file."
    validate "$PWD/$2" "$PWD/$3" "$PWD/$4"
    exit 0
else
    echo "No plan file."
    validate "$PWD/$2" "$PWD/$3"
    exit 99
fi
