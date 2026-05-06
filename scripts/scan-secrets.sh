#!/usr/bin/env bash

set -euo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  printf '%s\n' "gitleaks is not installed."
  printf '%s\n' "Install: https://github.com/gitleaks/gitleaks"
  printf '%s\n' "Then run: gitleaks detect --source . --no-git"
  exit 1
fi

gitleaks detect --source . --no-git
