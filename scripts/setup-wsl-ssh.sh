#!/usr/bin/env bash
# Symlink Windows SSH keys into WSL if running under WSL and ~/.ssh is missing.
set -euo pipefail

if ! grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Not running in WSL, skipping"
    exit 0
fi

WIN_USER=$(cmd.exe /C "echo %USERNAME%" 2>/dev/null | tr -d '\r')
WIN_SSH="/mnt/c/Users/$WIN_USER/.ssh"

if [ -d "$HOME/.ssh" ]; then
    echo "$HOME/.ssh already exists"
elif [ -d "$WIN_SSH" ]; then
    ln -s "$WIN_SSH" "$HOME/.ssh"
    echo "Linked $WIN_SSH -> $HOME/.ssh"
else
    echo "Windows SSH keys not found at $WIN_SSH"
fi
