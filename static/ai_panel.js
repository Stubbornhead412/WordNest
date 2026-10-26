/* 左侧四级冲刺助教侧栏：对话 + 快速选词复制 */
(function () {
    'use strict';

    var panel = document.getElementById('aiCoach');
    if (!panel) return;

    var KEY_HISTORY = 'wordnest_ai_coach_history_v1';
    var KEY_OPEN = 'wordnest_ai_coach_open_v1';
    var KEY_WIDTH = 'wordnest_ai_coach_width_v1';

    var elToggle = document.getElementById('aiCoachToggle');
    var elCollapse = document.getElementById('aiCoachCollapse');
    var elClear = document.getElementById('aiCoachClear');
    var elWide = document.getElementById('aiCoachWide');
    var elResizer = document.getElementById('aiCoachResizer');
    var elRefresh = document.getElementById('aiRefreshWords');
    var elRefreshDot = document.getElementById('aiRefreshDot');
    var elMessages = document.getElementById('aiCoachMessages');
    var elForm = document.getElementById('aiCoachForm');
    var elInput = document.getElementById('aiCoachInput');
    var elSend = document.getElementById('aiCoachSend');
    var elQuick = document.getElementById('aiCoachQuick');
    var elWordList = document.getElementById('aiWordList');
    var elTabToday = document.getElementById('aiTabToday');
    var elTabMarked = document.getElementById('aiTabMarked');
    var elCopyAll = document.getElementById('aiCopyAll');
    var elToast = document.getElementById('aiToast');

    var QUICK_PROMPTS = [
        { label: '翻译练习', text: '给我 2 道四级汉译英小练习（一句话一句子），先只给题目，我做完你再批改。' },
        { label: '语法辨析', text: '讲讲四级高频语法点，挑一个我容易错的，用例子说明并出一道题。' },
        { label: '易混词', text: '用我词库里的词，挑 3 组容易混淆的单词辨析，每组给一句例句和中文。' },
        { label: '短语辨析', text: '挑 3 个四级常考且容易混的固定搭配，说明区别并各给一个例句。' },
        { label: '阅读长难句', text: '给一句四级阅读理解里的长难句，带我拆主干再翻译。' },
        { label: '写作模板', text: '给我一套四级议论文三段式模板，附 5 个高分替换词和常见扣分点。' },
        { label: '我的进度', text: '看看我的单词学习进度，给我一个今天能完成的最小复习计划。' }
    ];

    var WELCOME = [
        '我是四级冲刺助教，会结合你的单词进度出题与答疑。',
        '',
        '可以这样问我：',
        '- 帮我翻译：随着科技的发展，人们的生活发生了巨大变化',
        '- 辨析 affect / effect',
        '- 非谓语动词在四级里怎么考',
        '- 用我今天学的词出 3 道题',
        '',
        '下面的词块点一下就能复制，双击会填进输入框。'
    ].join('\n');

    var messages = load();
    var streaming = false;
    var wordData = { today: [], marked: [], today_count: 0, marked_count: 0 };
    var currentTab = 'today';

    /* ---------- 状态存取 ---------- */

    function load() {
        try {
            var raw = sessionStorage.getItem(KEY_HISTORY);
            var arr = raw ? JSON.parse(raw) : [];
            return Array.isArray(arr) ? arr : [];
        } catch (e) {
            return [];
        }
    }

    function save() {
        try {
            sessionStorage.setItem(KEY_HISTORY, JSON.stringify(messages.slice(-40)));
        } catch (e) { /* 忽略配额问题 */ }
    }

    function applyOpen(open) {
        panel.classList.toggle('collapsed', !open);
        document.body.classList.toggle('ai-coach-open', open);
        try { localStorage.setItem(KEY_OPEN, open ? '1' : '0'); } catch (e) {}
    }

    /* ---------- 渲染 ---------- */

    function fmt(text) {
        var h = String(text).replace(/[&<>]/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c];
        });
        h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
        return h;
    }

    function scrollBottom() {
        elMessages.scrollTop = elMessages.scrollHeight;
    }

    function renderAll() {
        elMessages.innerHTML = '';
        messages.forEach(function (m) {
            elMessages.appendChild(bubbleEl(m));
        });
        scrollBottom();
    }

    function bubbleEl(m) {
        var row = document.createElement('div');
        row.className = 'ai-msg ' + (m.role === 'user' ? 'user' : 'assistant');
        var b = document.createElement('div');
        b.className = 'ai-bubble';
        b.innerHTML = fmt(m.content || '');
        row.appendChild(b);
        return row;
    }

    function renderLastBubble() {
        var last = elMessages.lastElementChild;
        if (!last) return;
        var b = last.querySelector('.ai-bubble');
        if (b) b.innerHTML = fmt(messages[messages.length - 1].content || '');
        scrollBottom();
    }

    function renderQuick() {
        elQuick.innerHTML = '';
        QUICK_PROMPTS.forEach(function (p) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ai-quick-chip';
            btn.textContent = p.label;
            btn.addEventListener('click', function () {
                send(p.text);
            });
            elQuick.appendChild(btn);
        });
    }

    function renderWords() {
        var list = currentTab === 'marked' ? wordData.marked : wordData.today;
        elTabToday.classList.toggle('active', currentTab === 'today');
        elTabMarked.classList.toggle('active', currentTab === 'marked');
        elTabToday.textContent = '今天学的' + (wordData.today_count ? ' ' + wordData.today_count : '');
        elTabMarked.textContent = '星标词' + (wordData.marked_count ? ' ' + wordData.marked_count : '');

        elWordList.innerHTML = '';
        if (!list || !list.length) {
            var empty = document.createElement('span');
            empty.className = 'ai-words-empty';
            empty.textContent = currentTab === 'today'
                ? '今天尚未学习单词，可在自测页查看释义'
                : '暂无星标单词，可在单词卡上标记星标';
            elWordList.appendChild(empty);
            return;
        }
        list.forEach(function (w) {
            var chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'ai-word';
            chip.textContent = w;
            chip.title = '单击复制，双击填入输入框';
            chip.addEventListener('click', async function () {
                var ok = await copyText(w);
                toast(ok ? '已复制：' + w : '复制失败，请手动选中');
            });
            chip.addEventListener('dblclick', function (e) {
                e.preventDefault();
                elInput.value = (elInput.value ? elInput.value.replace(/\s+$/, '') + ' ' : '') + w;
                elInput.focus();
                autoGrow();
            });
            elWordList.appendChild(chip);
        });
    }

    /* ---------- 宽度调整（拖拽 / 一键加宽） ---------- */

    var MIN_W = 300;

    function cssDefaultWidth() {
        // 与 CSS 里的媒体查询保持一致：大屏 372，其余 330
        // 注意不能读 --ai-coach-w，那个值在拖拽后已经被覆盖了
        return window.innerWidth >= 1600 ? 372 : 330;
    }

    function maxWidth() {
        return Math.max(360, Math.min(window.innerWidth - 280, 900));
    }

    function setWidth(px, persist) {
        var w = Math.max(MIN_W, Math.min(Math.round(px), maxWidth()));
        document.documentElement.style.setProperty('--ai-coach-w', w + 'px');
        if (persist !== false) {
            try { localStorage.setItem(KEY_WIDTH, String(w)); } catch (e) { /* 忽略 */ }
        }
        return w;
    }

    function initWidth() {
        var saved = 0;
        try { saved = parseInt(localStorage.getItem(KEY_WIDTH) || '0', 10) || 0; } catch (e) { saved = 0; }
        if (saved) setWidth(saved, false);
    }

    function bindResizer() {
        if (!elResizer) return;
        var dragging = false;
        var startX = 0;
        var startW = 0;
        var targetW = 0;

        elResizer.addEventListener('pointerdown', function (e) {
            if (panel.classList.contains('collapsed')) return;
            dragging = true;
            startX = e.clientX;
            startW = panel.getBoundingClientRect().width;
            targetW = Math.round(startW);
            panel.classList.add('resizing');
            document.body.style.userSelect = 'none';
            try { elResizer.setPointerCapture(e.pointerId); } catch (err) { /* 忽略 */ }
        });

        elResizer.addEventListener('pointermove', function (e) {
            if (!dragging) return;
            // 记下目标宽度：松手时不能用 getBoundingClientRect 读，
            // 那时过渡动画还没跑完，会读到旧值把拖拽结果覆盖掉。
            targetW = setWidth(startW + (e.clientX - startX), false);
        });

        function endDrag() {
            if (!dragging) return;
            dragging = false;
            panel.classList.remove('resizing');
            document.body.style.userSelect = '';
            setWidth(targetW || Math.round(panel.getBoundingClientRect().width), true);
        }

        elResizer.addEventListener('pointerup', endDrag);
        elResizer.addEventListener('pointercancel', endDrag);

        elResizer.addEventListener('dblclick', function () {
            document.documentElement.style.removeProperty('--ai-coach-w');
            try { localStorage.removeItem(KEY_WIDTH); } catch (e) { /* 忽略 */ }
            toast('已还原默认宽度');
        });
    }

    function bindWide() {
        if (!elWide) return;
        elWide.addEventListener('click', function () {
            var cur = panel.getBoundingClientRect().width;
            if (cur >= 560) {
                setWidth(cssDefaultWidth(), true);
                toast('已还原宽度');
            } else {
                setWidth(620, true);
                toast('已加宽（可拖动右边缘继续调）');
            }
        });
    }

    /* ---------- 单词列表同步（不丢对话） ---------- */

    var refreshing = false;
    var lastWordsSig = '';
    var syncTimer = null;

    function wordsSig(data) {
        return JSON.stringify([data.today || [], data.marked || []]);
    }

    function flashDot() {
        if (!elRefreshDot) return;
        elRefreshDot.classList.add('on');
        setTimeout(function () { elRefreshDot.classList.remove('on'); }, 2400);
    }

    async function refreshWords(opts) {
        opts = opts || {};
        if (refreshing) return false;
        refreshing = true;

        var icon = elRefresh && elRefresh.querySelector('.ai-refresh-icon');
        if (icon) icon.classList.add('spinning');

        try {
            var res = await fetch('/ai/quick_words', { cache: 'no-store' });
            if (!res.ok) throw new Error('HTTP ' + res.status);
            var d = await res.json();
            var before = lastWordsSig;

            var next = {
                today: d.today || [],
                marked: d.marked || [],
                today_count: Number(d.today_count || 0),
                marked_count: Number(d.marked_count || 0)
            };
            wordData = next;
            renderWords();

            var changed = wordsSig(next) !== before;
            lastWordsSig = wordsSig(next);

            if (changed) {
                flashDot();
                if (opts.notify) {
                    toast('已同步：今天 ' + next.today_count + ' 词 / 星标 ' + next.marked_count + ' 词');
                }
            } else if (opts.notify) {
                toast('已是最新，没有新单词');
            }
            return changed;
        } catch (e) {
            if (opts.notify) toast('同步失败：' + e.message);
            return false;
        } finally {
            refreshing = false;
            if (icon) icon.classList.remove('spinning');
        }
    }

    function scheduleSync(delay) {
        clearTimeout(syncTimer);
        syncTimer = setTimeout(function () { refreshWords(); }, delay || 500);
    }

    // 右侧每"看一次释义 / 星标"都会请求这些接口，同时同步侧栏词表
    function bindAutoSync() {
        if (window.fetch && !window.__aiCoachFetchWrapped) {
            window.__aiCoachFetchWrapped = true;
            var origFetch = window.fetch;
            window.fetch = function (input) {
                var url = typeof input === 'string' ? input : (input && input.url) || '';
                var p = origFetch.apply(this, arguments);
                if (url.indexOf('/get_word_definition/') >= 0 ||
                    url.indexOf('/mark_word/') >= 0 ||
                    url.indexOf('/unmark_word/') >= 0) {
                    p.then(function () { scheduleSync(400); }).catch(function () { /* 忽略 */ });
                }
                return p;
            };
        }

        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) scheduleSync(200);
        });
        window.addEventListener('focus', function () { scheduleSync(300); });
    }

    /* ---------- 复制 / 提示 ---------- */

    async function copyText(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return true;
            }
        } catch (e) { /* 走降级方案 */ }

        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', 'readonly');
        ta.style.position = 'fixed';
        ta.style.top = '-1000px';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        var ok = false;
        try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
        document.body.removeChild(ta);
        return ok;
    }

    var toastTimer = null;
    function toast(msg) {
        if (!elToast) return;
        elToast.textContent = msg;
        elToast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { elToast.classList.remove('show'); }, 1600);
    }

    /* ---------- 发送 / 流式接收 ---------- */

    function autoGrow() {
        elInput.style.height = 'auto';
        elInput.style.height = Math.min(elInput.scrollHeight, 110) + 'px';
    }

    async function send(text) {
        text = (text || '').trim();
        if (!text || streaming) return;

        messages.push({ role: 'user', content: text });
        var placeholder = { role: 'assistant', content: '' };
        messages.push(placeholder);
        renderAll();
        elInput.value = '';
        autoGrow();

        streaming = true;
        elSend.disabled = true;
        elSend.textContent = '思考中';

        var history = messages.slice(0, -2).filter(function (m) {
            return m.content && !m.local;
        }).slice(-8).map(function (m) {
            return { role: m.role, content: m.content };
        });

        try {
            var res = await fetch('/ai/coach_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, history: history })
            });
            if (!res.ok) throw new Error('HTTP ' + res.status);
            if (!res.body) throw new Error('浏览器不支持流式读取');

            var reader = res.body.getReader();
            var decoder = new TextDecoder('utf-8');
            var buffer = '';

            while (true) {
                var chunk = await reader.read();
                if (chunk.done) break;
                buffer += decoder.decode(chunk.value, { stream: true });

                var idx;
                while ((idx = buffer.indexOf('\n\n')) >= 0) {
                    var piece = buffer.slice(0, idx);
                    buffer = buffer.slice(idx + 2);
                    handleSSE(piece);
                }
            }
            handleSSE(buffer);
        } catch (e) {
            placeholder.content += '\n\n[请求失败：' + e.message + ']';
        } finally {
            streaming = false;
            elSend.disabled = false;
            elSend.textContent = '发送';
            save();
            renderAll();
            // 回答结束后同步一次词表（新学的词可能已进库）
            scheduleSync(300);
        }
    }

    function handleSSE(piece) {
        if (!piece) return;
        piece.split('\n').forEach(function (line) {
            if (line.indexOf('data: ') !== 0) return;
            var payload = line.slice(6).trim();
            if (!payload || payload === '[DONE]') return;
            try {
                var data = JSON.parse(payload);
                if (data && data.content) {
                    messages[messages.length - 1].content += data.content;
                    renderLastBubble();
                }
            } catch (e) { /* 忽略非 JSON 行 */ }
        });
    }

    /* ---------- 事件绑定 ---------- */

    elForm.addEventListener('submit', function (e) {
        e.preventDefault();
        send(elInput.value);
    });

    elInput.addEventListener('input', autoGrow);
    elInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            send(elInput.value);
        }
    });

    elCollapse.addEventListener('click', function () { applyOpen(false); });
    elToggle.addEventListener('click', function () { applyOpen(true); });
    elClear.addEventListener('click', function () {
        if (!messages.length) return;
        if (!confirm('清空当前对话记录？')) return;
        messages = [];
        ensureWelcome();
        save();
        renderAll();
    });

    elTabToday.addEventListener('click', function () { currentTab = 'today'; renderWords(); });
    elTabMarked.addEventListener('click', function () { currentTab = 'marked'; renderWords(); });
    if (elRefresh) {
        elRefresh.addEventListener('click', function () {
            refreshWords({ notify: true });
        });
    }
    elCopyAll.addEventListener('click', async function () {
        var list = currentTab === 'marked' ? wordData.marked : wordData.today;
        if (!list || !list.length) { toast('列表为空'); return; }
        var ok = await copyText(list.join(', '));
        toast(ok ? '已复制 ' + list.length + ' 个单词' : '复制失败');
    });

    /* ---------- 初始化 ---------- */

    function ensureWelcome() {
        if (!messages.length) {
            messages.push({ role: 'assistant', content: WELCOME, local: true });
        }
    }

    function init() {
        // 手机/窄屏上默认收起，避免 62vh 的浮层挡住单词卡和"下一个"按钮
        var defaultOpen = window.innerWidth >= 900;
        try {
            var saved = localStorage.getItem(KEY_OPEN);
            applyOpen(saved === null ? defaultOpen : saved === '1');
        } catch (e) {
            applyOpen(defaultOpen);
        }

        initWidth();
        bindResizer();
        bindWide();
        bindAutoSync();

        ensureWelcome();
        renderAll();
        renderQuick();
        renderWords();

        // 首次加载 + 之后由「同步」按钮 / 右侧刷词 / 切回标签页触发
        refreshWords();
    }

    init();
})();
