# -*- coding: utf-8 -*-
"""
把 CSV 词表导入 WordNest

用法（在项目根目录执行，需要本机有 Python 3.8+）：

    # 1) 最简单：CSV 放项目根目录
    python import_vocabulary.py --csv vocabulary.csv

    # 2) 导入成一个新的词表（不动现有数据，推荐）
    python import_vocabulary.py --csv my_words.csv --list cet4

    # 3) 覆盖已有词表（会先自动备份到 backup/）
    python import_vocabulary.py --csv my_words.csv --list words --replace

CSV 格式：带表头的 UTF-8 文件，建议列名如下（顺序无所谓，按表头识别）：

    序号,单词/短语,音标,词性,中文释义,类型,首字母

    1,abuse,əˈbjuːs,n./v.,滥用；虐待；辱骂,单词,a

最少只需要「单词」和「释义」两列；音标/词性/类型可缺省。

注意：导入前建议先停容器，避免 SQLite 写入竞争：
    docker compose stop
    python import_vocabulary.py --csv vocabulary.csv
    docker compose start
"""
import argparse
import csv
import io
import os
import shutil
import sqlite3
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.path.join(ROOT, 'instance')
BACKUP = os.path.join(ROOT, 'backup')

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

# 表头别名 → 内部字段
HEADER_ALIASES = {
    'word': ['单词/短语', '单词', 'word', '英文', '词汇'],
    'phonetic': ['音标', 'phonetic', '发音'],
    'pos': ['词性', 'part_of_speech', 'pos'],
    'meaning': ['中文释义', '释义', 'meaning', '中文', '翻译'],
    'kind': ['类型', 'kind', 'type'],
}


def detect_columns(header):
    """根据表头文字找到各列下标"""
    idx = {}
    for col, aliases in HEADER_ALIASES.items():
        for i, name in enumerate(header):
            clean = (name or '').strip().lower()
            if clean in [a.lower() for a in aliases]:
                idx[col] = i
                break
    return idx


def read_csv(path):
    if not os.path.exists(path):
        sys.exit(f'找不到 CSV 文件: {path}\n提示：把文件放到项目根目录，或用 --csv 指定完整路径。')

    # Excel 在中文 Windows 上默认导出 GBK 编码，所以要逐个编码尝试
    text, used = None, None
    for encoding in ('utf-8-sig', 'utf-8', 'gb18030', 'gbk'):
        try:
            with open(path, 'r', encoding=encoding, newline='') as f:
                text = f.read()
            used = encoding
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        sys.exit('无法识别 CSV 的编码（已尝试 UTF-8 / GBK）。\n'
                 '请在 Excel 里用「另存为 → CSV UTF-8（逗号分隔）」重新导出后重试。')

    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        sys.exit('CSV 是空的')
    header, data = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
    cols = detect_columns(header)
    if 'word' not in cols or 'meaning' not in cols:
        sys.exit(f'CSV 表头里找不到「单词」或「释义」列。\n实际表头: {header}\n'
                 f'建议表头: 序号,单词/短语,音标,词性,中文释义,类型,首字母')
    print(f'CSV: {path}（编码 {used}）')
    print(f'表头: {header}')
    print(f'识别到列: {cols}')
    print(f'数据行数: {len(data)}')
    return cols, data


def main():
    ap = argparse.ArgumentParser(description='把 CSV 词表导入 WordNest')
    ap.add_argument('--csv', default=os.path.join(ROOT, 'vocabulary.csv'),
                    help='CSV 文件路径（默认：项目根目录下的 vocabulary.csv）')
    ap.add_argument('--list', default='words', help='导入到哪个词表（默认 words，会出现在网页右上角列表里）')
    ap.add_argument('--replace', action='store_true',
                    help='目标词表已有单词时：先备份、清空，再导入')
    args = ap.parse_args()

    cols, data = read_csv(args.csv)

    os.makedirs(INSTANCE, exist_ok=True)
    target_db = os.path.join(INSTANCE, f'{args.list}.db')

    # 已有数据检查
    existing = 0
    if os.path.exists(target_db):
        con = sqlite3.connect(target_db)
        con.executescript(SCHEMA)
        existing = con.execute('select count(*) from word').fetchone()[0]
        con.close()
    if existing and not args.replace:
        sys.exit(f'词表 [{args.list}] 里已经有 {existing} 个单词，为安全起见不覆盖。\n'
                 f'想覆盖请加 --replace（会自动备份），或换一个 --list 名字，例如 --list cet4')

    # 备份
    if os.path.exists(target_db):
        os.makedirs(BACKUP, exist_ok=True)
        bak = os.path.join(BACKUP, f'{args.list}.db.{datetime.now():%Y%m%d-%H%M%S}.bak')
        shutil.copy2(target_db, bak)
        print('已备份 ->', bak)

    con = sqlite3.connect(target_db)
    con.executescript(SCHEMA)
    con.execute('delete from definition')
    con.execute('delete from word')
    con.commit()

    seen, dup, no_phonetic, phrases, imported = set(), [], 0, [], 0
    for row in data:
        def cell(key):
            i = cols.get(key)
            if i is None or i >= len(row):
                return ''
            return (row[i] or '').strip()

        word = cell('word')
        if not word:
            continue
        key = word.lower()
        if key in seen:
            dup.append(word)
            continue
        seen.add(key)

        phonetic = cell('phonetic').strip('[]/ ')
        note = f'音标 /{phonetic}/' if phonetic else ''
        if not phonetic:
            no_phonetic += 1
        if cell('kind') == '短语' or ' ' in word:
            phrases.append(word)

        cur = con.execute('insert into word (word, marked) values (?, 0)', (word,))
        con.execute(
            'insert into definition (word_id, part_of_speech, meaning, example, note) '
            'values (?,?,?,?,?)',
            (cur.lastrowid, cell('pos') or '-', cell('meaning'), '', note),
        )
        imported += 1

    con.commit()
    total = con.execute('select count(*) from word').fetchone()[0]
    sample = con.execute(
        'select w.word, d.part_of_speech, d.meaning, d.note from word w '
        'join definition d on d.word_id = w.id order by w.id limit 5').fetchall()
    con.close()

    print('\n=== 导入结果 ===')
    print(f'词表: {args.list} -> instance/{args.list}.db')
    print(f'导入单词: {imported} | 库内总数: {total}')
    print('重复跳过:', dup if dup else '无')
    print(f'无音标: {no_phonetic} | 短语: {len(phrases)}')
    print('样例:')
    for s in sample:
        print('  ', s)
    print('\n下一步：')
    print('  1) docker compose start           # 如果刚才停了容器')
    print('  2) 浏览器打开 http://localhost:5000 ，右上角可切换词表')
    print('  3) 想让 AI 批量补例句/记忆法：python enrich_words.py --limit 10 --dry-run')


if __name__ == '__main__':
    main()
