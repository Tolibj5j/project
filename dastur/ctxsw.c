/*
 * ctxsw.c - kontekstni almashtirish vaqtini o'lchash.
 * Bitta yadroga bog'langan ikki jarayon kanal (pipe) orqali 1 baytni
 * navbat bilan uzatadi: har bir uzatishda protsessor bir jarayondan
 * ikkinchisiga o'tadi. Kanal tizim chaqiruvlarining narxi alohida
 * o'lchanib, umumiy vaqtdan ayiriladi (lmbench lat_ctx usuli).
 *
 * Kompilyatsiya: gcc -O2 -Wall -o ctxsw ctxsw.c
 * Ishlatish:     ./ctxsw [takrorlashlar_soni] [yadro_raqami]
 */
#define _GNU_SOURCE
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static double now(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

static void pin(int cpu)
{
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof(set), &set) != 0) {
        perror("sched_setaffinity");
        exit(1);
    }
}

int main(int argc, char **argv)
{
    long n = argc > 1 ? atol(argv[1]) : 200000;
    int cpu = argc > 2 ? atoi(argv[2]) : 0;
    int self[2], a[2], b[2];
    char c = 'x';
    pin(cpu);

    /* 1) faqat tizim chaqiruvlari: jarayon o'z kanaliga yozadi va o'qiydi */
    if (pipe(self) != 0) { perror("pipe"); return 1; }
    double t0 = now();
    for (long i = 0; i < n; i++)
        if (write(self[1], &c, 1) != 1 || read(self[0], &c, 1) != 1)
            return 1;
    double t_sys = (now() - t0) / n;

    /* 2) ikki jarayon o'rtasida "ping-pong": har bir uzatishda almashtirish */
    if (pipe(a) != 0 || pipe(b) != 0) { perror("pipe"); return 1; }
    pid_t pid = fork();
    if (pid == 0) {                            /* bola jarayon */
        for (long i = 0; i < n; i++)
            if (read(a[0], &c, 1) != 1 || write(b[1], &c, 1) != 1)
                _exit(1);
        _exit(0);
    }
    t0 = now();
    for (long i = 0; i < n; i++)
        if (write(a[1], &c, 1) != 1 || read(b[0], &c, 1) != 1)
            return 1;
    double t_pp = (now() - t0) / (2.0 * n);    /* bitta yo'nalish vaqti */
    waitpid(pid, NULL, 0);

    printf("takrorlash=%ld yadro=%d tizim_chaqiruvi=%.2f mks "
           "ping_pong=%.2f mks almashtirish=%.2f mks\n",
           n, cpu, t_sys * 1e6, t_pp * 1e6, (t_pp - t_sys) * 1e6);
    return 0;
}
