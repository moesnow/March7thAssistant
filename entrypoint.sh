#!/bin/sh
set -e

if [ "$(uname -m)" = "aarch64" ]; then
  export MARCH7TH_BROWSER_TYPE=chromium
  export MARCH7TH_BROWSER_PATH=/usr/bin/chromium
  export MARCH7TH_DRIVER_PATH=/usr/bin/chromedriver
fi

exec "$@"
