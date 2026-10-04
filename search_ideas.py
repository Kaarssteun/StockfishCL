"""Search the Fishtest index for earlier attempts at given ideas (regex on branch + info).
Usage: python search_ideas.py [csv]"""
import csv, re, sys
from collections import OrderedDict

path = sys.argv[1] if len(sys.argv) > 1 else r"D:\stockfish\fishtest_index\fishtest_index.csv"
IDEAS = OrderedDict([
    ("qsearch SEE with (capture) history",
     r"(qs|qsearch|quiescence).{0,40}(see).{0,40}(hist|capthist|capturehist)|(see).{0,40}(hist|capthist).{0,40}(qs|qsearch|quiescence)"),
    ("quiet TT move in qsearch",
     r"(qs|qsearch|quiescence).{0,50}(quiet).{0,30}(tt ?move|ttm)|(quiet).{0,30}(tt ?move|ttm).{0,50}(qs|qsearch|quiescence)|(tt ?move|ttm).{0,40}(qs|qsearch).{0,40}quiet"),
    ("correction history on losing captures",
     r"(corr|correction).{0,60}(losing|bad|negative see|see ?<).{0,30}captur|(losing|bad).{0,30}captur.{0,60}(corr|correction)"),
    ("history-adjusted LMP (late move pruning)",
     r"(lmp|late move prun|movecount prun|move ?count prun).{0,60}hist|hist.{0,60}(lmp|late move prun|movecount prun|move ?count prun)"),
    ("countermove fail-low bonus",
     r"(counter ?move|countermove|prior ?move|prev(ious)? ?move).{0,60}(fail.?low|faillow).{0,40}(bonus)?|(fail.?low|faillow).{0,60}(counter ?move|countermove|prior ?move|prevsq|prev(ious)? ?move)"),
])

rows = list(csv.DictReader(open(path, encoding="utf-8", newline="")))
print(f"{len(rows)} runs in index\n")
for name, pat in IDEAS.items():
    rx = re.compile(pat, re.I)
    hits = [r for r in rows if rx.search(r["branch"] + " " + r["info"])]
    print(f"== {name}: {len(hits)} runs")
    for r in sorted(hits, key=lambda r: r["start_time"], reverse=True)[:25]:
        res = r["result"]
        print(f"  {r['start_time'][:10]} {r['username'][:14]:14} {r['branch'][:28]:28} {r['tc']:>8} {res:9} "
              f"LLR {r['llr'] or '-':>6} elo {r['elo'] or '-':>6}±{r['elo_err95'] or '-':<5} g {r['games']:>6} | {r['info'][:70]}")
    print()
