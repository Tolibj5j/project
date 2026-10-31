#!/usr/bin/env bash
# simulyatsiya_testlari.sh - simulyator bilan o'tkaziladigan barcha
# tajribalarni ketma-ket bajaradi va natijalarni natijalar/ papkasiga yozadi.
set -eu
cd "$(dirname "$0")"
S="python3 rejalashtiruvchi.py"
Y=yuklamalar
R=natijalar
mkdir -p $R

{   # 1. To'g'rilikni tekshirish: darslikdagi ma'lum natijalar bilan solishtirish
    $S $Y/t1_fcfs_rr.txt -a fcfs --gantt
    $S $Y/t1_fcfs_rr.txt -a rr -q 4 --gantt
    $S $Y/t2_sjf.txt -a sjf --gantt
    $S $Y/t3_prio.txt -a prio --gantt
} > $R/1_tekshiruv.txt

{   # 2. Asosiy algoritmlarni bitta yuklamada taqqoslash
    $S $Y/w1_aralash.txt --compare -q 3
    for a in fcfs sjf prio rr mlfq fair; do $S $Y/w1_aralash.txt -a $a -q 3 --gantt; done
} > $R/2_taqqoslash.txt

{   # 3. Vaqt kvantining ta'siri (s - kontekstni almashtirish vaqti, ms)
    for s in 0 0.5; do echo "s=$s"; $S $Y/w2_kvant.txt -a rr -s $s --sweep 1,2,5,10,20,50,100,200; done
    $S $Y/w2_kvant.txt --compare -q 10 -s 0.5
} > $R/3_kvant.txt

{   # 4. Foydalanuvchilar o'rtasida adolatlilik
    $S $Y/w3_foydalanuvchilar.txt --compare -q 10 --window 200
    $S $Y/w3_foydalanuvchilar.txt -a rr -q 10 --window 200
    $S $Y/w3_foydalanuvchilar.txt -a fair -q 10 --window 200
    $S $Y/w4_ogirliklar.txt -a rr -q 10 --window 400
    $S $Y/w4_ogirliklar.txt -a fair -q 10 --window 400
} > $R/4_adolatlilik.txt

{   # 5. Interaktiv jarayonlar: RR va MLFQ
    $S $Y/w5_interaktiv.txt -a rr -q 20 -s 0.1
    $S $Y/w5_interaktiv.txt -a rr -q 4 -s 0.1
    $S $Y/w5_interaktiv.txt -a mlfq -q 4 -s 0.1
    $S $Y/w5_interaktiv.txt -a mlfq -q 4 -s 0.1 --boost 100
} > $R/5_mlfq.txt

{   # 6. Ochlik va qarish usuli
    $S $Y/w6_ochlik.txt -a prio --gantt
    $S $Y/w6_ochlik.txt -a prio --aging 2 --gantt
} > $R/6_ochlik.txt

ls -l $R
