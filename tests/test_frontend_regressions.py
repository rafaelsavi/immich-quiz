import re
from collections import Counter
from pathlib import Path

# Elements created at runtime by JS.
DYNAMIC_IDS = frozenset(
    {
        'album-shuffle-help-modal',
        'card-goal-date',
        'card-goal-location',
        'goal-date',
        'goal-location',
        'photo-lightbox',
        'photo-lightbox-img',
        'preflight-warning',
        'reveal-shuffle-map-shell',
        'shuffle-cards-list',
        'shuffle-map-shell',
    }
)

STATIC_DIR = Path(__file__).parent.parent / 'static'
INDEX_HTML = STATIC_DIR / 'index.html'
AUDIO_PLAYGROUND_HTML = STATIC_DIR / 'audio-playground.html'
JS_DIR = STATIC_DIR / 'js'


def test_every_referenced_element_id_exists_in_markup() -> None:
    html_files = [INDEX_HTML, AUDIO_PLAYGROUND_HTML]
    defined_ids: set[str] = set()
    for html_file in html_files:
        if html_file.exists():
            content = html_file.read_text(encoding='utf-8')
            defined_ids.update(re.findall(r'id=["\']([^"\']+)["\']', content))

    js_files = list(JS_DIR.rglob('*.js'))
    missing_references: list[str] = []

    get_elem_pattern = re.compile(r'document\.getElementById\(\s*["\']([^"\']+)["\']\s*\)')
    query_sel_pattern = re.compile(r'document\.querySelector(?:All)?\(\s*["\']#([a-zA-Z0-9_-]+)')

    for js_file in js_files:
        content = js_file.read_text(encoding='utf-8')
        referenced_ids = set(get_elem_pattern.findall(content))
        referenced_ids.update(query_sel_pattern.findall(content))

        for target_id in referenced_ids:
            if target_id in DYNAMIC_IDS:
                continue
            if target_id not in defined_ids:
                rel_path = js_file.relative_to(STATIC_DIR)
                missing_references.append(f"'{target_id}' referenced in {rel_path}")

    assert not missing_references, f'Referenced element IDs missing from HTML markup: {", ".join(missing_references)}'


def test_template_owned_ids_use_lazy_getters() -> None:
    # Arms in Phase 2 when template elements are introduced.
    index_content = INDEX_HTML.read_text(encoding='utf-8')
    template_blocks = re.findall(r'<template[^>]*>(.*?)</template>', index_content, flags=re.DOTALL)
    template_ids: set[str] = set()
    for block in template_blocks:
        template_ids.update(re.findall(r'id=["\']([^"\']+)["\']', block))

    state_js = JS_DIR / 'modules' / 'state.js'
    content = state_js.read_text(encoding='utf-8')

    el_match = re.search(r'export const el = \{(.*?)\n\};', content, flags=re.DOTALL)
    assert el_match, f'Could not find export const el in {state_js}'
    el_body = el_match.group(1)

    eager_violations: list[str] = []
    lines = el_body.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('get ') or stripped.startswith('//') or stripped.startswith('/*'):
            continue
        eager_match = re.match(r'([a-zA-Z0-9_$]+)\s*:\s*document\.(?:getElementById|querySelector)\(', stripped)
        if eager_match:
            prop_name = eager_match.group(1)
            target_ids = re.findall(r'getElementById\(\s*["\']([^"\']+)["\']\s*\)', stripped)
            query_ids = re.findall(r'querySelector(?:All)?\(\s*["\']#([a-zA-Z0-9_-]+)', stripped)
            for tid in target_ids + query_ids:
                if tid in template_ids:
                    eager_violations.append(f"Property '{prop_name}' eagerly fetches template-owned ID '{tid}'")

    assert not eager_violations, f'Eager properties in state.js targeting template-owned IDs: {eager_violations}'


def _get_exported_names(js_file: Path) -> set[str]:
    content = js_file.read_text(encoding='utf-8')
    exports: set[str] = set()

    for match in re.finditer(r'export\s+(?:async\s+)?(?:function|const|let|class)\s+([a-zA-Z0-9_$]+)', content):
        exports.add(match.group(1))

    for match in re.finditer(r'export\s+\{([^}]+)\}', content):
        raw_exports = match.group(1)
        for item in raw_exports.split(','):
            item = item.strip()
            if not item:
                continue
            if ' as ' in item:
                exports.add(item.split(' as ')[1].strip())
            else:
                exports.add(item)

    return exports


def _case_sensitive_exists(path: Path) -> bool:
    if not path.exists():
        return False
    curr = path
    while curr != curr.parent:
        parent = curr.parent
        if parent.exists():
            entries = {entry.name for entry in parent.iterdir()}
            if curr.name not in entries:
                return False
        curr = parent
    return True


def test_every_es_import_resolves() -> None:
    js_files = list(JS_DIR.rglob('*.js'))
    import_errors: list[str] = []

    import_pattern = re.compile(
        r'import\s+(?:(\{([^}]+)\}|[a-zA-Z0-9_$]+|\*\s+as\s+[a-zA-Z0-9_$]+)\s+from\s+)?["\']([^"\']+)["\'];?',
        re.DOTALL,
    )

    for js_file in js_files:
        content = js_file.read_text(encoding='utf-8')
        for match in import_pattern.finditer(content):
            named_block = match.group(2)
            import_path_str = match.group(3)

            if not import_path_str.startswith('.'):
                continue

            target_file = (js_file.parent / import_path_str).resolve()
            rel_source = js_file.relative_to(STATIC_DIR)

            if not _case_sensitive_exists(target_file):
                import_errors.append(f"{rel_source} imports non-existent file '{import_path_str}'")
                continue

            if named_block:
                exported_names = _get_exported_names(target_file)
                for item in named_block.split(','):
                    item = item.strip()
                    if not item:
                        continue
                    original_name = item.split(' as ')[0].strip() if ' as ' in item else item

                    if original_name not in exported_names:
                        rel_target = target_file.relative_to(STATIC_DIR)
                        import_errors.append(
                            f"{rel_source} imports '{original_name}' from {rel_target}, but it is not exported"
                        )

    assert not import_errors, f'ES Module import resolution failures:\n{chr(10).join(import_errors)}'


def test_element_ids_are_unique() -> None:
    content = INDEX_HTML.read_text(encoding='utf-8')
    all_ids = re.findall(r'id=["\']([^"\']+)["\']', content)
    counts = Counter(all_ids)
    duplicates = {id_name: count for id_name, count in counts.items() if count > 1}

    assert not duplicates, f'Duplicate element IDs found in index.html: {duplicates}'


def test_js_files_have_valid_syntax() -> None:
    import shutil
    import subprocess

    node_bin = shutil.which('node')
    if not node_bin:
        for candidate in [
            r'C:\Program Files\nodejs\node.exe',
            r'C:\Program Files (x86)\nodejs\node.exe',
            r'C:\Program Files\Adobe\Adobe Photoshop 2026\node.exe',
            r'C:\Program Files\Adobe\Adobe Creative Cloud Experience\libs\node.exe',
        ]:
            if Path(candidate).is_file():
                node_bin = candidate
                break
    if not node_bin:
        return

    syntax_errors: list[str] = []
    for js_file in JS_DIR.rglob('*.js'):
        res = subprocess.run([node_bin, '--check', str(js_file)], capture_output=True, text=True)
        if res.returncode != 0:
            rel_file = js_file.relative_to(STATIC_DIR)
            syntax_errors.append(f'{rel_file}: {res.stderr.strip()}')

    assert not syntax_errors, f'JavaScript syntax errors found:\n{chr(10).join(syntax_errors)}'


def test_app_js_does_not_reference_template_owned_el_properties() -> None:
    index_content = INDEX_HTML.read_text(encoding='utf-8')
    template_blocks = re.findall(r'<template[^>]*>(.*?)</template>', index_content, flags=re.DOTALL)
    template_ids: set[str] = set()
    for block in template_blocks:
        template_ids.update(re.findall(r'id=["\']([^"\']+)["\']', block))

    state_js = JS_DIR / 'modules' / 'state.js'
    state_content = state_js.read_text(encoding='utf-8')

    el_match = re.search(r'export const el = \{(.*?)\n\};', state_content, flags=re.DOTALL)
    assert el_match, f'Could not find export const el in {state_js}'
    el_body = el_match.group(1)

    template_owned_props: set[str] = set()

    # Eager shape: prop_name: document.getElementById('id')
    eager_matches = re.finditer(
        r'(\w+)\s*:\s*document\.(?:getElementById|querySelector)\(\s*["\']#?([^"\']+)["\']\s*\)',
        el_body,
    )
    for m in eager_matches:
        prop_name, tid = m.group(1), m.group(2)
        if tid in template_ids:
            template_owned_props.add(prop_name)

    # Getter shape: get prop_name() { ... getElementById('id') ... }
    getter_matches = re.finditer(
        r'get\s+(\w+)\s*\(\)\s*\{(.*?)(?=get\s+\w+\s*\(\)|$|\n\s*\w+\s*:)',
        el_body,
        flags=re.DOTALL,
    )
    for m in getter_matches:
        prop_name = m.group(1)
        getter_body = m.group(2)
        target_ids = re.findall(r'getElementById\(\s*["\']([^"\']+)["\']\s*\)', getter_body)
        query_ids = re.findall(r'querySelector(?:All)?\(\s*["\']#([a-zA-Z0-9_-]+)', getter_body)
        for tid in target_ids + query_ids:
            if tid in template_ids:
                template_owned_props.add(prop_name)

    app_js = JS_DIR / 'app.js'
    app_content = app_js.read_text(encoding='utf-8')

    violations: list[str] = []
    for prop_name in sorted(template_owned_props):
        pattern = rf'\bel\.{prop_name}\b'
        if re.search(pattern, app_content):
            violations.append(f'app.js directly references template-owned el.{prop_name}')

    assert not violations, f'Direct references to template-owned el properties in app.js: {violations}'


def test_event_listener_callbacks_are_defined() -> None:
    js_files = list(JS_DIR.rglob('*.js'))
    callback_errors: list[str] = []

    listener_pattern = re.compile(r'addEventListener\(\s*["\'][^"\']+["\']\s*,\s*([a-zA-Z0-9_$]+)\s*[,)]')

    for js_file in js_files:
        content = js_file.read_text(encoding='utf-8')
        for match in listener_pattern.finditer(content):
            cb_name = match.group(1)
            has_import = bool(re.search(rf'\bimport\s+[^;]*\b{re.escape(cb_name)}\b[^;]*from', content, re.DOTALL))
            has_fn_def = bool(re.search(rf'\bfunction\s+{re.escape(cb_name)}\b', content))
            has_var_def = bool(
                re.search(rf'\b(?:const|let|var)\s+.*?(\b{re.escape(cb_name)}\b)\s*[:=,]', content, re.DOTALL)
            )
            has_param = bool(re.search(rf'function[^(]*\([^)]*\b{re.escape(cb_name)}\b[^)]*\)', content, re.DOTALL))
            if not (has_import or has_fn_def or has_var_def or has_param):
                rel_path = js_file.relative_to(STATIC_DIR)
                callback_errors.append(f"Callback '{cb_name}' in {rel_path} is neither imported nor defined")

    assert not callback_errors, f'Undefined event listener callbacks:\n{chr(10).join(callback_errors)}'


def test_map_controls_disable_click_propagation_and_guard_pin_placement() -> None:
    maps_js = (JS_DIR / 'modules' / 'maps.js').read_text(encoding='utf-8')
    pinpoint_js = (JS_DIR / 'modules' / 'modes' / 'pinpoint.js').read_text(encoding='utf-8')

    # maps.js must call disableClickPropagation for controls and buttons
    assert 'L.DomEvent.disableClickPropagation' in maps_js, 'maps.js must disable click propagation for controls'
    assert 'L.DomEvent.disableScrollPropagation' in maps_js, 'maps.js must disable scroll propagation for controls'

    # ensureGuessMap must guard click event target against control/button elements
    assert 'origTarget.closest' in maps_js, (
        'ensureGuessMap in maps.js must check origTarget.closest to avoid setting pin on control clicks'
    )

    # pinpoint.js must also disable propagation on guessMapFullscreen
    assert 'L.DomEvent.disableClickPropagation(el.guessMapFullscreen)' in pinpoint_js, (
        'pinpoint.js must disable click propagation on guessMapFullscreen'
    )


def test_preflight_warning_disables_start_button_and_guards_submission() -> None:
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    state_js = (JS_DIR / 'modules' / 'state.js').read_text(encoding='utf-8')
    setup_filters_js = (JS_DIR / 'modules' / 'setup_filters.js').read_text(encoding='utf-8')
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')

    # start-match-btn exists in HTML as submit button
    assert 'id="start-match-btn"' in index_html, 'start-match-btn ID missing from index.html'
    assert 'setupSubmitBtn' in state_js, 'setupSubmitBtn missing from state.js'

    # showPreflightWarning must disable the submit button
    assert 'showPreflightWarning' in setup_filters_js
    assert 'submitBtn.disabled = true' in setup_filters_js, 'showPreflightWarning must disable the submit button'

    # hidePreflightWarning must re-enable the submit button
    assert 'hidePreflightWarning' in setup_filters_js
    assert 'submitBtn.disabled = false' in setup_filters_js, 'hidePreflightWarning must re-enable the submit button'

    # startMatch must guard against starting if button is disabled or preflight warning is visible
    assert 'async function startMatch' in app_js
    assert 'submitBtn.disabled' in app_js, 'startMatch must check submitBtn.disabled'


def test_pinpoint_quiz_image_fullscreen_button_handling() -> None:
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    state_js = (JS_DIR / 'modules' / 'state.js').read_text(encoding='utf-8')
    pinpoint_js = (JS_DIR / 'modules' / 'modes' / 'pinpoint.js').read_text(encoding='utf-8')
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')

    assert 'id="quiz-image-fullscreen"' in index_html, 'quiz-image-fullscreen ID missing from index.html'
    assert 'quizImageFullscreen' in state_js, 'quizImageFullscreen getter missing from state.js'

    # pinpoint.js onReady must unhide quizImageFullscreen
    assert 'el.quizImageFullscreen.classList.remove("hidden")' in pinpoint_js, (
        'pinpoint.js must unhide quizImageFullscreen on onReady / reveal'
    )
    # pinpoint.js unmount / renderQuestion must hide quizImageFullscreen
    assert 'el.quizImageFullscreen.classList.add("hidden")' in pinpoint_js, (
        'pinpoint.js must hide quizImageFullscreen on renderQuestion / unmount'
    )
    # app.js must not call removeAttribute('src') on quizImageFullscreen
    assert 'el.quizImageFullscreen.removeAttribute("src")' not in app_js, (
        'app.js must not call removeAttribute("src") on quizImageFullscreen'
    )


def test_leaderboard_enhancements_markup_and_modules() -> None:
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    state_js = (JS_DIR / 'modules' / 'state.js').read_text(encoding='utf-8')
    leaderboard_js = (JS_DIR / 'modules' / 'leaderboard.js').read_text(encoding='utf-8')
    leaderboard_css = (STATIC_DIR / 'css' / 'components' / 'leaderboard.css').read_text(encoding='utf-8')
    i18n_js = (JS_DIR / 'modules' / 'i18n.js').read_text(encoding='utf-8')

    api_js = (JS_DIR / 'modules' / 'api.js').read_text(encoding='utf-8')
    setup_filters_js = (JS_DIR / 'modules' / 'setup_filters.js').read_text(encoding='utf-8')

    assert 'id="leaderboard-scope-pill"' in index_html, 'leaderboard-scope-pill ID missing from index.html'
    assert 'leaderboardScopePill' in state_js, 'leaderboardScopePill getter missing from state.js'
    assert 'leaderboard-empty-row' in leaderboard_js, 'leaderboard.js must handle empty state'
    assert 'leaderboard-empty-row' in leaderboard_css, 'leaderboard.css must style empty state'
    assert 'rank-medal' in leaderboard_js, 'leaderboard.js must apply rank medals'
    assert 'leaderboard-scope-pill' in leaderboard_css, 'leaderboard.css must style scope pill'
    assert '"leaderboard.empty"' in i18n_js, 'i18n.js must define leaderboard.empty key'
    assert '"leaderboard.perfect_badge"' in i18n_js, 'i18n.js must define leaderboard.perfect_badge key'
    assert 'min_date' in api_js, 'api.js must support min_date query parameter'
    assert 'max_date' in api_js, 'api.js must support max_date query parameter'
    assert 'countries' in api_js, 'api.js must support countries query parameter'
    assert 'cities' in api_js, 'api.js must support cities query parameter'
    assert 'person_ids' in api_js, 'api.js must support person_ids query parameter'
    assert 'people_mode' in api_js, 'api.js must support people_mode query parameter'
    assert 'loadLeaderboardDebounced' in leaderboard_js, 'leaderboard.js must export loadLeaderboardDebounced'
    assert 'getActiveFilterSummary' in setup_filters_js, 'setup_filters.js must export getActiveFilterSummary'
    assert 'isCustomFilteredActive' in setup_filters_js, 'setup_filters.js must export isCustomFilteredActive'
