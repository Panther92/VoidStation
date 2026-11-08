#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Startet den Launcher. launcher.py wird importiert statt direkt ausgefuehrt, damit Python den fertigen
Bytecode aus __pycache__ nutzt: Ein direkt gestartetes Skript wird bei jedem Start neu uebersetzt."""
import ctypes

try:
    ctypes.CDLL(None).mallopt(-8, 2)            # M_ARENA_MAX: gilt nur hier, nicht fuer gestartete Programme (rund 3 MB)
except (OSError, AttributeError):
    pass

import launcher  # noqa: E402

launcher.main()
