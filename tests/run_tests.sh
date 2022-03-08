#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

IWHO_TEST="${SCRIPT_DIR}/../lib/iwho/tests/test_iwho.py"

set -ex

pytest ${SCRIPT_DIR} ${IWHO_TEST}
