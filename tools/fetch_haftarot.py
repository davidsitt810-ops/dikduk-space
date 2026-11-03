"""The Sephardic haftarah of every parasha, from Sefaria's calendar (custom=sephardi): every Shabbat from Bereshit 5787 for
five years; per parasha the haftarot seen and how often (a special Shabbat — Rosh Hodesh, Shekalim... — replaces the
parasha's own some years, so the most frequent is the parasha's). Also the Ashkenazi one, as a second candidate.
writes haftarot_calendar.json"""
import json, time, datetime, collections, requests, sys
S = requests.Session(); S.headers.update({'User-Agent': 'Mozilla/5.0 (pizmonim dikduk checker)'})
seen = {'sephardi': collections.defaultdict(collections.Counter), 'ashkenazi': collections.defaultdict(collections.Counter)}
d = datetime.date(2026, 10, 10); end = datetime.date(2031, 10, 1)
while d < end:
    for custom in ('sephardi', 'ashkenazi'):
        for attempt in range(3):
            try:
                r = S.get('https://www.sefaria.org/api/calendars', params={'custom': custom, 'year': d.year, 'month': d.month, 'day': d.day, 'diaspora': 1}, timeout=60)
                items = r.json().get('calendar_items', []); break
            except Exception as e:
                time.sleep(3); items = []
        par = [i['displayValue']['en'] for i in items if i.get('title', {}).get('en') == 'Parashat Hashavua']
        haf = [i['ref'] for i in items if i.get('title', {}).get('en', '').startswith('Haftarah')]
        if par: seen[custom][par[0]][' | '.join(haf)] += 1
        time.sleep(0.25)
    d += datetime.timedelta(days=7)
out = {c: {p: v.most_common() for p, v in m.items()} for c, m in seen.items()}
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else 'haftarot_calendar.json', 'w'), indent=1, ensure_ascii=False)
for p, v in out['sephardi'].items(): print(f'{p:28s} {v[:3]}')
