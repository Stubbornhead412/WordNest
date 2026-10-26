"""
笔记路由

- /notes                    笔记页（列表 + 编辑器）
- /notes/api/list           列表 / 搜索
- /notes/api/get/<id>       单条
- /notes/api/create         新建
- /notes/api/update/<id>    更新
- /notes/api/delete/<id>    删除
"""
from flask import Blueprint, jsonify, render_template, request

from services.notes_service import NotesService

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/notes')
def notes_page():
    """笔记页；支持 ?word=xxx 预填关联单词（从单词卡"记笔记"跳过来）"""
    return render_template('notes.html', prefill_word=(request.args.get('word') or '').strip())


@notes_bp.route('/notes/api/list')
def api_list():
    q = request.args.get('q', '')
    word = request.args.get('word', '')
    notes = NotesService.list_notes(q=q, word=word)
    return jsonify({
        'notes': [n.to_dict() for n in notes],
        'count': NotesService.count(),
    })


@notes_bp.route('/notes/api/get/<int:note_id>')
def api_get(note_id):
    note = NotesService.get(note_id)
    if not note:
        return jsonify({'error': '笔记不存在'}), 404
    return jsonify({'note': note.to_dict()})


@notes_bp.route('/notes/api/create', methods=['POST'])
def api_create():
    data = request.get_json(silent=True) or {}
    note, err = NotesService.create(
        content=data.get('content', ''),
        title=data.get('title', ''),
        word=data.get('word', ''),
        tags=data.get('tags', ''),
    )
    if err:
        return jsonify({'error': err}), 400
    return jsonify({'success': True, 'note': note.to_dict()})


@notes_bp.route('/notes/api/update/<int:note_id>', methods=['POST'])
def api_update(note_id):
    data = request.get_json(silent=True) or {}
    fields = {k: data[k] for k in ('content', 'title', 'word', 'tags') if k in data}
    note, err = NotesService.update(note_id, **fields)
    if err:
        return jsonify({'error': err}), 400 if '不存在' not in err else 404
    return jsonify({'success': True, 'note': note.to_dict()})


@notes_bp.route('/notes/api/delete/<int:note_id>', methods=['POST'])
def api_delete(note_id):
    if NotesService.delete(note_id):
        return jsonify({'success': True})
    return jsonify({'error': '删除失败（笔记可能已不存在）'}), 404
