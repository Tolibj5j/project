/*
 * burn.c - protsessorga yuklama beruvchi sinov dasturi.
 * Berilgan vaqt davomida uzluksiz hisoblaydi va yakunda quyidagilarni
 * chiqaradi: olingan protsessor vaqti va ulushi, bajarilgan ish hajmi,
 * ixtiyoriy (nvcsw) va majburiy (nivcsw) kontekst almashtirishlar soni,
 * jarayon protsessorsiz qolgan oraliqlarning o'rtacha va eng katta qiymati.
 *
 * Kompilyatsiya: gcc -O2 -Wall -o burn burn.c
 * Ishlatish:     ./burn [davomiylik_soniya] [belgi] [boshlanish_vaqti]
 * boshlanish_vaqti (Unix vaqti, soniya) berilsa, barcha jarayonlar bir xil
 * [T0; T0 + davomiylik] oraliqda o'lchanadi.
 */
#define _GNU_SOURCE
#include <pwd.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

#define GAP_MIN 0.0005 /* 0,5 ms dan uzun tanaffus - jarayon navbatda turgan */

static double now(clockid_t clk)
{
    struct timespec ts;
    clock_gettime(clk, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

int main(int argc, char **argv)
{
    double dur = argc > 1 ? atof(argv[1]) : 10.0;
    const char *tag = argc > 2 ? argv[2] : "-";
    volatile unsigned long x = 1;
    unsigned long work = 0;
    long gaps = 0;
    double gap_sum = 0, gap_max = 0;

    if (argc > 3) {                         /* umumiy boshlanish paytini kutish */
        double start = atof(argv[3]);
        struct timespec ts = { (time_t)start,
                               (long)((start - (time_t)start) * 1e9) };
        clock_nanosleep(CLOCK_REALTIME, TIMER_ABSTIME, &ts, NULL);
        dur -= now(CLOCK_REALTIME) - start; /* kechikkan bo'lsa, oyna qisqaradi */
    }
    double cpu0 = now(CLOCK_PROCESS_CPUTIME_ID);
    double t0 = now(CLOCK_MONOTONIC), prev = t0, t = t0;
    while (t - t0 < dur) {
        for (int i = 0; i < 20000; i++)     /* bitta ish bo'lagi (~30 mks) */
            x = x * 6364136223846793005UL + 1442695040888963407UL;
        work++;
        t = now(CLOCK_MONOTONIC);
        double gap = t - prev;              /* ikki bo'lak orasidagi vaqt */
        if (gap > GAP_MIN) {                /* jarayon protsessorni yo'qotgan */
            gaps++;
            gap_sum += gap;
        }
        if (gap > gap_max)
            gap_max = gap;
        prev = t;
    }

    double wall = t - t0;
    double cpu = now(CLOCK_PROCESS_CPUTIME_ID) - cpu0;
    struct rusage ru;
    getrusage(RUSAGE_SELF, &ru);
    struct passwd *pw = getpwuid(getuid());
    const char *pol = sched_getscheduler(0) == SCHED_RR ? "RR" : "OTHER";

    printf("foyd=%s pid=%d siyosat=%s nice=%d cpu=%.2f ulush=%.1f ish=%lu "
           "nvcsw=%ld nivcsw=%ld kutish_ort=%.2f kutish_max=%.1f belgi=%s\n",
           pw ? pw->pw_name : "?", getpid(), pol,
           getpriority(PRIO_PROCESS, 0), cpu, 100.0 * cpu / wall, work,
           ru.ru_nvcsw, ru.ru_nivcsw,
           gaps ? 1000.0 * gap_sum / gaps : 0.0, 1000.0 * gap_max, tag);
    return 0;
}
