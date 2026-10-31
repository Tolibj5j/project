#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rejalashtiruvchi.py - ajratilgan vaqt tizimida protsessorni rejalashtirish
algoritmlarini modellashtiruvchi diskret-hodisali simulyator.

Algoritmlar:
  fcfs - birinchi kelgan birinchi xizmat qilinadi (majburiy emas)
  sjf  - eng qisqa CPU davri birinchi (majburiy emas)
  prio - ustuvorlik bo'yicha, majburiy; --aging bilan qarish usuli
  rr   - Round Robin, vaqt kvanti -q
  mlfq - ko'p darajali qayta aloqali navbat (kvantlar q, 2q, 4q, ...)
  fair - foydalanuvchilar bo'yicha adolatli taqsimlash (fair-share)
"""
import argparse
import sys
from collections import deque

INF = float("inf")
EPS = 1e-9


class PCB:
    """Jarayonni boshqarish bloki (Process Control Block)."""

    def __init__(self, pid, user, arrival, prio, bursts, io):
        self.pid, self.user = pid, user
        self.arrival, self.prio = arrival, prio
        self.bursts, self.io = bursts, io   # CPU davrlari va I/O davomiyligi
        self.state = "YANGI"
        self.idx = 0                    # joriy CPU davrining tartib raqami
        self.left = bursts[0]           # joriy davrning qolgan qismi
        self.ready_since = arrival      # tayyor navbatga oxirgi kirgan vaqt
        self.burst_ready = arrival      # joriy CPU davri tayyor bo'lgan vaqt
        self.started = False            # joriy davr protsessor oldimi
        self.latency = []               # har bir davr uchun reaksiya vaqti
        self.first_run = None           # birinchi marta protsessor olgan vaqt
        self.finish = None              # yakunlangan vaqt
        self.slice = 0.0                # joriy kvantda ishlangan vaqt
        self.run_prio = prio            # PRIO: ishga tushirilgandagi ustuvorlik
        self.level = 0                  # MLFQ: navbat darajasi
        self.allot = 0.0                # MLFQ: joriy darajada sarflangan vaqt

    @property
    def cpu(self):
        return sum(self.bursts)

    @property
    def io_total(self):
        return self.io * (len(self.bursts) - 1)


# ----------------------------------------------------------------------------
# Rejalashtirish siyosatlari. Har bir siyosat bir xil interfeysga ega:
#   add(p, t)            - jarayon tayyor holatga o'tdi
#   pick(t)              - navbatdan keyingi jarayonni tanlash
#   run_limit(p)         - p uzilishsiz yana qancha ishlay oladi
#   on_run(p, used)      - p protsessorda used vaqt ishladi (hisob)
#   on_expire / on_preempt / on_leave - protsessordan chiqish sabablari
#   should_preempt(cur, t), next_timer(t), timer(t) - majburiy almashtirish
# ----------------------------------------------------------------------------
class FCFS:
    """Birinchi kelgan - birinchi xizmat qilinadi."""
    name = "FCFS"

    def __init__(self, args):
        self.queue = deque()

    def add(self, p, t):
        self.queue.append(p)

    def pick(self, t):
        return self.queue.popleft() if self.queue else None

    def run_limit(self, p):
        return INF

    def on_run(self, p, used):
        p.slice += used

    def on_expire(self, p, t):
        self.queue.append(p)

    def on_preempt(self, p, t):
        self.on_expire(p, t)

    def on_leave(self, p, t):
        pass

    def should_preempt(self, cur, t):
        return False

    def next_timer(self, t):
        return INF

    def timer(self, t):
        pass


class RR(FCFS):
    """Round Robin: har bir jarayonga navbat bilan bitta vaqt kvanti beriladi."""
    name = "RR"

    def __init__(self, args):
        super().__init__(args)
        self.quant = args.q

    def run_limit(self, p):
        return self.quant - p.slice


class SJF(FCFS):
    """Eng qisqa CPU davriga ega jarayon birinchi tanlanadi."""
    name = "SJF"

    def __init__(self, args):
        self.ready = []

    def add(self, p, t):
        self.ready.append(p)

    def on_expire(self, p, t):
        self.ready.append(p)

    def key(self, p, t):
        return (p.left, p.burst_ready, p.pid)

    def pick(self, t):
        if not self.ready:
            return None
        p = min(self.ready, key=lambda x: self.key(x, t))
        self.ready.remove(p)
        return p


class PRIO(SJF):
    """Ustuvorlik bo'yicha majburiy rejalashtirish (kichik son - yuqori
    ustuvorlik). aging > 0 bo'lsa, navbatda har aging vaqt birligi kutgan
    jarayonning ustuvorligi 1 ga yaxshilanadi (qarish usuli)."""
    name = "PRIO"

    def __init__(self, args):
        super().__init__(args)
        self.aging = args.aging

    def eff(self, p, t):
        if self.aging > 0:
            return p.prio - int((t - p.ready_since + EPS) // self.aging)
        return p.prio

    def key(self, p, t):
        return (self.eff(p, t), p.ready_since, p.pid)

    def pick(self, t):
        p = super().pick(t)
        if p is not None:
            p.run_prio = self.eff(p, t)
        return p

    def should_preempt(self, cur, t):
        return any(self.eff(p, t) < cur.run_prio for p in self.ready)

    def next_timer(self, t):
        if self.aging <= 0 or not self.ready:
            return INF
        # navbatdagi biror jarayon ustuvorligi o'zgaradigan eng yaqin payt
        return min(p.ready_since + self.aging *
                   (int((t - p.ready_since + EPS) // self.aging) + 1)
                   for p in self.ready)


class MLFQ(FCFS):
    """Ko'p darajali qayta aloqali navbat. Yangi jarayon eng yuqori navbatga
    tushadi; darajadagi vaqt ulushini to'liq sarflagan jarayon pastga
    tushiriladi; har S vaqt birligida barcha jarayonlar yuqoriga qaytariladi."""
    name = "MLFQ"

    def __init__(self, args):
        self.n = args.levels
        self.quanta = [args.q * 2 ** i for i in range(self.n)]
        self.queues = [deque() for _ in range(self.n)]
        self.boost = args.boost
        self.next_boost = args.boost if args.boost > 0 else INF
        self.known = {}                         # tizimdagi barcha jarayonlar

    def add(self, p, t):
        self.known[p.pid] = p
        self.queues[p.level].append(p)

    def pick(self, t):
        for q in self.queues:
            if q:
                return q.popleft()
        return None

    def run_limit(self, p):
        return self.quanta[p.level] - p.allot

    def on_run(self, p, used):
        p.slice += used
        p.allot += used

    def demote(self, p):
        if p.allot >= self.quanta[p.level] - EPS:      # ulush tugadi
            p.level = min(p.level + 1, self.n - 1)
            p.allot = 0.0

    def on_expire(self, p, t):
        self.demote(p)
        self.queues[p.level].append(p)

    def on_preempt(self, p, t):
        self.queues[p.level].appendleft(p)

    def on_leave(self, p, t):
        self.demote(p)

    def should_preempt(self, cur, t):
        return any(self.queues[k] for k in range(cur.level))

    def next_timer(self, t):
        return self.next_boost

    def timer(self, t):
        while t >= self.next_boost - EPS:              # ustuvorlikni tiklash
            for p in self.known.values():
                p.level, p.allot = 0, 0.0
            merged = [p for q in self.queues for p in q]
            for q in self.queues:
                q.clear()
            self.queues[0].extend(merged)
            self.next_boost += self.boost


class FAIR(FCFS):
    """Foydalanuvchilar bo'yicha adolatli taqsimlash: avval virtual vaqti
    (CPU vaqti / og'irlik) eng kichik foydalanuvchi, so'ng uning navbatidagi
    jarayon Round Robin tartibida tanlanadi."""
    name = "FAIR"

    def __init__(self, args):
        self.quant = args.q
        self.weights = args.weights
        self.queues = {}                        # foydalanuvchi -> navbat
        self.vt = {}                            # foydalanuvchi virtual vaqti
        self.running = None

    def active(self):
        users = {u for u, q in self.queues.items() if q}
        if self.running is not None:
            users.add(self.running.user)
        return users

    def add(self, p, t):
        u = p.user
        if u not in self.active():
            # yangi faollashgan foydalanuvchi to'plangan "qarz" hisobiga
            # protsessorni uzoq egallab olmasligi uchun tenglashtiriladi
            others = [self.vt[x] for x in self.active()]
            base = min(others) if others else 0.0
            self.vt[u] = max(self.vt.get(u, 0.0), base)
        self.queues.setdefault(u, deque()).append(p)

    def pick(self, t):
        cand = [u for u, q in self.queues.items() if q]
        if not cand:
            return None
        u = min(cand, key=lambda x: (self.vt[x], x))
        self.running = self.queues[u].popleft()
        return self.running

    def run_limit(self, p):
        return self.quant - p.slice

    def on_run(self, p, used):
        p.slice += used
        self.vt[p.user] += used / self.weights.get(p.user, 1.0)

    def on_expire(self, p, t):
        self.queues[p.user].append(p)
        self.running = None

    def on_leave(self, p, t):
        self.running = None


POLICIES = {"fcfs": FCFS, "sjf": SJF, "prio": PRIO,
            "rr": RR, "mlfq": MLFQ, "fair": FAIR}


# ----------------------------------------------------------------------------
# Simulyator yadrosi
# ----------------------------------------------------------------------------
def simulate(procs, pol, cs=0.0):
    """Diskret-hodisali simulyatsiya. cs - bitta kontekstni almashtirish vaqti."""
    pending = deque(sorted(procs, key=lambda p: (p.arrival, p.pid)))
    blocked = []                                # (uyg'onish vaqti, pid, PCB)
    t, cur, last = 0.0, None, None
    gantt, switches, busy, overhead, done = [], 0, 0.0, 0.0, 0

    def make_ready(p, when):
        p.state, p.ready_since = "TAYYOR", when
        p.burst_ready, p.started = when, False
        pol.add(p, when)

    def admit(now):
        while pending and pending[0].arrival <= now + EPS:
            p = pending.popleft()
            make_ready(p, p.arrival)
        blocked.sort(key=lambda b: (b[0], b[1]))
        while blocked and blocked[0][0] <= now + EPS:
            wake, _, p = blocked.pop(0)
            make_ready(p, wake)
        pol.timer(now)

    def next_event():
        cands = [pol.next_timer(t)]
        if pending:
            cands.append(pending[0].arrival)
        if blocked:
            cands.append(min(b[0] for b in blocked))
        return min(cands)

    while done < len(procs):
        admit(t)
        if cur is None:                         # dispetcher: keyingi jarayon
            cur = pol.pick(t)
            if cur is None:                     # protsessor bo'sh turibdi
                nxt = next_event()
                if gantt and gantt[-1][2] == "-":
                    gantt[-1][1] = nxt
                else:
                    gantt.append([t, nxt, "-"])
                t = nxt
                continue
            if last is not None and cur is not last:
                switches += 1                   # kontekstni almashtirish
                if cs > 0:
                    gantt.append([t, t + cs, "CS"])
                    t += cs
                    overhead += cs
                    admit(t)
            cur.state, cur.slice = "BAJARILMOQDA", 0.0
            if cur.first_run is None:
                cur.first_run = t
            if not cur.started:
                cur.latency.append(t - cur.burst_ready)
                cur.started = True

        run = max(0.0, min(cur.left, pol.run_limit(cur), next_event() - t))
        if gantt and gantt[-1][2] == cur.pid and abs(gantt[-1][1] - t) < EPS:
            gantt[-1][1] = t + run
        else:
            gantt.append([t, t + run, cur.pid])
        t += run
        busy += run
        cur.left -= run
        pol.on_run(cur, run)
        admit(t)                # yangi kelganlar navbatga birinchi qo'yiladi

        if cur.left <= EPS:                     # CPU davri tugadi
            cur.idx += 1
            if cur.idx < len(cur.bursts):       # kiritish-chiqarishga o'tadi
                cur.state, cur.left = "KUTISH", cur.bursts[cur.idx]
                blocked.append((t + cur.io, cur.pid, cur))
            else:
                cur.state, cur.finish = "YAKUNLANGAN", t
                done += 1
            pol.on_leave(cur, t)
            last, cur = cur, None
        elif pol.run_limit(cur) <= EPS:         # vaqt kvanti tugadi
            cur.state, cur.ready_since = "TAYYOR", t
            pol.on_expire(cur, t)
            last, cur = cur, None
        elif pol.should_preempt(cur, t):        # majburiy almashtirish
            cur.state, cur.ready_since = "TAYYOR", t
            pol.on_preempt(cur, t)
            last, cur = cur, None
    return {"gantt": gantt, "switches": switches, "busy": busy,
            "overhead": overhead, "end": t}


# ----------------------------------------------------------------------------
# Samaradorlik ko'rsatkichlari
# ----------------------------------------------------------------------------
def metrics(procs, res):
    rows = []
    for p in procs:
        T = p.finish - p.arrival                # to'liq bajarilish vaqti
        W = T - p.cpu - p.io_total              # tayyor navbatda kutish
        R = p.first_run - p.arrival             # javob vaqti
        L = sum(p.latency) / len(p.latency)     # o'rtacha reaksiya vaqti
        rows.append((p, T, W, R, L))
    n = len(rows)
    span = res["end"] - min(p.arrival for p in procs)
    summ = {k: sum(r[i] for r in rows) / n
            for i, k in enumerate(("T", "W", "R", "L"), start=1)}
    summ.update(span=span, cs=res["switches"],
                util=100 * res["busy"] / span,
                ovh=100 * res["overhead"] / span, thr=n / span)
    return rows, summ


def user_shares(procs, gantt, window):
    """[0; window] oraliqda har bir foydalanuvchi olgan CPU ulushi, %."""
    owner = {p.pid: p.user for p in procs}
    use = {u: 0.0 for u in sorted(set(owner.values()))}
    for s, e, lab in gantt:
        if lab in owner and s < window:
            use[owner[lab]] += min(e, window) - s
    total = sum(use.values()) or 1.0
    return {u: 100 * v / total for u, v in use.items()}


def jain(values):
    """Jain adolatlilik indeksi: 1 - to'liq adolat, 1/n - eng yomon holat."""
    s = sum(values)
    return s * s / (len(values) * sum(v * v for v in values))


# ----------------------------------------------------------------------------
# Kiritish va chiqarish
# ----------------------------------------------------------------------------
def load(path):
    """Yuklama fayli: pid foydalanuvchi kelish ustuvorlik cpu[,cpu...] [io]
    "@weight foydalanuvchi og'irlik" qatori FAIR uchun og'irlik beradi."""
    specs, weights = [], {}
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.split("#")[0].strip()
            if not line:
                continue
            x = line.split()
            if x[0] == "@weight":
                weights[x[1]] = float(x[2])
                continue
            if len(x) not in (5, 6):
                sys.exit(f"{path}:{ln}: qator formati noto'g'ri")
            bursts = [float(b) for b in x[4].split(",")]
            io = float(x[5]) if len(x) == 6 else 0.0
            specs.append((x[0], x[1], float(x[2]), int(x[3]), bursts, io))
    return specs, weights


def fmt(v):
    return f"{round(v, 2):g}"


def print_gantt(gantt, width=96):
    segs = [g for g in gantt if g[1] - g[0] > EPS]
    lines, top, bot = [], "|", fmt(segs[0][0])
    for s, e, lab in segs:
        cell = "|" + lab.center(max(len(lab) + 2, len(fmt(e)) + 2, 5))
        if len(top) + len(cell) > width:
            lines += [top, bot, ""]
            top, bot = "|", fmt(s)
        top = top[:-1] + cell + "|"
        bot = bot.ljust(len(top) - 1) + fmt(e)
    print("\n".join(lines + [top, bot]))


def run_once(specs, args, alg, q=None):
    a = argparse.Namespace(**vars(args))
    if q is not None:
        a.q = q
    procs = [PCB(*s) for s in specs]
    res = simulate(procs, POLICIES[alg](a), args.cs)
    rows, summ = metrics(procs, res)
    return procs, res, rows, summ


def shares_line(procs, res, args):
    sh = user_shares(procs, res["gantt"], args.window)
    norm = [v / args.weights.get(u, 1.0) for u, v in sh.items()]
    txt = ", ".join(f"{u}: {v:.1f}%" for u, v in sh.items())
    return txt, jain(norm)


def main():
    ap = argparse.ArgumentParser(
        description="Protsessorni rejalashtirish algoritmlari simulyatori")
    ap.add_argument("fayl", help="yuklama fayli")
    ap.add_argument("-a", "--alg", default="rr", choices=POLICIES)
    ap.add_argument("-q", type=float, default=4, help="vaqt kvanti")
    ap.add_argument("-s", "--cs", type=float, default=0.0,
                    help="kontekstni almashtirish vaqti")
    ap.add_argument("--levels", type=int, default=3, help="MLFQ darajalari")
    ap.add_argument("--boost", type=float, default=0,
                    help="MLFQ ustuvorlikni tiklash davri (0 - yo'q)")
    ap.add_argument("--aging", type=float, default=0, help="PRIO qarish qadami")
    ap.add_argument("--window", type=float, default=0,
                    help="foydalanuvchi ulushlari uchun [0; W] oraliq")
    ap.add_argument("--compare", action="store_true",
                    help="barcha algoritmlarni taqqoslash")
    ap.add_argument("--sweep", help="kvant qiymatlari, masalan 1,2,4,8")
    ap.add_argument("--gantt", action="store_true", help="Gant diagrammasi")
    args = ap.parse_args()
    specs, args.weights = load(args.fayl)
    head = (f"{'':6}{'T_ort':>8}{'W_ort':>8}{'R_ort':>8}{'Reak':>8}"
            f"{'CS':>6}{'CPU%':>7}{'Xar%':>6}{'Ish':>8}")

    def row(name, s):
        return (f"{name:6}{s['T']:8.2f}{s['W']:8.2f}{s['R']:8.2f}{s['L']:8.2f}"
                f"{s['cs']:6d}{s['util']:7.1f}{s['ovh']:6.1f}{s['span']:8.1f}")

    if args.compare or args.sweep:
        print(head + ("   Jain" if args.window else ""))
        items = ([(a, None, a.upper()) for a in POLICIES] if args.compare else
                 [(args.alg, float(v), f"q={v}") for v in args.sweep.split(",")])
        for alg, q, name in items:
            procs, res, _, s = run_once(specs, args, alg, q)
            extra = f"{shares_line(procs, res, args)[1]:7.3f}" if args.window else ""
            print(row(name, s) + extra)
        return

    procs, res, rows, s = run_once(specs, args, args.alg)
    quant = f", q={fmt(args.q)}" if args.alg in ("rr", "mlfq", "fair") else ""
    print(f"Algoritm: {args.alg.upper()}{quant}, "
          f"kontekst almashtirish vaqti={fmt(args.cs)}")
    print(f"{'PID':6}{'Foyd.':8}{'Kelish':>7}{'CPU':>6}{'Tugash':>8}"
          f"{'T':>7}{'W':>7}{'R':>7}{'Reak':>7}")
    for p, T, W, R, L in rows:
        print(f"{p.pid:6}{p.user:8}{fmt(p.arrival):>7}{fmt(p.cpu):>6}"
              f"{fmt(p.finish):>8}{fmt(T):>7}{fmt(W):>7}{fmt(R):>7}{fmt(L):>7}")
    print(head)
    print(row("O'rt.", s))
    print(f"O'tkazuvchanlik: {s['thr']:.3f} jarayon/vaqt birligi")
    if args.window:
        txt, j = shares_line(procs, res, args)
        print(f"[0; {fmt(args.window)}] oraliqdagi CPU ulushlari: {txt}; "
              f"Jain indeksi = {j:.3f}")
    if args.gantt:
        print("Gant diagrammasi:")
        print_gantt(res["gantt"])


if __name__ == "__main__":
    main()
