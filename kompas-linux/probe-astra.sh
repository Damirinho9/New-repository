#!/usr/bin/env bash
set -euxo pipefail
IMAGE=registry.astralinux.ru/library/astra/ubi18:latest

docker pull "$IMAGE"
docker run --name kompas-astra --privileged --network host -d   -v "$GITHUB_WORKSPACE:/work"   "$IMAGE" sleep infinity

docker exec kompas-astra bash -lc '
  set -euxo pipefail
  apt-get update
  apt-get install -y wget curl gnupg lsb-release procps iproute2 python3 unzip
  echo "=== OS ==="
  cat /etc/os-release
  lsb_release -a || true
  wget -qO /tmp/ascon-personal-deb.sh https://repo.ascon.ru/personal/scripts/ascon-personal-deb.sh
  wget -qO /tmp/ascon-stable-deb.sh https://repo.ascon.ru/scripts/ascon-stable-deb.sh
  bash /tmp/ascon-personal-deb.sh
  bash /tmp/ascon-stable-deb.sh
  apt-get update
  echo "=== POLICY ==="
  apt-cache policy ascon-kompas-graphic-v25 ascon-kompas-study-v25 ascon-kompas-sdk-v25
  apt-get install -y ascon-kompas-graphic-v25 ascon-kompas-study-v25 ascon-kompas-sdk-v25
  echo "=== INSTALLED ==="
  dpkg -l | grep -E "ascon-kompas|ascon-help" || true
  find /opt/ascon/kompas3d-v25/Bin -maxdepth 1 -type f | head -50
'
