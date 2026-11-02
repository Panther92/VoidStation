#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Startet den Launcher. launcher.py wird importiert statt direkt ausgefuehrt, damit Python den fertigen
Bytecode aus __pycache__ nutzt: Ein direkt gestartetes Skript wird bei jedem Start neu uebersetzt."""
import launcher

launcher.main()
