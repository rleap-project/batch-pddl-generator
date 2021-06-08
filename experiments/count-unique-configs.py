#! /usr/bin/env python3

from collections import defaultdict
from pathlib import Path
import sys


DIR = Path(sys.argv[1])

counter = defaultdict(int)
for path in DIR.iterdir():
    name = "-".join(str(path.name).split("-")[:-1])
    if name:
        counter[name] += 1

for name, count in sorted(counter.items(), key=lambda x: x[1]):
    print(f"{name}: {count}")
