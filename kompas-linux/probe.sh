#!/usr/bin/env bash
set -euxo pipefail

sudo apt-get update
sudo apt-get install -y wget ca-certificates gnupg xvfb xserver-xephyr openbox procps iproute2 unzip

wget -O /tmp/ascon-personal-deb.sh https://repo.ascon.ru/personal/scripts/ascon-personal-deb.sh
wget -O /tmp/ascon-stable-deb.sh https://repo.ascon.ru/scripts/ascon-stable-deb.sh

echo "=== PERSONAL REPO SCRIPT ==="
sed -n '1,160p' /tmp/ascon-personal-deb.sh
echo "=== STABLE REPO SCRIPT ==="
sed -n '1,160p' /tmp/ascon-stable-deb.sh

sudo bash /tmp/ascon-personal-deb.sh
sudo bash /tmp/ascon-stable-deb.sh
sudo apt-get update

apt-cache policy ascon-kompas-graphic-v25 ascon-kompas-study-v25 ascon-kompas-sdk-v25
sudo apt-get install -y ascon-kompas-graphic-v25 ascon-kompas-study-v25 ascon-kompas-sdk-v25

dpkg -l | grep -E 'ascon-kompas|ascon-help' || true
find /opt/ascon -maxdepth 4 \( -name ksapi.py -o -name kStudy -o -name 'kompas-study-v25' \) -print || true

Xvfb :99 -screen 0 1600x1000x24 > /tmp/xvfb.log 2>&1 &
sleep 2
DISPLAY=:99 Xephyr :5 -screen 1400x900 -ac > /tmp/xephyr.log 2>&1 &
sleep 2
DISPLAY=:5 openbox > /tmp/openbox.log 2>&1 &
sleep 2

unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
DISPLAY=:5 nohup kompas-study-v25 >/tmp/kompas.log 2>&1 &

set +e
for i in $(seq 1 75); do
  ss -ltnp | grep -E 'kStudy|kKompas|kHome' && break
  sleep 2
done
set -e

echo "=== PROCESSES ==="
ps aux | grep -E '[k]Study|[k]Kompas|[k]Home' || true
echo "=== SOCKETS ==="
ss -ltnp | grep -E 'kStudy|kKompas|kHome' || true
echo "=== KOMPAS LOG ==="
tail -200 /tmp/kompas.log || true

if ! ss -ltnp | grep -Eq 'kStudy|kKompas|kHome'; then
  echo "KOMPAS_API_SOCKET_NOT_FOUND"
  exit 12
fi

BIN=/opt/ascon/kompas3d-v25/Bin
cd "$BIN"
DISPLAY=:5 python3 - <<'PY'
import sys,time
sys.path.insert(0,'.')
import ksapi
app=None
for _ in range(30):
    app=ksapi.GetKompas()
    if app is not None:
        break
    time.sleep(2)
if app is None:
    raise SystemExit('GetKompas returned None')
print('APP_NAME='+str(app.GetApplicationName(True)))
print('DOCS='+str(app.GetDocuments().GetCount()))
PY
