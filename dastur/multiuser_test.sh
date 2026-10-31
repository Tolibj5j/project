#!/usr/bin/env bash
# multiuser_test.sh - Linux operatsion tizimida ko'p foydalanuvchili rejimni
# tajribada tekshirish: protsessor vaqtining foydalanuvchilar o'rtasida
# taqsimlanishi (nice, cgroup v2, autogroup) va himoya mexanizmlari.
# Ishga tushirish: sudo ./multiuser_test.sh      (DUR=10 CPU=0 sozlanadi)
set -u
DUR=${DUR:-10}                 # har bir tajriba davomiyligi, soniya
CPU=${CPU:-0}                  # barcha jarayonlar bog'lanadigan yadro raqami
DIR=$(cd "$(dirname "$0")" && pwd)
BIN_DIR=${BIN_DIR:-/opt/mfq}    # burn dasturi joylashadigan papka
BIN=$BIN_DIR/burn
CG=/sys/fs/cgroup/mfq
# konteynerlarda cgroup ildizi "threaded" turida bo'lishi mumkin
CGTYPE=$(cat /sys/fs/cgroup/cgroup.type 2>/dev/null || echo domain)
PROCS=cgroup.procs
[ "$CGTYPE" = threaded ] && PROCS=cgroup.threads
UA=talaba_a
UB=talaba_b
AG=/proc/sys/kernel/sched_autogroup_enabled
OUT=$(mktemp -d)

[ "$(id -u)" -eq 0 ] || { echo "Skriptni root huquqi bilan ishga tushiring"; exit 1; }
AG_OLD=$(cat $AG)

cleanup() {                    # tizim holatini dastlabki ko'rinishga qaytarish
    echo "$AG_OLD" > $AG
    pkill -u $UA 2>/dev/null
    sleep 0.5
    rmdir $CG/$UA $CG/$UB $CG 2>/dev/null
    rm -rf "$OUT"
}
trap cleanup EXIT

setup() {
    for u in $UA $UB; do
        id -u $u >/dev/null 2>&1 || useradd -m -s /bin/bash $u
    done
    mkdir -p $BIN_DIR
    gcc -O2 -Wall -o $BIN "$DIR/burn.c" && chmod 755 $BIN
    [ -w /sys/fs/cgroup ] || mount -o remount,rw /sys/fs/cgroup
    grep -qw cpu /sys/fs/cgroup/cgroup.subtree_control ||
        echo +cpu > /sys/fs/cgroup/cgroup.subtree_control
    for g in $CG $CG/$UA $CG/$UB; do      # mfq/{talaba_a,talaba_b} guruhlari
        mkdir -p $g
        [ "$CGTYPE" = threaded ] && echo threaded > $g/cgroup.type
        [ $g = $CG ] && echo +cpu > $CG/cgroup.subtree_control
    done
}

# start FOYDALANUVCHI SONI [NICE] [CGROUP] [SEANS]
# FOYDALANUVCHI nomidan SONI ta burn jarayonini bitta CPU yadrosida ishga
# tushiradi. CGROUP berilsa, jarayonlar shu guruhga joylanadi; SEANS=yes
# bo'lsa, foydalanuvchi jarayonlari alohida seansda (setsid) ishlaydi.
start() {
    local user=$1 n=$2 nv=${3:-0} grp=${4:-} ses=${5:-}
    (
        [ -n "$grp" ] && echo $BASHPID > "$CG/$grp/$PROCS"
        exec ${ses:+setsid -w} runuser -u "$user" -- env N="$n" NV="$nv" \
            C="$CPU" B="$BIN" D="$DUR" T0="$T0" bash -c \
            'for i in $(seq $N); do nice -n $NV taskset -c $C $B $D $i $T0 & done; wait'
    ) >> "$OUT/natija.txt" &
}

title() {                      # sarlavha va umumiy boshlanish payti (T0)
    printf '\n=== %s\n' "$1"
    T0=$(awk -v t="$(date +%s.%N)" 'BEGIN { printf "%.3f", t + 1 }')
}

report() {                     # jarayonlar va foydalanuvchilar bo'yicha natija
    wait
    awk '{ for (i = 1; i <= NF; i++) { split($i, kv, "="); v[kv[1]] = kv[2] }
           printf "  %-9s pid=%-7s nice=%-3s cpu=%5ss ulush=%5s%% nivcsw=%-5s kutish_ort=%sms\n",
                  v["foyd"], v["pid"], v["nice"], v["cpu"], v["ulush"], v["nivcsw"], v["kutish_ort"] | "sort"
           s[v["foyd"]] += v["ulush"]; c[v["foyd"]]++ }
         END { close("sort")
               for (u in s) printf "  JAMI %-9s jarayonlar=%d  CPU ulushi=%5.1f%%\n", u, c[u], s[u] | "sort"
               close("sort") }' "$OUT/natija.txt"
    : > "$OUT/natija.txt"
}

setup
echo "Yadro: $(uname -r), CPU yadrolari: $(nproc), tajriba yadrosi: $CPU, davomiylik: ${DUR} s"
echo "Foydalanuvchilar: $(id $UA); $(id $UB)"

echo 0 > $AG
title "1-tajriba. Standart CFS: $UA - 1 ta, $UB - 4 ta jarayon"
start $UA 1; start $UB 4; report

title "2-tajriba. nice: $UB jarayonlari nice=5 bilan"
start $UA 1 0; start $UB 4 5; report

title "3-tajriba. cgroup v2: har bir foydalanuvchi guruhi cpu.weight=100"
echo 100 > $CG/$UA/cpu.weight
echo 100 > $CG/$UB/cpu.weight
start $UA 1 0 $UA; start $UB 4 0 $UB; report

title "4-tajriba. cgroup v2: $UB guruhi uchun cpu.max=\"20000 100000\" (20 %)"
echo "20000 100000" > $CG/$UB/cpu.max
start $UA 1 0 $UA; start $UB 4 0 $UB; report
echo max > $CG/$UB/cpu.max

title "5-tajriba. autogroup yoqilgan, har bir foydalanuvchi alohida seansda"
echo 1 > $AG
start $UA 1 0 "" yes; start $UB 4 0 "" yes; report

title "6-tajriba. Himoya mexanizmlari ($UB foydalanuvchisi nomidan)"
F=/home/$UA/maxfiy.txt
runuser -u $UA -- bash -c "echo 'maxfiy' > $F; chmod 600 $F"
ls -ld /home/$UA | awk '{print "  " $1, $3, $4, $NF}'
ls -l $F | awk '{print "  " $1, $3, $4, $NF}'
echo "  \$ cat $F";             runuser -u $UB -- cat $F 2>&1 | sed 's/^/  /'
echo "  \$ cat /etc/shadow";    runuser -u $UB -- cat /etc/shadow 2>&1 | sed 's/^/  /'
runuser -u $UA -- sleep 60 &
sleep 0.5
PA=$(pgrep -u $UA -n sleep)
echo "  \$ kill $PA   # $UA jarayoni"; runuser -u $UB -- kill $PA 2>&1 | sed 's/^/  /'
echo "  \$ renice -n -5 -p \$\$"; runuser -u $UB -- bash -c 'renice -n -5 -p $$' 2>&1 | sed 's/^/  /'
cat > $BIN_DIR/forktest.py <<'EOF'
import os, time
n = 0
try:
    for _ in range(50):
        if os.fork() == 0:
            time.sleep(2)
            os._exit(0)
        n += 1
except OSError as e:
    print(f"yaratildi: {n} ta jarayon, keyingi fork() xatosi: {e.strerror}")
EOF
echo "  \$ ulimit -u 20; python3 forktest.py   # 50 ta jarayon yaratishga urinish"
runuser -u $UB -- bash -c "ulimit -u 20; python3 $BIN_DIR/forktest.py" 2>&1 | sed 's/^/  /'
{ kill $PA; wait; } 2>/dev/null
