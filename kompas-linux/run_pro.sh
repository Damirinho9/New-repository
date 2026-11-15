#!/bin/bash
set -u
mkdir -p kompas-linux/logs
exec > >(tee kompas-linux/logs/runner.log) 2>&1

echo "=== enable ASCON repo ==="
apt-get update
apt-get install -y wget ca-certificates
bash -c "$(wget -O - https://repo.ascon.ru/scripts/ascon-stable-alt.sh)"
apt-get update

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
set +e
apt-get install -y procps iproute2 python3
set -e

echo "=== X11 passed from host ==="
echo "DISPLAY=$DISPLAY"
ls -la /tmp/.X11-unix || true

echo "=== start KOMPAS professional ==="
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true
nohup kompas-v25 >kompas-linux/logs/kompas.log 2>&1 &
KP=$!
echo "$KP" >kompas-linux/logs/kompas.pid

OK=0
for i in $(seq 1 75); do
  echo "probe=$i"
  ps aux | grep -E '[k]Kompas|[k]Home|[k]Study' || true
  if ss -ltnp | grep -E 'kKompas|kHome|kStudy'; then
    OK=1
    break
  fi
  if ! kill -0 "$KP" 2>/dev/null; then
    echo "KOMPAS process exited"
    break
  fi
  sleep 2
done

echo "=== KOMPAS LOG ==="
tail -300 kompas-linux/logs/kompas.log || true
echo "=== SOCKETS ==="
ss -ltnp | grep -E 'kKompas|kHome|kStudy' || true

if [ "$OK" != "1" ]; then
  echo "RESULT=KOMPAS_API_NOT_AVAILABLE" | tee kompas-linux/verification.txt
  exit 2
fi

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
