#!/usr/bin/env bash
set -euxo pipefail
IMAGE=registry.astralinux.ru/library/astra/ubi18:latest

docker pull "$IMAGE"
docker rm -f kompas-astra 2>/dev/null || true
docker run --name kompas-astra --privileged --network host --shm-size=2g -d   -v "$GITHUB_WORKSPACE:/work" "$IMAGE" sleep infinity

docker exec kompas-astra bash -lc '
  set -euxo pipefail
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y wget curl gnupg lsb-release procps iproute2 python3 unzip locales     xvfb xserver-xephyr openbox dbus-x11 x11-xkb-utils desktop-file-utils scrot
  touch /etc/locale.gen
  grep -q "^ru_RU.CP1251 CP1251" /etc/locale.gen || echo "ru_RU.CP1251 CP1251" >> /etc/locale.gen
  locale-gen || true

  wget -qO /tmp/ascon-personal-deb.sh https://repo.ascon.ru/personal/scripts/ascon-personal-deb.sh
  wget -qO /tmp/ascon-stable-deb.sh https://repo.ascon.ru/scripts/ascon-stable-deb.sh
  bash /tmp/ascon-personal-deb.sh
  bash /tmp/ascon-stable-deb.sh
  apt-get update
  apt-get install -y ascon-kompas-graphic-v25 ascon-kompas-study-v25 ascon-kompas-sdk-v25

  mkdir -p /work/kompas-diagnostic
  echo "=== PACKAGE STATUS ===" | tee /work/kompas-diagnostic/install.txt
  dpkg -l | grep -E "ascon-kompas-(graphic|study|sdk)-v25" | tee -a /work/kompas-diagnostic/install.txt
  command -v kompas-study-v25 | tee -a /work/kompas-diagnostic/install.txt
  find /opt/ascon/kompas3d-v25/Bin -maxdepth 1 -type f -printf "%f\n" | sort | head -100 >> /work/kompas-diagnostic/install.txt

  echo "=== API signatures ===" > /work/kompas-diagnostic/api-signatures.txt
  grep -n -A140 "^class IApplication" /opt/ascon/kompas3d-v25/Bin/ksapi.py | head -180 >> /work/kompas-diagnostic/api-signatures.txt || true
  grep -n -A120 "^class IParametriticConstraint" /opt/ascon/kompas3d-v25/Bin/ksapi.py >> /work/kompas-diagnostic/api-signatures.txt || true
  grep -n -A120 "^class IDrawingObject1" /opt/ascon/kompas3d-v25/Bin/ksapi.py >> /work/kompas-diagnostic/api-signatures.txt || true
  grep -n -A100 "^class IKompasDocument2D1" /opt/ascon/kompas3d-v25/Bin/ksapi.py >> /work/kompas-diagnostic/api-signatures.txt || true

  Xvfb :99 -screen 0 1600x1000x24 -ac >/tmp/xvfb.log 2>&1 &
  sleep 2
  DISPLAY=:99 Xephyr :5 -screen 1400x900 -ac >/tmp/xephyr.log 2>&1 &
  sleep 2
  DISPLAY=:5 openbox >/tmp/openbox.log 2>&1 &
  sleep 2

  unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
  eval "$(dbus-launch --sh-syntax)"
  export DISPLAY=:5 QT_QPA_PLATFORM=xcb
  BIN=/opt/ascon/kompas3d-v25/Bin/kStudy
  test -x "$BIN"
  nohup "$BIN" >/tmp/kompas.log 2>&1 &
  echo $! >/tmp/kstudy.pid

  set +e
  found=0
  for i in $(seq 1 45); do
    if ss -ltnp | grep -Eq "kStudy|kKompas|kHome"; then
      found=1
      break
    fi
    sleep 2
  done
  DISPLAY=:5 scrot /work/kompas-diagnostic/screen.png || true
  ps aux | grep -E "[k]Study|[k]Kompas|[k]Home" > /work/kompas-diagnostic/processes.txt || true
  ss -ltnp | grep -E "kStudy|kKompas|kHome" > /work/kompas-diagnostic/sockets.txt || true
  cp /tmp/kompas.log /work/kompas-diagnostic/kompas.log || true
  cp /tmp/xvfb.log /work/kompas-diagnostic/xvfb.log || true
  cp /tmp/xephyr.log /work/kompas-diagnostic/xephyr.log || true
  cp /tmp/openbox.log /work/kompas-diagnostic/openbox.log || true
  set -e

  if [ "$found" -ne 1 ]; then
    echo "NO_API_SOCKET" | tee /work/kompas-diagnostic/result.txt
    exit 20
  fi

  cd /opt/ascon/kompas3d-v25/Bin
  timeout 25s env DISPLAY=:5 QT_QPA_PLATFORM=xcb python3 - <<PY
import os,sys,time
sys.path.insert(0,'.')
import ksapi
from constants import constants as c
app=None
for _ in range(15):
    app=ksapi.GetKompas()
    if app is not None: break
    time.sleep(1)
if app is None: raise SystemExit("GetKompas=None")
print("APP", app.GetApplicationName(True))
try:
    app.SetHideMessage(c.ksHideMessageYes)
except Exception as e:
    print("SetHideMessage",repr(e))
doc=app.GetDocuments().Add(c.ksDocumentFragment, True)
d2=ksapi.IKompasDocument2D(doc)
view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc=ksapi.IDrawingContainer(view)
s=dc.GetLineSegments().Add()
s.SetX1(0); s.SetY1(0); s.SetX2(50); s.SetY2(20); s.SetStyle(c.ksCSNormal)
assert s.Update()
out="/work/kompas-diagnostic/native-smoke.frw"
try: os.remove(out)
except FileNotFoundError: pass
ok=doc.SaveAs(out)
print("SAVE",ok,os.path.getsize(out) if os.path.exists(out) else -1)
if not ok or not os.path.exists(out): raise SystemExit("SaveAs failed")
PY

  unzip -t /work/kompas-diagnostic/native-smoke.frw | tee /work/kompas-diagnostic/unzip.txt
  sha256sum /work/kompas-diagnostic/native-smoke.frw | tee /work/kompas-diagnostic/sha256.txt
  echo "NATIVE_SMOKE_PASS" | tee /work/kompas-diagnostic/result.txt
'
