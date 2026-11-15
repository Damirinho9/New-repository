#!/bin/bash
set -u
mkdir -p kompas-linux/logs
exec > >(tee kompas-linux/logs/runner.log) 2>&1

echo "=== enable ASCON repo ==="
apt-get update
apt-get install -y wget ca-certificates
bash -c "$(wget -O - https://repo.ascon.ru/scripts/ascon-stable-alt.sh)"
apt-get update

echo "=== install locale and XCB dependencies first ==="
apt-get install -y glibc-i18ndata libxcbutil-icccm libxcbutil-keysyms libxcbutil-image libxcb-render-util libXv libXScrnSaver libxkbfile libfontenc || true

echo "=== install KOMPAS professional payload ==="
set +e
apt-get install -y ascon-kompas-graphic-v25 ascon-kompas-v25 ascon-kompas-sdk-v25
APT_RC=$?
set -e
echo "kompas_apt_rc=$APT_RC"
rpm -qa | grep -i '^ascon-kompas' | sort || true
find /opt/ascon -maxdepth 4 -type f -name kKompas -ls || true
find /opt/ascon -maxdepth 4 -type f -name ksapi.py -ls || true
test -x /opt/ascon/kompas3d-v25/Bin/kKompas

echo "=== install small runtime helpers separately ==="
apt-get install -y procps iproute2 python3 dbus || true
command -v python3
command -v dbus-run-session || true

echo "=== Qt headless mode ==="
unset DISPLAY || true
export QT_QPA_PLATFORM=offscreen
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

echo "=== dependency audit ==="
ldd /opt/ascon/kompas3d-v25/Bin/kKompas | tee kompas-linux/logs/ldd.txt
if grep -q "not found" kompas-linux/logs/ldd.txt; then
  echo "MISSING_LIBRARIES_DETECTED"
  grep "not found" kompas-linux/logs/ldd.txt
fi

echo "=== start KOMPAS professional ==="
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
pushd /opt/ascon/kompas3d-v25/Bin >/dev/null
if command -v dbus-run-session >/dev/null 2>&1; then
  nohup dbus-run-session -- ./kKompas > /work/kompas-linux/logs/kompas.log 2>&1 &
else
  nohup ./kKompas > /work/kompas-linux/logs/kompas.log 2>&1 &
fi
KP=$!
popd >/dev/null
echo "$KP" >kompas-linux/logs/kompas.pid

echo "=== process/API initial probe ==="
sleep 10
ps -eo pid,ppid,comm,args | grep -Ei '[k]Kompas|[k]Home|[k]Study|[K]OMPAS' || true
ss -ltnp || true
python3 - <<'PY' || true
import sys
sys.path.insert(0, "/opt/ascon/kompas3d-v25/Bin")
import ksapi
try:
    app=ksapi.GetKompas()
    print("KSAPI_GETKOMPAS=", app)
    if app is not None:
        print("APP_NAME=", app.GetApplicationName(True))
except Exception as e:
    print("KSAPI_ERROR=", repr(e))
PY

echo "=== build native FRW ==="

export KOMPAS_DIR=/opt/ascon/kompas3d-v25
python3 kompas-linux/build_native.py
test -s "kompas-linux/Работа_1_параметрическая.frw"
python3 - <<'PY'
import zipfile, pathlib, hashlib
p=pathlib.Path('kompas-linux/Работа_1_параметрическая.frw')
print('size',p.stat().st_size)
print('sha256',hashlib.sha256(p.read_bytes()).hexdigest())
assert zipfile.is_zipfile(p)
with zipfile.ZipFile(p) as z:
    print('members',z.namelist())
    assert 'Contents' in z.namelist()
PY
