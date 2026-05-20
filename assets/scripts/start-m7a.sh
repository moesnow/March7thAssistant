#!/bin/bash
termux-wake-lock
cd ~/march7thassistant
proot-distro run march7thassistant \
  --bind config.yaml:/m7a/config.yaml \
  --bind logs:/m7a/logs \
  --bind 3rdparty/WebBrowser/UserProfile:/m7a/3rdparty/WebBrowser/UserProfile \
  --env MARCH7TH_AFTER_FINISH=Exit \
  --env MARCH7TH_LOG_LEVEL=DEBUG
# -- python main.py daily
