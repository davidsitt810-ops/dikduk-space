"""The student's own vowel ear (v5.7, his choice): his first clear, fully right takes teach a copy of the shipped vowel
head his voice, and his later takes are heard with it (the hazzan's line keeps the shipped head).

What was measured (LAB_NOTES §32-33, §39): 30 of a reader's pesukim, x5, with 300 of Rabbi Alouf's to anchor, 6 epochs
from the shipped head: on a reader the checker never heard, false vowel notes on his correct reading down a third
(Faraj Samra 2.5% -> 1.7%) or a quarter (Shmuelof 0.8% -> 0.6%), every kind of real mistake told as often or more.
A mistake he makes every time would be learned as his voice: safe3 (§33) relabels a confusion that is his USUAL way of
saying a vowel (at least half its clearly heard slots) to what the shipped head hears, so the head keeps hearing it
and the page keeps telling him; a sometimes-confusion is his voice wobbling, and is learned. On a phone in a room no
gain was shown (§39: calibrated on recordings or on the phone, no false note fewer on 1,083 words), so it is offered,
not imposed: he can switch it off, or have it forgotten.

Files under <keep dir>/students/<id>/: items.jsonl (one line per kept take: words, pron, the shipped head's vowel slots,
frames, time), items/<n>.npz (the take's Arabic layer-12 features as int8 with a scale per frame), head.pt (his head),
status.json. Rabbi Alouf's anchor pesukim are made once from the server's own Tehillim audio, in students/_anchor/."""
import os, re, json, time, random, shutil, threading, collections
import numpy as np
import torch, torch.nn as nn

N_READY = 30      # takes kept before his head can be made (30 pesukim, about 4½ minutes of reading; 10 gave half the gain)
N_MAX = 40        # kept at most (a few to spare: a take whose labels do not fit the frames is left out of training)
W_STUDENT = 5     # his takes x5 ...
N_ANCHOR = 300    # ... with 300 of Rabbi Alouf's pesukim
EPOCHS, LR, BS = 6, 3e-4, 12
USUAL = 0.5       # safe3: a confusion in at least half of a vowel's clearly heard slots is his usual way: not learned
MAX_STUDENTS = 100   # voices one server keeps at most: /check is open to anyone, so a new id stops here. A voice is
                     # about 27 MB (40 takes' features 16, his head 10.5): 2.7 GB at most, and Rabbi Alouf's anchor 117 MB once
ID_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')
VOWELS = 'AEIOU'

def ok_id(sid): return bool(sid) and bool(ID_RE.match(sid))

class Students:
    def __init__(self, root, head_cls, sym, shipped_path, clear, pron_of, durable=True):
        """root: the folder; head_cls: the head's class (app.LetterHead); sym: the vowel head's symbols; shipped_path:
           the shipped vowel head; clear(slot, ratio): vowels.clear; pron_of(nikud) -> the pronounced words with their
           vowel classes, as the training manifests write them; durable: this server's disk keeps it across restarts"""
        self.root = os.path.join(root, 'students'); os.makedirs(self.root, exist_ok=True)
        self.Head, self.sym, self.shipped, self.clear, self.pron_of = head_cls, list(sym), shipped_path, clear, pron_of
        self.s2i = {c: i for i, c in enumerate(self.sym)}
        self.lock = threading.Lock(); self.train_lock = threading.Lock(); self.heads = collections.OrderedDict()
        self.job = None   # the one training under way: {'id', 'stage', 't'}
        self.durable = bool(durable)

    # ------------------------------------------------------------------ files
    def dir(self, sid): return os.path.join(self.root, sid)
    def _items(self, sid):
        p = os.path.join(self.dir(sid), 'items.jsonl')
        return [json.loads(l) for l in open(p, encoding='utf-8')] if os.path.exists(p) else []
    def _status(self, sid):
        p = os.path.join(self.dir(sid), 'status.json')
        try: return json.load(open(p, encoding='utf-8'))
        except Exception: return {}
    def _set_status(self, sid, **kw):
        st = {**self._status(sid), **kw}; os.makedirs(self.dir(sid), exist_ok=True)
        tmp = os.path.join(self.dir(sid), 'status.json.tmp'); json.dump(st, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False); os.replace(tmp, os.path.join(self.dir(sid), 'status.json'))
        return st

    def n_students(self):
        try: return sum(1 for d in os.listdir(self.root) if not d.startswith('_') and os.path.isdir(os.path.join(self.root, d)))
        except Exception: return 0

    def status(self, sid):
        """what the page shows: how many takes are kept, whether his head is made and in use, what it did not learn"""
        st = self._status(sid); n = len(self._items(sid)); trained = os.path.exists(os.path.join(self.dir(sid), 'head.pt'))
        job = self.job if self.job and self.job.get('id') == sid else None
        state = 'training' if job else 'trained' if trained else 'failed' if st.get('error') else 'ready' if n >= N_READY else 'enrolling'
        return {'id': sid, 'kept': n, 'need': N_READY, 'state': state, 'on': bool(trained and st.get('on', True)), 'stage': job.get('stage') if job else None,
                'not_learned': st.get('not_learned', []), 'learned': st.get('learned', []), 'trained_at': st.get('trained_at'), 'error': st.get('error'), 'kept_here': self.durable,
                'room': os.path.isdir(self.dir(sid)) or self.n_students() < MAX_STUDENTS}

    # ------------------------------------------------------------------ enrollment
    def keep(self, sid, h12, nikud, words, take_words, summary):
        """keep one take as his training item when it is clear (the letter head's median >= .7), every word came through,
           and the line has nikud; -> True when kept. h12: the take's Arabic layer 12 (frames x 1024)"""
        if not ok_id(sid) or not nikud or h12 is None: return False
        # every word right ('' is a word too short to judge, like יה or הוא: on Faraj's correct reading 44 of 660 clear
        # takes have one, so it does not keep a take out)
        if not summary.get('clean') or summary.get('line_wrong') or summary.get('no_speech') or any(m not in ('ok', '', None) for m in summary.get('marks') or []): return False
        if os.path.exists(os.path.join(self.dir(sid), 'head.pt')): return False   # made: a new enrollment starts with forget
        if not os.path.isdir(self.dir(sid)) and self.n_students() >= MAX_STUDENTS: return False
        pron = self.pron_of(nikud)
        if not pron or len(pron) != len(words): return False
        y = [self.s2i[c] for c in ' '.join(pron) if c in self.s2i]
        if not y or h12.shape[0] <= 2 * len(y): return False
        slots = [[{'heard': s['heard'], 'mass': s['mass']} for s in (w.get('vow') or [])] for w in take_words]
        with self.lock:
            items = self._items(sid)
            if len(items) >= N_MAX: return False
            d = self.dir(sid); os.makedirs(os.path.join(d, 'items'), exist_ok=True); n = len(items)
            sc = np.maximum(np.abs(h12).max(1), 1e-6).astype(np.float32)
            np.savez(os.path.join(d, 'items', f'{n}.npz'), h12q=np.round(h12 / sc[:, None] * 127).astype(np.int8), h12s=sc.astype(np.float16))
            with open(os.path.join(d, 'items.jsonl'), 'a', encoding='utf-8') as f:
                f.write(json.dumps({'n': n, 'words': list(words), 'pron': pron, 'slots': slots, 'T': int(h12.shape[0]), 't': int(time.time())}, ensure_ascii=False) + '\n')
        return True

    # ------------------------------------------------------------------ safe3
    def labels(self, items):
        """safe3 (§33): each item's pron, with a confusion that is his usual way of saying a vowel (>= half of that
           vowel's clearly heard slots, by the shipped head) relabeled to what the head hears -> (prons, not learned, learned)"""
        seen = []
        for it in items:
            for i, (p, sl) in enumerate(zip(it['pron'], it['slots'])):
                pv = [c for c in p if c in VOWELS]
                if len(sl) != len(pv): continue
                for j, (s, c) in enumerate(zip(sl, pv)): seen.append((it['n'], i, j, c, s['heard'], self.clear(s, 2.0)))
        n_c = collections.Counter(c for *_, c, h, cl in seen)
        f = collections.Counter((c, h) for *_, c, h, cl in seen if h != c and cl)
        usual = {(c, h) for (c, h), k in f.items() if n_c[c] < 10 or k >= USUAL * n_c[c]}
        out = {it['n']: [list(p) for p in it['pron']] for it in items}
        for n, i, j, c, h, cl in seen:
            if h != c and cl and (c, h) in usual:
                w = out[n][i]; k = [q for q, ch in enumerate(w) if ch in VOWELS][j]; w[k] = h
        prons = {n: [''.join(w) for w in ws] for n, ws in out.items()}
        nl = [{'page': c, 'heard': h, 'slots': f[(c, h)], 'of': n_c[c]} for c, h in sorted(usual)]
        ln = [{'page': c, 'heard': h, 'slots': k, 'of': n_c[c]} for (c, h), k in f.most_common() if (c, h) not in usual and k >= 2]
        return prons, nl, ln

    # ------------------------------------------------------------------ training
    def _feat(self, path):
        d = np.load(path); return torch.from_numpy(d['h12q'].astype(np.float32) * (d['h12s'].astype(np.float32)[:, None] / 127))

    def train_async(self, sid, anchor):
        """start making his head in a thread (one training at a time on this server); anchor() -> [(npz path, pron)] of
           Rabbi Alouf's pesukim, made once. -> (started, reason)"""
        if not ok_id(sid): return False, 'bad id'
        if len(self._items(sid)) < N_READY: return False, f'{N_READY} clear takes are needed first'
        if os.path.exists(os.path.join(self.dir(sid), 'head.pt')): return False, 'already made'
        if not self.train_lock.acquire(blocking=False): return False, 'another voice is being learned: try again in a few minutes'
        self.job = {'id': sid, 'stage': 'starting', 't': time.time()}
        def run():
            try: self._train(sid, anchor)
            except Exception as e:
                self._set_status(sid, error=str(e)[:300]); print('student training failed:', sid, e, flush=True)
            finally:
                self.job = None; self.train_lock.release()
        threading.Thread(target=run, daemon=True).start()
        return True, 'started'

    def _train(self, sid, anchor):
        items = self._items(sid); prons, not_learned, learned = self.labels(items)
        self.job['stage'] = 'Rabbi Alouf\'s pesukim to anchor it'; A = anchor()
        data = []
        for it in items:
            y = [self.s2i[c] for c in ' '.join(prons[it['n']]) if c in self.s2i]
            if y and it['T'] > 2 * len(y): data += [(os.path.join(self.dir(sid), 'items', f"{it['n']}.npz"), y, it['T'])] * W_STUDENT
        for path, pron, T in A:
            y = [self.s2i[c] for c in ' '.join(pron) if c in self.s2i]
            if y and T > 2 * len(y): data.append((path, y, T))
        ck = torch.load(self.shipped, map_location='cpu'); model = self.Head(d_in=ck.get('d_in', 1024), n=len(self.sym)); model.load_state_dict(ck['state'])
        opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-2); ctc = nn.CTCLoss(blank=0, zero_infinity=True)
        steps = EPOCHS * (len(data) // BS + 1); sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=LR, total_steps=steps)
        rng = random.Random(zlib_seed(sid)); cache = {}
        def feat(p):
            if p not in cache: cache[p] = self._feat(p)
            return cache[p]
        for ep in range(EPOCHS):
            self.job['stage'] = f'learning: pass {ep + 1} of {EPOCHS}'; model.train()
            srt = sorted(data, key=lambda z: z[2]); bs = [srt[i:i + BS] for i in range(0, len(srt), BS)]; rng.shuffle(bs)
            for b in bs:
                xs = nn.utils.rnn.pad_sequence([feat(p) for p, _, _ in b], batch_first=True); xl = torch.tensor([T for _, _, T in b])
                ys = torch.cat([torch.tensor(y) for _, y, _ in b]); yl = torch.tensor([len(y) for _, y, _ in b])
                lp = torch.log_softmax(model(xs), -1).transpose(0, 1)
                loss = ctc(lp, ys, xl, yl); opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5.0); opt.step(); sched.step()
        model.eval(); tmp = os.path.join(self.dir(sid), 'head.pt.tmp')
        torch.save({'state': model.state_dict(), 'sym': self.sym, 'layer': 'h12', 'd_in': ck.get('d_in', 1024), 'mode': 'full', 'student': sid, 'items': len(items)}, tmp)
        os.replace(tmp, os.path.join(self.dir(sid), 'head.pt'))
        self._set_status(sid, on=True, trained_at=int(time.time()), not_learned=not_learned, learned=learned[:6], error=None)

    # ------------------------------------------------------------------ use
    def head(self, sid):
        """his head when it is made and switched on, else None (a few kept in memory)"""
        if not ok_id(sid): return None
        p = os.path.join(self.dir(sid), 'head.pt')
        if not os.path.exists(p) or not self._status(sid).get('on', True): return None
        with self.lock:
            m = self.heads.get(sid)
            if m is None or m[0] != os.path.getmtime(p):
                ck = torch.load(p, map_location='cpu'); h = self.Head(d_in=ck.get('d_in', 1024), n=len(ck['sym'])); h.load_state_dict(ck['state']); h.eval()
                m = (os.path.getmtime(p), h); self.heads[sid] = m
            self.heads.move_to_end(sid)
            while len(self.heads) > 8: self.heads.popitem(last=False)
            return m[1]

    def set_on(self, sid, on):
        if not ok_id(sid): return None
        self._set_status(sid, on=bool(on)); return self.status(sid)

    def forget(self, sid):
        """everything kept for him, gone (his request)"""
        if not ok_id(sid) or (self.job and self.job.get('id') == sid): return False
        with self.lock:
            self.heads.pop(sid, None); shutil.rmtree(self.dir(sid), ignore_errors=True)
        return True

def zlib_seed(s):
    import zlib; return zlib.crc32(s.encode())
