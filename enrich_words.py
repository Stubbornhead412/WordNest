# -*- coding: utf-8 -*-
"""
给词库里"还没有例句"的单词批量补例句 + 记忆法（调用项目自带的 AI 接口）

用法：
    python enrich_words.py --limit 10          # 补前 10 个（先用小样本看效果）
    python enrich_words.py --limit 10 --dry-run # 只生成、不写库，先预览
    python enrich_words.py                     # 补全部（默认每批 100，可反复跑，已补过的会跳过）

说明：
- 走 HTTP 接口（/ai_fill_word、/edit_word），所以容器要在运行中；
- 只改两个字段：example（例句）、note（AI 记忆法 + 保留原音标）；你 CSV 里的
  词性和中文释义不会被覆盖；
- 已补过例句的词自动跳过，支持断点续跑。
"""
import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:5000"
DB = r"C:\Users\Asus\Documents\deepseek-harness\default-workspace\WordNest\instance\words.db"

PHONETIC_RE = re.compile(r"音标\s*/([^/]+)/")


def api(path, payload=None, method="GET", timeout=120):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def pending_words(limit, only_empty=True):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "select w.word, d.part_of_speech, d.meaning, coalesce(d.example,'') "
            "from word w join definition d on d.word_id = w.id order by w.id"
        ).fetchall()
    finally:
        con.close()
    if only_empty:
        rows = [r for r in rows if not r[3].strip()]
    return rows[:limit] if limit else rows


def pick_definition(ai_defs, want_pos):
    """按词性匹配 AI 返回的释义；匹配不到就用第一个"""
    want = {p.strip().strip(".").lower() for p in str(want_pos).split("/") if p.strip()}
    for d in ai_defs:
        pos = {p.strip().strip(".").lower() for p in str(d.get("part_of_speech", "")).split("/") if p.strip()}
        if want & pos:
            return d
    return ai_defs[0]


def merge_note(ai_note, old_note):
    """AI 记忆法 + 保留原音标"""
    ai_note = (ai_note or "").strip()
    m = PHONETIC_RE.search(old_note or "")
    phonetic = m.group(1).strip() if m else ""
    if phonetic and f"/{phonetic}/" not in ai_note:
        return f"{ai_note}（音标 /{phonetic}/）" if ai_note else f"音标 /{phonetic}/"
    return ai_note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100, help="本次处理多少个词（0=全部）")
    ap.add_argument("--sleep", type=float, default=0.3, help="每次调用之间的间隔秒数")
    ap.add_argument("--dry-run", action="store_true", help="只生成不写库")
    ap.add_argument("--all", action="store_true", help="包括已有例句的词（会覆盖）")
    args = ap.parse_args()

    st, _ = api("/api/lists")
    if st != 200:
        sys.exit("应用没在运行，请先 docker compose up -d")

    words = pending_words(args.limit, only_empty=not args.all)
    if not words:
        sys.exit("没有需要补例句的词（可能都补完了）")
    print(f"待处理 {len(words)} 个词，dry-run={args.dry_run}\n")

    ok = fail = 0
    t0 = time.time()
    for i, (word, pos, meaning, _old_example) in enumerate(words, 1):
        st, defs = api(f"/get_word_definition/{urllib.parse.quote(word)}")
        if st != 200 or not isinstance(defs, dict):
            print(f"[{i}/{len(words)}] {word}: 读取失败({st})")
            fail += 1
            continue
        current = defs.get("definitions", [])
        if not current:
            print(f"[{i}/{len(words)}] {word}: 无释义，跳过")
            fail += 1
            continue

        st, ai = api("/ai_fill_word", {"word": word}, method="POST")
        if st != 200 or "definitions" not in (ai or {}):
            print(f"[{i}/{len(words)}] {word}: AI 失败({st}) {str(ai)[:80]}")
            fail += 1
            time.sleep(args.sleep)
            continue

        picked = pick_definition(ai["definitions"], current[0]["part_of_speech"])
        example = (picked.get("example") or "").strip()
        note = merge_note(picked.get("note"), current[0].get("note", ""))

        # 只改 example / note，词性和中文释义保持 CSV 原样
        payload_defs = [{
            "part_of_speech": d.get("part_of_speech", ""),
            "meaning": d.get("meaning", ""),
            "example": example if idx == 0 else d.get("example", ""),
            "note": note if idx == 0 else d.get("note", ""),
        } for idx, d in enumerate(current)]

        if not args.dry_run:
            st, res = api(f"/edit_word/{urllib.parse.quote(word)}", {"word": word, "definitions": payload_defs}, method="POST")
            if st != 200:
                print(f"[{i}/{len(words)}] {word}: 写库失败({st}) {str(res)[:80]}")
                fail += 1
                continue

        ok += 1
        print(f"[{i}/{len(words)}] {word} ({pos}) {'[预览]' if args.dry_run else '✓'}")
        print(f"    释义: {meaning}")
        print(f"    例句: {example.replace(chr(10), ' / ')}")
        print(f"    笔记: {note}")
        print()
        time.sleep(args.sleep)

    print(f"完成：成功 {ok}，失败 {fail}，用时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
