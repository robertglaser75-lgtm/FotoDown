# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""FotoDown Compatibility Wrapper.

FotoDown wurde in Vitrina umbenannt. Dieser Wrapper leitet Aufrufe
transparent an vitrina.py weiter.
"""

from __future__ import annotations

import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from vitrina import main

if __name__ == "__main__":
    main()
