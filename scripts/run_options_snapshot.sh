#!/bin/bash
cd "$(dirname "$0")" && python3 deribit_options.py >> ../logs/options_snapshot.log 2>&1
