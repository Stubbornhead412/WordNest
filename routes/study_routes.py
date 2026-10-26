"""
学习记录路由

- /study_log            学习记录页（统计 + 时间序列图 + 按天目录）
- /study_log/review     开始"复习某一天"
- /study_log/review/end 退出复习模式
"""
from flask import Blueprint, jsonify, redirect, render_template, request, session

from services.study_service import StudyService

study_bp = Blueprint('study', __name__)


@study_bp.route('/study_log')
def study_log():
    """学习记录页"""
    series = StudyService.daily_series(30)
    days = StudyService.days_with_words(60)
    summary = StudyService.summary()
    max_count = max([p['count'] for p in series] + [1])

    review_date = session.get('review_date')
    # 只把日期存进 session（Cookie 上限 4KB，存整份词表会溢出），词表按需查询
    review_count = len(StudyService.word_texts_for_day(review_date)) if review_date else 0

    return render_template(
        'study_log.html',
        series=series,
        days=days,
        summary=summary,
        max_count=max_count,
        review_date=review_date,
        review_count=review_count,
        has_record=bool(days),
    )


@study_bp.route('/study_log/review', methods=['POST'])
def start_review():
    """把某一天学过的单词设为本次抽查范围"""
    data = request.get_json(silent=True) or {}
    day = (data.get('date') or request.form.get('date') or '').strip()

    words = StudyService.word_texts_for_day(day)
    if not words:
        return jsonify({'error': '这一天没有学习记录'}), 400

    # 只记日期，词表在抽查时按需查询，避免 Cookie 超出 4KB
    session['review_date'] = day
    session.pop('review_words', None)

    # 换复习日期时清掉旧的复习轮次状态（不然数据库里会越积越多）
    try:
        from services.cycle_service import CycleService
        CycleService.clear_pools_like('review|')
    except Exception:
        pass

    return jsonify({'success': True, 'count': len(words), 'date': day})


@study_bp.route('/study_log/review/end', methods=['POST', 'GET'])
def end_review():
    """退出复习模式，回到全部单词"""
    session.pop('review_words', None)
    session.pop('review_date', None)
    if request.method == 'GET':
        return redirect('/')
    return jsonify({'success': True})
