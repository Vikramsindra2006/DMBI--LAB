#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Create an environment first: python3.12 -m venv .venv'
  echo 'Then install packages: .venv/bin/python -m pip install -r requirements.txt'
  exit 1
fi
exec .venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
