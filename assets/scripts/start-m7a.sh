#!/bin/bash
termux-wake-lock
cd ~/march7thassistant
if [[ -f config.yaml && ! -f userdata/config.yaml ]]; then
  mounts=(--bind config.yaml:/m7a/config.yaml --bind logs:/m7a/logs
          --bind 3rdparty/WebBrowser/UserProfile:/m7a/3rdparty/WebBrowser/UserProfile)
else
  mkdir -p userdata
  mounts=(--bind userdata:/m7a/userdata)
fi
proot-distro run march7thassistant "${mounts[@]}" \
  --env MARCH7TH_AFTER_FINISH=Exit \
  --env MARCH7TH_LOG_LEVEL=DEBUG
# -- python main.py daily
