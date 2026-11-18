"""레포 루트의 test_*.json을 index.html의 SAMPLES 상수에 다시 넣습니다.

사용법: python tools/vizier-mock/sync_samples.py
"""
import json
import re
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[1]
html_path = here / "index.html"

samples = {
    p.stem.removeprefix("test_"): json.loads(p.read_text(encoding="utf-8"))
    for p in sorted(root.glob("test_*.json"))
}
line = "const SAMPLES = " + json.dumps(samples, ensure_ascii=False) + ";"
html = html_path.read_text(encoding="utf-8")
html, n = re.subn(r"^const SAMPLES = .*;$", lambda _: line, html, count=1, flags=re.M)
if n != 1:
    raise SystemExit("index.html에서 SAMPLES 줄을 찾지 못했습니다")
html_path.write_text(html, encoding="utf-8")
print(f"샘플 {len(samples)}개 반영: {', '.join(samples)}")
