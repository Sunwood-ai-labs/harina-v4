from __future__ import annotations

import os
import platform


if os.name == "nt":
    # Avoid Windows WMI calls inside platform.system(), which can stall aiohttp/discord imports
    # for minutes in this environment. The project only needs the coarse OS name here.
    platform.system = lambda: "Windows"
