#!/bin/sh
set -e

if [ "$MARCH7TH_MODE" != "api" ] && [ ! -s /m7a/config.yaml ]; then
  cp /m7a/assets/config/config.example.yaml /m7a/config.yaml
fi

if [ "$(uname -m)" = "aarch64" ]; then
  export MARCH7TH_BROWSER_TYPE=chromium
  export MARCH7TH_BROWSER_PATH=/usr/bin/chromium
  export MARCH7TH_DRIVER_PATH=/usr/bin/chromedriver
fi

exec "$@"
