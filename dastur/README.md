# Multidasturlash: rejalashtirish simulyatori va Linux tajribalari

Mustaqil ishning III–IV boblarida ishlatilgan dasturlar.

| Fayl | Vazifasi |
|---|---|
| `rejalashtiruvchi.py` | FCFS, SJF, PRIO, RR, MLFQ va FAIR algoritmlari simulyatori (Python 3, tashqi kutubxonasiz) |
| `burn.c` | CPU yuklama generatori va o‘lchash dasturi |
| `ctxsw.c` | Kontekstni almashtirish vaqtini o‘lchash |
| `multiuser_test.sh` | Ikki foydalanuvchi bilan nice, cgroup v2, autogroup va himoya tajribalari |
| `rr_kvant_test.sh` | `SCHED_RR` vaqt kvanti tajribasi |
| `simulyatsiya_testlari.sh` | Barcha simulyatsiya tajribalarini bajaradi |
| `yuklamalar/` | Tekshiruv testlari va tajriba yuklamalari |
| `natijalar/` | Hisobotda keltirilgan haqiqiy natijalar |

## Ishga tushirish

```bash
# bitta algoritm
python3 rejalashtiruvchi.py yuklamalar/t1_fcfs_rr.txt -a rr -q 4 --gantt
# barcha algoritmlarni taqqoslash
python3 rejalashtiruvchi.py yuklamalar/w1_aralash.txt --compare -q 3
# kvant tajribasi
python3 rejalashtiruvchi.py yuklamalar/w2_kvant.txt -a rr -s 0.5 --sweep 1,2,5,10,20,50,100,200
# adolatlilik (foydalanuvchilar ulushi va Jain indeksi)
python3 rejalashtiruvchi.py yuklamalar/w3_foydalanuvchilar.txt -a fair -q 10 --window 200

# barcha simulyatsiya tajribalari
./simulyatsiya_testlari.sh

# Linux tajribalari (root huquqi, gcc kerak; masalan, VirtualBox dagi Ubuntu)
sudo ./multiuser_test.sh        # DUR=10 CPU=0
sudo ./rr_kvant_test.sh         # DUR=5 CPU=0 N=3
```

Linux skriptlari tizim sozlamalarini (autogroup, `sched_rr_timeslice_ms`, cgroup guruhlari) vaqtincha o‘zgartiradi va yakunda dastlabki holatga qaytaradi. `multiuser_test.sh` `talaba_a` va `talaba_b` foydalanuvchilarini yaratadi; ular tizimda qoladi (`sudo userdel -r talaba_a` bilan o‘chiriladi).
