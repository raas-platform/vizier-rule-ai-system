"""
리포트 실측 스크립트 (실제 Anthropic 키 사용 → 과금 발생)

이미 떠 있는 서버(기본 http://localhost:8010)에 샘플마다
  1) POST /rules/validate-json  2) POST /rules/report/stream (md, html)
을 호출해 리포트 파일을 저장하고, 시간·토큰·비용과 이슈 번호 대조 결과를 summary.md로 남긴다.

    python tools/report_smoke.py --server http://localhost:8010 --out report-smoke-out
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ["all_errors_combined", "type_mismatch", "missing_condition", "new_rule"]


def stream_report(client, server, fmt, rule, validation, headers):
    t0 = time.monotonic()
    first = None
    parts, done, error = [], None, None
    skip_head = fmt == "html"
    with client.stream("POST", f"{server}/rules/report/stream", headers=headers,
                       json={"format": fmt, "rule": rule, "validation": validation}) as r:
        if r.status_code != 200:
            return None, {"error": f"HTTP {r.status_code}: {r.read().decode('utf-8', 'replace')}"}
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            if ev["type"] == "delta":
                if skip_head:
                    skip_head = False
                elif first is None:
                    first = time.monotonic() - t0
                parts.append(ev["text"])
            elif ev["type"] == "done":
                done = ev
            elif ev["type"] == "error":
                error = ev["message"]
    total = time.monotonic() - t0
    info = {"client_first_s": round(first, 2) if first else None, "client_total_s": round(total, 2)}
    if done:
        info.update(done)
    if error:
        info["error"] = error
    return "".join(parts), info


def sec(v):
    return f"{v:.2f}s" if isinstance(v, (int, float)) else "-"


def check_ids(text, validation):
    """본문+부록에 모든 이슈 번호가 2번 이상 나오고, 없는 번호는 없는지"""
    issues = validation.get("issues") or []
    n_err = sum(1 for i in issues if i.get("severity") == "error")
    expected = [f"E{k}" for k in range(1, n_err + 1)] + [f"W{k}" for k in range(1, len(issues) - n_err + 1)]
    found = re.findall(r"\b([EW]\d{1,3})\b", text)
    counts = {i: found.count(i) for i in expected}
    missing = [i for i, c in counts.items() if c < 2]
    extra = sorted(set(found) - set(expected))
    return {"expected": len(expected), "missing_or_once": missing, "extra": extra}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://localhost:8010")
    ap.add_argument("--out", default="report-smoke-out")
    ap.add_argument("--api-key", default=None, help="서버에 REPORT_API_KEY가 설정된 경우")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    headers = {"X-API-Key": args.api_key} if args.api_key else {}

    rows = []
    with httpx.Client(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
        for name in SAMPLES:
            rules = json.loads((ROOT / f"test_{name}.json").read_text(encoding="utf-8"))
            v = client.post(f"{args.server}/rules/validate-json", json=rules)
            v.raise_for_status()
            validation = v.json()
            (out / f"{name}.validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=1), encoding="utf-8")
            for fmt in ("md", "html"):
                text, info = stream_report(client, args.server, fmt, rules[0], validation, headers)
                if text:
                    (out / f"{name}.{fmt}").write_text(text, encoding="utf-8")
                    info["ids"] = check_ids(text, validation)
                info.update({"sample": name, "format": fmt, "issues": len(validation.get("issues") or [])})
                rows.append(info)
                print(json.dumps(info, ensure_ascii=False), flush=True)

    (out / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["| 샘플 | 형식 | 이슈 | 첫 글자(화면) | 첫 글자(서버) | 전체 | 입력/출력 토큰 | 비용 | 번호 대조 | 비고 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ids = r.get("ids") or {}
        ok = "-" if not ids else "OK" if ids and not ids["missing_or_once"] and not ids["extra"] else f'누락 {ids.get("missing_or_once")} 추가 {ids.get("extra")}'
        u = r.get("usage") or {}
        lines.append(
            f'| {r["sample"]} | {r["format"]} | {r["issues"]} | {sec(r.get("client_first_s"))} | '
            f'{sec(r.get("ttft_ms") and r["ttft_ms"] / 1000)} | {sec(r.get("client_total_s"))} | '
            f'{u.get("input_tokens", "-")}/{u.get("output_tokens", "-")} | ${r.get("cost_usd")} | {ok} | '
            f'{r.get("error") or r.get("warning") or r.get("model", "")} |')
    costs = [r["cost_usd"] for r in rows if r.get("cost_usd")]
    if costs:
        lines.append(f"\n총 비용 ${sum(costs):.4f}, 건당 평균 ${sum(costs) / len(costs):.4f} (공개 단가로 계산한 추정)")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if all(not r.get("error") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
