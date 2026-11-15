#!/usr/bin/env bash
set -euxo pipefail
IMAGE=registry.astralinux.ru/library/astra/ubi18:latest

docker pull "$IMAGE"
docker rm -f kompas-astra 2>/dev/null || true
docker run --name kompas-astra --privileged --network host --shm-size=2g -d \
  -v "$GITHUB_WORKSPACE:/work" "$IMAGE" sleep infinity

timeout 420s docker exec kompas-astra bash -lc '
  set -euxo pipefail
  export DEBIAN_FRONTEND=noninteractive
  timeout 120s apt-get update
  timeout 180s apt-get install -y wget curl gnupg lsb-release procps iproute2 python3 unzip locales \
    xserver-xorg-core xserver-xorg-video-dummy openbox dbus-x11 x11-xkb-utils \
    desktop-file-utils x11-apps libatomic1 libxcb-res0 libgl1-mesa-dri
  touch /etc/locale.gen
  grep -q "^ru_RU.CP1251 CP1251" /etc/locale.gen || echo "ru_RU.CP1251 CP1251" >> /etc/locale.gen
  locale-gen || true

  wget -qO /tmp/ascon-personal-deb.sh https://repo.ascon.ru/personal/scripts/ascon-personal-deb.sh
  wget -qO /tmp/ascon-stable-deb.sh https://repo.ascon.ru/scripts/ascon-stable-deb.sh
  bash /tmp/ascon-personal-deb.sh
  bash /tmp/ascon-stable-deb.sh
  timeout 120s apt-get update
  timeout 180s apt-get install -y ascon-kompas-graphic-v25 ascon-kompas-study-v25 ascon-kompas-sdk-v25

  mkdir -p /work/kompas-xorg-fast
  cat >/tmp/xorg-dummy.conf <<"EOF"
Section "ServerFlags"
  Option "DontVTSwitch" "true"
  Option "AllowMouseOpenFail" "true"
  Option "AutoEnableDevices" "false"
  Option "AutoAddDevices" "false"
EndSection
Section "Device"
  Identifier "DummyDevice"
  Driver "dummy"
  VideoRam 256000
EndSection
Section "Monitor"
  Identifier "DummyMonitor"
  HorizSync 5.0 - 1000.0
  VertRefresh 5.0 - 200.0
  Modeline "1400x900" 106.50 1400 1488 1632 1864 900 903 913 934 -HSync +Vsync
EndSection
Section "Screen"
  Identifier "DummyScreen"
  Device "DummyDevice"
  Monitor "DummyMonitor"
  DefaultDepth 24
  SubSection "Display"
    Depth 24
    Modes "1400x900"
  EndSubSection
EndSection
EOF

  Xorg :5 -config /tmp/xorg-dummy.conf -noreset -nolisten tcp -logfile /tmp/Xorg.5.log >/tmp/xorg.stdout 2>&1 &
  for i in $(seq 1 40); do [ -e /tmp/.X11-unix/X5 ] && break; sleep 0.25; done
  test -e /tmp/.X11-unix/X5

  export DISPLAY=:5 QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1
  export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
  timeout 5s xset q > /work/kompas-xorg-fast/xset.txt 2>&1
  openbox >/tmp/openbox.log 2>&1 &
  eval "$(dbus-launch --sh-syntax)"
  unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true

  BIN=/opt/ascon/kompas3d-v25/Bin/kStudy
  ldd "$BIN" > /work/kompas-xorg-fast/ldd.txt
  ! grep -q "not found" /work/kompas-xorg-fast/ldd.txt

  nohup "$BIN" >/tmp/kompas.log 2>&1 &
  echo $! > /work/kompas-xorg-fast/kstudy.pid

  found=0
  for i in $(seq 1 30); do
    if ss -ltnp | grep -Eq "kStudy|kKompas|kHome"; then found=1; break; fi
    sleep 2
  done

  DISPLAY=:5 xwd -root -silent -out /work/kompas-xorg-fast/screen.xwd || true
  ps aux | grep -E "[k]Study|[k]Kompas|[k]Home" > /work/kompas-xorg-fast/processes.txt || true
  ss -ltnp | grep -E "kStudy|kKompas|kHome" > /work/kompas-xorg-fast/sockets.txt || true
  cp /tmp/kompas.log /work/kompas-xorg-fast/kompas.log || true
  cp /tmp/Xorg.5.log /work/kompas-xorg-fast/Xorg.5.log || true
  cp /tmp/openbox.log /work/kompas-xorg-fast/openbox.log || true

  if [ "$found" -ne 1 ]; then echo "NO_API_SOCKET" > /work/kompas-xorg-fast/result.txt; exit 20; fi

  cd /opt/ascon/kompas3d-v25/Bin
  timeout 20s env DISPLAY=:5 QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1 python3 - <<"PY"
import os,sys,time
sys.path.insert(0,".")
import ksapi
from constants import constants as c
app=None
for _ in range(10):
    app=ksapi.GetKompas()
    if app is not None: break
    time.sleep(1)
if app is None: raise SystemExit("GetKompas=None")
print("APP",app.GetApplicationName(True),flush=True)
doc=app.GetDocuments().Add(c.ksDocumentFragment,True)
d2=ksapi.IKompasDocument2D(doc)
view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc=ksapi.IDrawingContainer(view)
s=dc.GetLineSegments().Add()
s.SetX1(0); s.SetY1(0); s.SetX2(50); s.SetY2(20); s.SetStyle(c.ksCSNormal)
assert s.Update()
out="/work/kompas-xorg-fast/native-smoke.frw"
try: os.remove(out)
except FileNotFoundError: pass
assert doc.SaveAs(out)
assert os.path.getsize(out)>1000
print("SAVED",os.path.getsize(out),flush=True)
PY
  unzip -t /work/kompas-xorg-fast/native-smoke.frw > /work/kompas-xorg-fast/unzip.txt
  sha256sum /work/kompas-xorg-fast/native-smoke.frw > /work/kompas-xorg-fast/sha256.txt
  echo NATIVE_SMOKE_PASS > /work/kompas-xorg-fast/result.txt
'
