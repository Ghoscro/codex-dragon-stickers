"""Select bundled stickers; runtime uses only the standard library."""
import argparse
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Pools describe the reply's tone, rather than choosing indiscriminately from all PNGs.
TONES = {
    '收到': ['roger', 'okay', 'help'],
    '开工': ['working', 'writing', 'help', 'cheer'],
    '思考': ['thinking', 'writing', 'letter'],
    '犯难': ['stumped', 'thinking', 'confused'],
    '完成': ['done', 'ta-da', 'happy'],
    '开心': ['happy', 'excited', 'okay'],
    '陪伴': ['tea', 'happy', 'welcome'],
    '喜欢': ['love', 'heart-eyes', 'shy', 'hug-heart', 'treasure'],
    '安慰': ['touched', 'hug-heart', 'help'],
    '加油': ['cheer', 'help', 'excited'],
    '招呼': ['hello', 'welcome'],
    '早安': ['morning', 'hello', 'welcome'],
    '晚安': ['goodnight', 'sleepy', 'rest'],
    '休息': ['tea', 'rest', 'sleepy'],
}
ALIASES = {'好的': '收到', '工作': '开工', '分析': '思考', '困难': '犯难',
           '展示': '完成', '爱心': '喜欢', '打招呼': '招呼', '你好': '招呼'}


def state_path():
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'state')
    return base / 'codex-dragon-stickers' / 'recent.json'


def read_recent(path):
    try:
        recent = json.loads(path.read_text(encoding='utf-8')).get('recent', [])
        return [value for value in recent if isinstance(value, str)][:3] if isinstance(recent, list) else []
    except (OSError, ValueError, AttributeError):
        return []


def save_recent(path, recent):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Runtime state stays outside the installed Skill; interrupted writes keep the old state intact.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.recent-', suffix='.tmp', delete=False) as handle:
        temporary = Path(handle.name)
        json.dump({'recent': recent[:3]}, handle, ensure_ascii=False)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def choose_auto(items, query, recent, avoid):
    tone = ALIASES.get(query, query)
    if tone not in TONES:
        raise ValueError('auto 需要语气：' + '、'.join(TONES))
    pool = [item for item in items if item['id'] in TONES[tone]]
    explicit = []
    for token in avoid:
        matches = [item for item in items if score(item, token) == 100]
        if not matches:
            raise ValueError(f'未知排除表情：{token}')
        explicit.append(matches[0]['id'])
    excluded = set(recent + explicit)
    candidates = [item for item in pool if item['id'] not in excluded]
    if not candidates:
        # Small pools may need older stickers again; the latest visible sticker takes priority.
        latest = explicit[0] if explicit else (recent[0] if recent else None)
        candidates = [item for item in pool if item['id'] != latest]
    if not candidates:
        raise ValueError('当前语气没有可用的不同表情')
    return secrets.choice(candidates)


def score(item, query):
    q = query.strip().casefold()
    if q in (str(item['number']), f"{item['number']:02}", item['id'].casefold(), item['label'].casefold()):
        return 100
    if q in [word.casefold() for word in item['keywords']]:
        return 90
    return 10 if q and any(q in word.casefold() for word in [item['id'], item['label'], *item['keywords']]) else 0


def main():
    parser = argparse.ArgumentParser(description='Codex 龙娘表情选择器')
    parser.add_argument('command', choices=['auto', 'pick', 'list', 'gallery'])
    parser.add_argument('query', nargs='?', default='')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--avoid', default='', help='最近发过的编号/ID/名称，逗号分隔，最新在前')
    parser.add_argument('--state-file', type=Path, default=None, help='可选的会话独立去重记录路径')
    args = parser.parse_args()
    if args.command == 'gallery':
        print((ROOT / 'assets/gallery.html').as_posix())
        return 0
    items = json.loads((ROOT / 'assets/catalog.json').read_text(encoding='utf-8'))['stickers']
    if args.command == 'list':
        items = [i for i in items if not args.query or score(i, args.query)]
        if args.json:
            print(json.dumps(items, ensure_ascii=False))
        else:
            for item in items:
                print(f"{item['number']:02}  {item['label']}  ({item['id']})")
        return 0
    if not args.query.strip():
        parser.error('auto 需要语气；pick 需要表情名称或编号；用 list 查看全部表情')
    recent_path = args.state_file if args.state_file is not None else state_path()
    recent = []
    if args.command == 'auto':
        recent = read_recent(recent_path)
        try:
            item = choose_auto(items, args.query.strip(), recent,
                               [value.strip() for value in args.avoid.split(',') if value.strip()])
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
    else:
        ranked = sorted(((score(i, args.query), i) for i in items), key=lambda entry: -entry[0])
        if not ranked[0][0]:
            print(f'没有找到表情：{args.query}；请用 list 查看可选表情。', file=sys.stderr)
            return 2
        item = ranked[0][1]
    path = (ROOT / 'assets' / item['file']).resolve()
    if not path.is_file():
        print(f'图片缺失：{path}', file=sys.stderr)
        return 3
    if args.command == 'auto':
        try:
            save_recent(recent_path, [item['id'], *[value for value in recent if value != item['id']]])
        except OSError as error:
            print(f'保存去重记录失败：{error}', file=sys.stderr)
            return 4
    markdown = f"![Codex龙娘·{item['label']}]({path.as_posix()})"
    print(json.dumps({**item, 'path': path.as_posix(), 'markdown': markdown}, ensure_ascii=False) if args.json else markdown)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
