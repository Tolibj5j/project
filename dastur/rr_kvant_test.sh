#!/usr/bin/env bash
# rr_kvant_test.sh - SCHED_RR vaqt kvantining real Linux yadrosidagi ta'sirini
# o'lchash: N ta real vaqt jarayoni bitta yadroda navbat bilan bajariladi.
# Ishga tushirish: sudo ./rr_kvant_test.sh       (DUR=5 CPU=0 N=3 sozlanadi)
set -u
DUR=${DUR:-5}
CPU=${CPU:-0}
N=${N:-3}
DIR=$(cd "$(dirname "$0")" && pwd)
BIN_DIR=${BIN_DIR:-/opt/mfq}    # burn dasturi joylashadigan papka
BIN=$BIN_DIR/burn
TS=/proc/sys/kernel/sched_rr_timeslice_ms
OUT=$(mktemp)

[ "$(id -u)" -eq 0 ] || { echo "Skriptni root huquqi bilan ishga tushiring"; exit 1; }
OLD=$(cat $TS)
trap 'echo "$OLD" > $TS; rm -f "$OUT"' EXIT
mkdir -p $BIN_DIR && gcc -O2 -Wall -o $BIN "$DIR/burn.c" &&
    gcc -O2 -Wall -o $BIN_DIR/ctxsw "$DIR/ctxsw.c" || exit 1

echo "Kontekstni almashtirish vaqtini o'lchash (3 marta):"
for i in 1 2 3; do $BIN_DIR/ctxsw 200000 $CPU; done

# measure NOM [chrt parametrlari] - N ta jarayonni ishga tushirib natijani jamlash
measure() {
    local name=$1; shift
    local t0
    t0=$(awk -v t="$(date +%s.%N)" 'BEGIN { printf "%.3f", t + 0.5 }')
    : > "$OUT"
    for i in $(seq $N); do "$@" taskset -c $CPU $BIN $DUR $i $t0 >> "$OUT" & done
    wait
    awk -v name="$name" -v dur="$DUR" '
        { for (i = 1; i <= NF; i++) { split($i, kv, "="); v[kv[1]] = kv[2] }
          work += v["ish"]; cpu += v["cpu"]; band += v["ulush"]
          sw += v["nivcsw"]; gap += v["kutish_ort"]
          if (v["kutish_max"] > mx) mx = v["kutish_max"]; n++ }
        END { printf "%-10s %10.0f %14.2f %11.1f %11.1f %11.0f\n",
                     name, sw / dur, gap / n, mx, band, work / cpu }' "$OUT"
}

echo "Yadro: $(uname -r); bitta yadroda $N ta jarayon, har biri $DUR s"
printf "%-10s %10s %14s %11s %11s %11s\n" "Kvant" "Almasht./s" \
    "Kutish_ort,ms" "Kutish_max" "CPU_band,%" "Ish/CPU-s"
for q in 1 5 10 20 50 100; do
    echo $q > $TS
    measure "RR q=${q}" chrt -r 10
done
echo "$OLD" > $TS
measure "CFS" env
