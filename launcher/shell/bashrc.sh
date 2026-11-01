#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# (wird nur eingelesen, nicht ausgefuehrt – die erste Zeile ist fuer shellcheck)
# VoidStation: Komfort im Terminal – liegt als /etc/bash/bashrc.d/voidstation.sh und gilt fuer jede
# interaktive bash (Terminal-Kachel, SSH, sudo -i). Eigene Einstellungen in ~/.bashrc werden danach gelesen
# und gehen vor (eigenes PS1, eigene Aliase, eigene bind-Zeilen).
# Tab-Vervollstaendigung kommt aus dem Paket bash-completion (eigene Datei in /etc/bash/bashrc.d).

[ -n "${BASH_VERSION:-}" ] || return 0
case $- in *i*) ;; *) return 0 ;; esac
[ -z "${__VS_BASHRC:-}" ] || return 0              # nur einmal je Shell (Login-Shells lesen bashrc ueber profile.d)
__VS_BASHRC=1

# --- Verlauf: gross, ohne Doppelte, sofort gespeichert; mehrere Terminals ueberschreiben sich nicht
HISTSIZE=10000
HISTFILESIZE=20000
HISTCONTROL=ignoreboth:erasedups
HISTIGNORE='ls:ll:la:cd:pwd:exit:clear:history'
shopt -s histappend checkwinsize cmdhist

# --- Eingabe: ↑/↓ suchen im Verlauf nach dem schon Getippten (leere Zeile: wie bisher Zeile fuer Zeile),
#     Tab zeigt bei mehreren Treffern gleich die Liste, Gross-/Kleinschreibung egal, Treffer farbig
bind '"\e[A": history-search-backward' 2>/dev/null
bind '"\e[B": history-search-forward' 2>/dev/null
bind '"\eOA": history-search-backward' 2>/dev/null
bind '"\eOB": history-search-forward' 2>/dev/null
bind 'set show-all-if-ambiguous on' 2>/dev/null
bind 'set completion-ignore-case on' 2>/dev/null
bind 'set colored-stats on' 2>/dev/null
bind 'set colored-completion-prefix on' 2>/dev/null
bind 'set mark-symlinked-directories on' 2>/dev/null

# --- Farben und Kuerzel
alias ls='ls --color=auto'
alias ll='ls -lh --group-directories-first'
alias la='ls -lAh --group-directories-first'
alias grep='grep --color=auto'
alias diff='diff --color=auto'
alias ip='ip -color=auto'
alias ..='cd ..'
alias ...='cd ../..'

# --- Eingabeaufforderung: benutzer@rechner in Cyan (im VoidStation-Terminal Petrol), als root in Rot,
#     Ordner in Blau; nach einem Fehler steht der Rueckgabewert rot davor, z. B. "paul@Wohnzimmer ~ 127 $".
#     Wer in ~/.bashrc ein eigenes PS1 setzt, behaelt es: neu gebaut wird nur, solange PS1 noch von hier stammt.
__vs_ps1() {
  local who='\[\e[1;36m\]' err=''
  [ "$EUID" = 0 ] && who='\[\e[1;31m\]'
  [ "${1:-0}" != 0 ] && err="\[\e[31m\]$1\[\e[0m\] "
  __VS_PS1="${who}\u@\h\[\e[0m\] \[\e[1;34m\]\w\[\e[0m\] ${err}\\\$ "
  PS1="$__VS_PS1"
}
__vs_prompt() {
  local rc=$?
  history -a
  [ "$PS1" = "${__VS_PS1:-}" ] && __vs_ps1 "$rc"
  return "$rc"
}
__vs_ps1 0
case ";${PROMPT_COMMAND:-};" in
  *";__vs_prompt;"*) ;;
  *) PROMPT_COMMAND="__vs_prompt${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;;
esac

# --- vsctl: Befehle und Kachel-IDs vervollstaendigen (vsctl launch <Tab>)
_vsctl() {
  local cur=${COMP_WORDS[COMP_CWORD]} ids
  COMPREPLY=()
  if [ "$COMP_CWORD" = 1 ]; then
    mapfile -t COMPREPLY < <(compgen -W "home launch status update version channel help" -- "$cur")
  elif [ "$COMP_CWORD" = 2 ] && [ "${COMP_WORDS[1]}" = channel ]; then
    mapfile -t COMPREPLY < <(compgen -W "stable testing" -- "$cur")
  elif [ "$COMP_CWORD" = 2 ] && [ "${COMP_WORDS[1]}" = launch ]; then
    ids="$(sed -n 's/^ *"id": *"\([^"]*\)".*/\1/p' "$HOME/.local/share/voidstation/tiles.json" 2>/dev/null)"
    mapfile -t COMPREPLY < <(compgen -W "$ids" -- "$cur")
  fi
}
complete -F _vsctl vsctl
