#!/usr/bin/env bash
set -euxo pipefail
IMAGE=registry.astralinux.ru/library/astra/ubi18:latest

docker pull "$IMAGE"
docker rm -f kompas-astra 2>/dev/null || true
docker run --name kompas-astra --privileged --network host --shm-size=2g -d \
  -v "$GITHUB_WORKSPACE:/work" \
  "$IMAGE" sleep infinity

docker exec kompas-astra bash -lc '
  set -euxo pipefail
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y wget curl gnupg lsb-release procps iproute2 python3 unzip locales \
    xvfb xserver-xephyr openbox dbus-x11 x11-xkb-utils desktop-file-utils
  touch /etc/locale.gen
  grep -q "^ru_RU.CP1251 CP1251" /etc/locale.gen || echo "ru_RU.CP1251 CP1251" >> /etc/locale.gen
  locale-gen || true

  wget -qO /tmp/ascon-personal-deb.sh https://repo.ascon.ru/personal/scripts/ascon-personal-deb.sh
  wget -qO /tmp/ascon-stable-deb.sh https://repo.ascon.ru/scripts/ascon-stable-deb.sh
  bash /tmp/ascon-personal-deb.sh
  bash /tmp/ascon-stable-deb.sh
  apt-get update
  apt-get install -y ascon-kompas-graphic-v25 ascon-kompas-study-v25 ascon-kompas-sdk-v25

  echo "=== KOMPAS FILES ==="
  command -v kompas-study-v25 || true
  find /opt/ascon/kompas3d-v25 -maxdepth 3 \( -name kStudy -o -name ksapi.py -o -name constants.py \) -print
  dpkg -l | grep -E "ascon-kompas-(graphic|study|sdk)-v25"

  Xvfb :99 -screen 0 1600x1000x24 -ac >/tmp/xvfb.log 2>&1 &
  sleep 2
  DISPLAY=:99 Xephyr :5 -screen 1400x900 -ac >/tmp/xephyr.log 2>&1 &
  sleep 2
  DISPLAY=:5 openbox >/tmp/openbox.log 2>&1 &
  sleep 2

  unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
  eval "$(dbus-launch --sh-syntax)"
  export DISPLAY=:5
  nohup kompas-study-v25 >/tmp/kompas.log 2>&1 &
  echo $! >/tmp/kompas-launch.pid

  set +e
  for i in $(seq 1 90); do
    if ss -ltnp | grep -Eq "kStudy|kKompas|kHome"; then
      echo "KOMPAS API SOCKET FOUND"
      break
    fi
    sleep 2
  done
  set -e

  echo "=== PROCESSES ==="
  ps aux | grep -E "[k]Study|[k]Kompas|[k]Home" || true
  echo "=== SOCKETS ==="
  ss -ltnp | grep -E "kStudy|kKompas|kHome" || true
  echo "=== KOMPAS LOG ==="
  tail -200 /tmp/kompas.log || true

  ss -ltnp | grep -Eq "kStudy|kKompas|kHome"

  export KOMPAS_DIR=/opt/ascon/kompas3d-v25
  cd /work
  python3 kompas-linux/build_native.py

  test -s "kompas-linux/Работа_1_параметрическая.frw"
  unzip -t "kompas-linux/Работа_1_параметрическая.frw"
  sha256sum "kompas-linux/Работа_1_параметрическая.frw" | tee kompas-linux/sha256.txt
  cp /tmp/kompas.log kompas-linux/kompas.log || true
  cp /tmp/xvfb.log kompas-linux/xvfb.log || true
  cp /tmp/xephyr.log kompas-linux/xephyr.log || true
  cp /tmp/openbox.log kompas-linux/openbox.log || true
'
