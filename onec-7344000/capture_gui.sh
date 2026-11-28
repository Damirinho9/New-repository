#!/usr/bin/env bash
set -euo pipefail
: "${WORK:?WORK required}"
: "${OUT:?OUT required}"
server="${SERVER_CONTAINER:-hotel-final-ibsrv}"
image="${CLIENT_IMAGE:-hotel-client-tools}"
mkdir -p "$OUT/screenshots"

terminate_sessions() {
  local list="$OUT/sessions-gui.txt"
  docker exec "$server" /opt/1cv8/x86_64/8.3.27.1508/ibcmd --pid=1 session list > "$list" 2>&1 || true
  while read -r sid; do
    [ -n "$sid" ] || continue
    docker exec "$server" /opt/1cv8/x86_64/8.3.27.1508/ibcmd --pid=1 session terminate --session="$sid" >> "$OUT/session-terminate-gui.txt" 2>&1 || true
  done < <(sed -nE 's/^[[:space:]]*session[[:space:]]*:[[:space:]]*([^[:space:]]+).*$/\1/p' "$list")
  sleep 2
}

capture_one() {
  local param="$1" file="$2" disp="$3" wait_s="$4"
  terminate_sessions
  rm -f "$WORK/tmp/$file" "$WORK/tmp/$param.log" 2>/dev/null || true
  docker run --rm --network host \
    -e PARAM="$param" -e FILE="$file" -e DISP="$disp" -e WAIT_S="$wait_s" \
    --entrypoint /bin/bash -v "$WORK/tmp:/tmp" "$image" -lc '
      set -euo pipefail
      export HOME="/tmp/home-$PARAM"
      mkdir -p "$HOME"
      export DISPLAY=":$DISP"
      Xvfb "$DISPLAY" -screen 0 1440x900x24 >"/tmp/xvfb-$PARAM.log" 2>&1 &
      xp=$!
      sleep 2
      C=/opt/1cv8/x86_64/8.3.27.1508/1cv8c
      if [ "$PARAM" = "main" ]; then
        "$C" ENTERPRISE "/WShttp://127.0.0.1:8314" /DisableStartupDialogs /DisableStartupMessages "/Out/tmp/$PARAM.log" &
      else
        "$C" ENTERPRISE "/WShttp://127.0.0.1:8314" "/C$PARAM" /DisableStartupDialogs /DisableStartupMessages "/Out/tmp/$PARAM.log" &
      fi
      p=$!
      sleep "$WAIT_S"
      if [ "$PARAM" = "shot-report" ]; then
        win=$(xdotool search --onlyvisible --name "Бронирование и выручка гостиницы за период" | head -n1 || true)
        if [ -n "$win" ]; then
          xdotool windowactivate --sync "$win" || true
          xdotool mousemove --window "$win" 285 118 click 1 || true
          sleep 2
          xdotool key --window "$win" ctrl+Return || true
        else
          xdotool mousemove 465 238 click 1 || true
          sleep 2
          xdotool key ctrl+Return || true
        fi
        sleep 20
      fi
      scrot "/tmp/$FILE"
      kill "$p" >/dev/null 2>&1 || true
      pkill -9 -x 1cv8c >/dev/null 2>&1 || true
      pkill -9 -x 1cv8 >/dev/null 2>&1 || true
      kill "$xp" >/dev/null 2>&1 || true
      chmod -R a+rwX /tmp
    '
  cp "$WORK/tmp/$file" "$OUT/screenshots/$file"
  cp "$WORK/tmp/$param.log" "$OUT/" 2>/dev/null || true
  test -s "$OUT/screenshots/$file"
}

capture_one main 01-main.png 97 15
capture_one shot-guests 02-guests.png 96 15
capture_one shot-rooms 03-rooms.png 95 15
capture_one shot-bookings 04-bookings.png 94 15
capture_one shot-payments 05-payments.png 93 15
capture_one shot-report 06-report.png 92 10
capture_one shot-live-autosum 07-live-autosum.png 91 18
capture_one shot-services 08-services.png 90 18
capture_one shot-threshold 09-threshold.png 89 20
terminate_sessions
