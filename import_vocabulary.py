# -*- coding: utf-8 -*-
"""
把 vocabulary.csv 导入 WordNest 的默认词库（instance/words.db）

处理策略：
1. 备份现有 words.db 到 backup/ 目录（保证可回滚）
2. 把原有的 21 个示例词迁移到 instance/demo.db（变成独立的 "demo" 词表）
3. 清空 words.db，导入 CSV 中的单词
   - 单词/短语      -> word.word
   - 词性           -> definition.part_of_speech
   - 中文释义       -> definition.meaning
   - 音标           -> definition.note（前缀 "音标 /.../"；项目没有音标字段）
   - 例句           -> 留空，稍后可用 AI 一键填充
"""
import os
import shutil
import sqlite3
import csv
from datetime import datetime

ROOT = r"C:\Users\Asus\Documents\deepseek-harness\default-workspace\WordNest"
INST = os.path.join(ROOT, "instance")
SRC = r"C:\Users\Asus\Downloads\vocabulary.csv"
WORDS_DB = os.path.join(INST, "words.db")
DEMO_DB = os.path.join(INST, "demo.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS word (
    id INTEGER NOT NULL,
    word VARCHAR(100) NOT NULL,
    marked BOOLEAN,
    PRIMARY KEY (id),
    UNIQUE (word)
);
CREATE TABLE IF NOT EXISTS definition (
    id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    part_of_speech VARCHAR(20) NOT NULL,
    meaning TEXT NOT NULL,
    example TEXT,
    note TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY(word_id) REFERENCES word (id)
);
"""


def read_csv():
    with open(SRC, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    print("表头:", header)
    print("数据行数:", len(data))
    return header, data


def main():
    header, data = read_csv()

    # 1. 备份
    backup_dir = os.path.join(ROOT, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if os.path.exists(WORDS_DB):
        bak = os.path.join(backup_dir, f"words.db.{stamp}.bak")
        shutil.copy2(WORDS_DB, bak)
        print("已备份 ->", bak)

    src = sqlite3.connect(WORDS_DB)
    old = src.execute(
        "select w.id, w.word, w.marked, d.part_of_speech, d.meaning, d.example, d.note "
        "from word w left join definition d on d.word_id = w.id order by w.id"
    ).fetchall()
    src.close()
    print("原有单词数:", len({r[1] for r in old}))

    # 2. 迁移示例词到 demo.db
    if os.path.exists(DEMO_DB):
        os.remove(DEMO_DB)
    demo = sqlite3.connect(DEMO_DB)
    demo.executescript(SCHEMA)
    wid = {}
    for oid, w, marked, pos, meaning, example, note in old:
        if w not in wid:
            cur = demo.execute("insert into word (word, marked) values (?, ?)", (w, marked or 0))
            wid[w] = cur.lastrowid
        if pos:
            demo.execute(
                "insert into definition (word_id, part_of_speech, meaning, example, note) values (?,?,?,?,?)",
                (wid[w], pos, meaning, example, note),
            )
    demo.commit()
    n_demo = demo.execute("select count(*) from word").fetchone()[0]
    demo.close()
    print("已迁移到 demo.db 的示例词:", n_demo)

    # 3. 清空 words.db
    con = sqlite3.connect(WORDS_DB)
    con.executescript(SCHEMA)
    con.execute("delete from definition")
    con.execute("delete from word")
    con.commit()

    # 4. 导入 CSV
    seen, skipped_dup, no_phonetic, phrases = set(), [], 0, []
    imported = 0
    for row in data:
        if len(row) < 5:
            continue
        idx, word, phonetic, pos, meaning = row[0], row[1].strip(), row[2].strip(), row[3].strip(), row[4].strip()
        kind = row[5].strip() if len(row) > 5 else ""
        if not word:
            continue
        key = word.lower()
        if key in seen:
            skipped_dup.append(word)
            continue
        seen.add(key)

        phonetic = phonetic.strip("[]/ ")
        note = f"音标 /{phonetic}/" if phonetic else ""
        if not phonetic:
            no_phonetic += 1
        if kind == "短语" or " " in word:
            phrases.append(word)

        cur = con.execute("insert into word (word, marked) values (?, 0)", (word,))
        con.execute(
            "insert into definition (word_id, part_of_speech, meaning, example, note) values (?,?,?,?,?)",
            (cur.lastrowid, pos or "-", meaning, "", note),
        )
        imported += 1

    con.commit()
    total = con.execute("select count(*) from word").fetchone()[0]
    defs = con.execute("select count(*) from definition").fetchone()[0]
    sample = con.execute(
        "select w.word, d.part_of_speech, d.meaning, d.note from word w join definition d on d.word_id=w.id order by w.id limit 5"
    ).fetchall()
    con.close()

    print("\n=== 导入结果 ===")
    print("导入单词:", imported, "| 库内总数:", total, "| 释义条数:", defs)
    print("重复跳过:", skipped_dup if skipped_dup else "无")
    print("无音标:", no_phonetic, "| 短语数:", len(phrases), phrases[:5])
    print("样例:")
    for s in sample:
        print("  ", s)


if __name__ == "__main__":
    main()
