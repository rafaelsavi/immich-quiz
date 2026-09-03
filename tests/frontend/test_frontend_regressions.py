import re
from collections import Counter
from pathlib import Path

# Elements created at runtime by JS.
DYNAMIC_IDS = frozenset(
    {
        'album-shuffle-help-modal',
        'card-goal-date',
        'card-goal-location',
        'carousel-indicator',
        'carousel-media-row',
        'carousel-next-btn',
        'carousel-photo-img',
        'carousel-photo-shell',
        'carousel-photo-zoom-btn',
        'carousel-prev-btn',
        'carousel-round-content',
        'carousel-round-extra',
        'carousel-title',
        'challenge-avatar-preview',
        'challenge-copy-btn',
        'challenge-error-home-btn',
        'challenge-finisher-count',
        'challenge-invite-link-box',
        'challenge-invite-qr-btn',
        'challenge-invite-qr-code',
        'challenge-invite-qr-container',
        'challenge-join-form',
        'challenge-journey-map',
        'challenge-journey-map-head',
        'challenge-journey-map-shell',
        'challenge-polaroid-gallery',
        'challenge-resume-btn',
        'challenge-round-live-pill',
        'challenge-round-live-status',
        'challenge-see-results-btn',
        'challenge-share-btn',
        'challenge-share-url',
        'challenge-start-btn',
        'empty-state-clear-btn',
        'empty-state-create-btn',
        'finisher-count-text',
        'goal-date',
        'goal-location',
        'grand-reveal-home-btn',
        'grand-reveal-hub-btn',
        'grand-reveal-live-pill',
        'grand-reveal-live-status',
        'grand-reveal-meta-tally',
        'grand-reveal-podium',
        'grand-reveal-podium-section',
        'grand-reveal-provisional',
        'grand-reveal-share-btn',
        'grand-reveal-share-summary-btn',
        'grand-reveal-table',
        'intermission-map',
        'intermission-map-shell',
        'intermission-next-btn',
        'intermission-standings-list',
        'photo-lightbox',
        'photo-lightbox-img',
        'player-name-input',
        'preflight-warning',
        'retry-load-challenges-btn',
        'reveal-shuffle-map-shell',
        'scatter-map',
        'scatter-map-shell',
        'shuffle-cards-list',
        'shuffle-map-shell',
    }
)


STATIC_DIR = Path(__file__).resolve().parents[2] / 'static'
INDEX_HTML = STATIC_DIR / 'index.html'
AUDIO_PLAYGROUND_HTML = STATIC_DIR / 'audio-playground.html'
JS_DIR = STATIC_DIR / 'js'


def read_challenges_page_js() -> str:
    challenges_screen = JS_DIR / 'modules' / 'screens' / 'challenges.js'
    return challenges_screen.read_text(encoding='utf-8')


def read_challenge_bundle_js() -> str:
    challenge_dir = JS_DIR / 'modules' / 'challenge'
    files = list(challenge_dir.glob('*.js'))
    return '\n'.join(f.read_text(encoding='utf-8') for f in files)


def test_legacy_monolith_and_proxy_files_are_removed() -> None:
    """Verify that legacy backwards-compatibility files are fully removed."""
    legacy_challenge_js = JS_DIR / 'modules' / 'challenge.js'
    legacy_challenges_page_js = JS_DIR / 'modules' / 'challenges_page.js'
    assert not legacy_challenge_js.exists(), 'Legacy challenge.js should be removed'
    assert not legacy_challenges_page_js.exists(), 'Legacy challenges_page.js should be removed'


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

    node_bin = shutil.which('node') or shutil.which('nodejs')
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
    setup_js = JS_DIR / 'modules' / 'screens' / 'setup.js'
    setup_code = (
        setup_js.read_text(encoding='utf-8') if setup_js.exists() else (JS_DIR / 'app.js').read_text(encoding='utf-8')
    )
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
    assert 'async function startMatch' in setup_code or 'async function startMatch' in app_js
    assert 'submitBtn.disabled' in setup_code, 'startMatch must check submitBtn.disabled'
    assert 'state.startingMatch' in setup_code, 'startMatch must check state.startingMatch'
    assert 'startingMatch' in state_js, 'startingMatch must be initialized in state.js'


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
    i18n_locales = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8') + (
        JS_DIR / 'modules' / 'locales' / 'pt_BR.js'
    ).read_text(encoding='utf-8')

    api_js = (JS_DIR / 'modules' / 'api.js').read_text(encoding='utf-8')
    setup_filters_js = (JS_DIR / 'modules' / 'setup_filters.js').read_text(encoding='utf-8')

    assert 'id="leaderboard-scope-pill"' in index_html, 'leaderboard-scope-pill ID missing from index.html'
    formatters_js = (JS_DIR / 'modules' / 'formatters.js').read_text(encoding='utf-8')
    assert 'leaderboardScopePill' in state_js, 'leaderboardScopePill getter missing from state.js'
    assert 'leaderboard-empty-row' in leaderboard_js, 'leaderboard.js must handle empty state'
    assert 'leaderboard-empty-row' in leaderboard_css, 'leaderboard.css must style empty state'
    assert 'rank-medal' in leaderboard_js or ('createRankBadge' in leaderboard_js and 'rank-medal' in formatters_js), (
        'leaderboard must apply rank medals'
    )
    assert 'leaderboard-scope-pill' in leaderboard_css, 'leaderboard.css must style scope pill'
    assert '.leaderboard-scope-pill:empty' in leaderboard_css, 'leaderboard.css must hide empty scope pill'
    assert '"leaderboard.empty"' in i18n_locales, 'locales must define leaderboard.empty key'
    assert '"leaderboard.perfect_badge"' in i18n_locales, 'locales must define leaderboard.perfect_badge key'
    assert 'min_date' in api_js, 'api.js must support min_date query parameter'
    assert 'max_date' in api_js, 'api.js must support max_date query parameter'
    assert 'countries' in api_js, 'api.js must support countries query parameter'
    assert 'cities' in api_js, 'api.js must support cities query parameter'
    assert 'people' in api_js, 'api.js must support people query parameter'
    assert 'albums' in api_js, 'api.js must support albums query parameter'
    assert 'people_mode' in api_js, 'api.js must support people_mode query parameter'
    assert 'loadLeaderboardDebounced' in leaderboard_js, 'leaderboard.js must export loadLeaderboardDebounced'
    assert 'getActiveFilterSummary' in setup_filters_js, 'setup_filters.js must export getActiveFilterSummary'
    assert 'isCustomFilteredActive' in setup_filters_js, 'setup_filters.js must export isCustomFilteredActive'


def test_filter_persistence_and_people_mode_lifecycle() -> None:
    """Verify that initial library loading does not overwrite saved filters with defaults."""
    setup_filters_js = (JS_DIR / 'modules' / 'setup_filters.js').read_text(encoding='utf-8')
    index_html = INDEX_HTML.read_text(encoding='utf-8')

    # 1. HTML markup defines both Any and All buttons with proper data-people-mode
    assert 'id="people-mode-toggle"' in index_html
    assert 'data-people-mode="ANY"' in index_html
    assert 'data-people-mode="ALL"' in index_html

    # 2. setup_filters.js exports people mode helpers
    assert 'export function getSelectedPeopleMode' in setup_filters_js
    assert 'export function setPeopleMode' in setup_filters_js
    assert 'export function resetPeopleMode' in setup_filters_js
    assert 'export function updatePeopleModeToggleVisibility' in setup_filters_js

    # 3. onLibrariesChanged must accept shouldSave flag and default or allow avoiding overwrite during init
    assert 'export async function onLibrariesChanged(shouldSave = true)' in setup_filters_js
    # 4. initLibraries must call onLibrariesChanged(false) before restoreFilters
    assert 'await onLibrariesChanged(false)' in setup_filters_js
    assert 'restoreFilters()' in setup_filters_js


def test_batch_reveal_item_supports_optional_pin_id() -> None:
    """Verify BatchRevealItem supports optional true_pin_id for locationless Album Shuffle."""
    from src.models import BatchRevealItem

    item_without_pin = BatchRevealItem(
        photo_id='photo-123',
        true_pin_id=None,
        actual_year=2024,
        actual_month=5,
    )
    assert item_without_pin.photo_id == 'photo-123'
    assert item_without_pin.true_pin_id is None


def test_html_favicon_and_pwa_assets_exist() -> None:
    """Verify all local favicon, icon, and manifest asset links in HTML markup resolve to disk."""
    import json

    html_files = [INDEX_HTML, AUDIO_PLAYGROUND_HTML]
    for html_file in html_files:
        assert html_file.exists(), f'{html_file} must exist'
        content = html_file.read_text(encoding='utf-8')
        # Extract href attributes targeting /static/
        static_hrefs = re.findall(r'href=["\'](/static/[^"\'?]+)', content)
        for href in static_hrefs:
            rel_path = href.removeprefix('/static/')
            target_file = STATIC_DIR / rel_path
            assert target_file.exists(), f'File referenced in {html_file.name} not found: {target_file}'

    manifest_file = STATIC_DIR / 'favicons' / 'manifest.json'
    assert manifest_file.exists(), 'manifest.json must exist in static/favicons/'
    manifest_data = json.loads(manifest_file.read_text(encoding='utf-8'))
    for icon in manifest_data.get('icons', []):
        src = icon['src']
        if src.startswith('/static/'):
            rel_path = src.removeprefix('/static/')
            target_file = STATIC_DIR / rel_path
            assert target_file.exists(), f'Icon referenced in manifest.json not found: {target_file}'


def test_game_navigation_guards_and_history_handling() -> None:
    """Verify that browser back button (popstate) and tab-close (beforeunload) confirmation guards are registered."""
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')
    router_js = (JS_DIR / 'modules' / 'router.js').read_text(encoding='utf-8')
    common_js = JS_DIR / 'modules' / 'screens' / 'common.js'
    common_code = common_js.read_text(encoding='utf-8') if common_js.exists() else app_js

    assert 'window.addEventListener("beforeunload", handleBeforeUnload)' in app_js
    assert 'setNavigationGuard(' in app_js
    assert 'initRouter(' in app_js
    assert 'function isGameActive()' in common_code or 'function isGameActive()' in app_js
    assert 'window.addEventListener("popstate"' in router_js


def test_score_rollup_timing_and_audio_coordination() -> None:
    """Verify that score rollup duration benchmarks, single-goal summary bounds, and audio coordination are in place."""
    effects_js = (JS_DIR / 'modules' / 'effects.js').read_text(encoding='utf-8')
    pinpoint_js = (JS_DIR / 'modules' / 'modes' / 'pinpoint.js').read_text(encoding='utf-8')
    album_shuffle_js = (JS_DIR / 'modules' / 'modes' / 'album_shuffle.js').read_text(encoding='utf-8')
    table_js = (JS_DIR / 'modules' / 'summary' / 'table.js').read_text(encoding='utf-8')

    # 1. effects.js must implement centralized active rollup session management
    assert 'let activeRollupSession = null;' in effects_js
    assert 'function registerRollupAnimation' in effects_js
    assert 'function unregisterRollupAnimation' in effects_js
    assert 'function triggerRollupAudioTick' in effects_js

    # 2. pinpoint.js and album_shuffle.js must not dilute total score rollup duration by multiplying round_number
    assert 'maxScore: maxRoundPoints * (reveal.round_number || 1)' not in pinpoint_js
    assert 'maxScore: maxRoundPoints * (revealData.round_number || 1)' not in album_shuffle_js

    # 3. table.js must compute maxGoalScore for single-goal location/date animations
    assert 'maxGoalScore' in table_js
    assert 'animateScoreRollup(locCell, player.location_score ?? 0, maxGoalScore);' in table_js
    assert 'animateScoreRollup(dateCell, player.date_score ?? 0, maxGoalScore);' in table_js


def test_early_routing_prevents_lobby_flash() -> None:
    """Verify that deep link URLs prevent Flash of Incorrect Content (lobby flash) during page bootstrap."""
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    cards_css = (STATIC_DIR / 'css' / 'components' / 'cards.css').read_text(encoding='utf-8')
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')

    # 1. Inline head script in index.html tags non-lobby routes immediately
    assert (
        'document.documentElement.classList.add("route-non-lobby")' in index_html
        or "document.documentElement.classList.add('route-non-lobby')" in index_html
    )

    # 2. CSS immediately hides setup and leaderboard cards under route-non-lobby
    assert 'html.route-non-lobby #setup-card' in cards_css
    assert 'html.route-non-lobby #leaderboard-card' in cards_css

    # 3. app.js removes route-non-lobby on dispatch and initializes router immediately
    assert 'document.documentElement.classList.remove("route-non-lobby")' in app_js
    assert 'ensureLobbyInitialized' in app_js


def test_anti_cheat_timer_persistence_and_resume() -> None:
    """Verify that timer duration remaining is persisted in session storage and passed to startTimer on reload."""
    state_js = (JS_DIR / 'modules' / 'state.js').read_text(encoding='utf-8')
    timer_js = (JS_DIR / 'modules' / 'timer.js').read_text(encoding='utf-8')
    game_js = JS_DIR / 'modules' / 'screens' / 'game.js'
    game_code = (
        game_js.read_text(encoding='utf-8') if game_js.exists() else (JS_DIR / 'app.js').read_text(encoding='utf-8')
    )
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')

    # 1. state.js persists activeQuestionId, timerEndTimeMs, and timerTotalSeconds
    assert 'activeQuestionId: state.currentQuestion?.question_id ?? null' in state_js
    assert 'timerEndTimeMs: typeof state.timerEndTimeMs === "number" ? state.timerEndTimeMs : null' in state_js
    assert 'timerTotalSeconds: typeof state.timerTotalSeconds === "number" ? state.timerTotalSeconds : null' in state_js

    # 2. timer.js supports initialRemainingSeconds parameter
    assert 'export function startTimer(roundLength, getActiveModeFn = null, initialRemainingSeconds = null)' in timer_js

    # 3. game.js / app.js calculates remainingSeconds from session and server data
    assert (
        'startTimer(data.round_length, getActiveMode, remainingSeconds);' in game_code
        or 'startTimer(data.round_length, getActiveMode, remainingSeconds);' in app_js
    )


def test_unknown_route_displays_404_card() -> None:
    """Verify that invalid/unknown routes render a localized 404 card rather than silently falling back to lobby."""
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')
    en_us = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')
    pt_br = (JS_DIR / 'modules' / 'locales' / 'pt_BR.js').read_text(encoding='utf-8')
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    # 1. HTML defines game-ended-icon and does not have static data-i18n attributes on dynamic title/msg
    assert 'id="game-ended-icon"' in index_html
    assert '<h2 id="game-ended-title">Match Ended</h2>' in index_html
    assert '<p id="game-ended-msg" class="ended-card-msg">This match session is no longer active.</p>' in index_html

    # 2. Locale files define 404 title and message strings for both unknown routes and non-existent matches
    assert '"game_ended.not_found_title"' in en_us
    assert '"game_ended.not_found_msg"' in en_us
    assert '"game_ended.match_not_found_title"' in en_us
    assert '"game_ended.match_not_found_msg"' in en_us
    assert '"game_ended.not_found_title"' in pt_br
    assert '"game_ended.not_found_msg"' in pt_br
    assert '"game_ended.match_not_found_title"' in pt_br
    assert '"game_ended.match_not_found_msg"' in pt_br

    # 3. app.js handles RouteType.UNKNOWN explicitly with 404 card
    assert 'case RouteType.UNKNOWN:' in app_js
    assert 't("game_ended.not_found_title")' in app_js
    assert 't("game_ended.not_found_msg"' in app_js
    assert 't("game_ended.match_not_found_title")' in app_js
    assert 't("game_ended.match_not_found_msg"' in app_js


def test_screen_and_player_position_persistence_on_reload() -> None:
    """Verify that current screen (reveal vs guessing vs pass_device) and player state are restored on reload."""
    state_js = (JS_DIR / 'modules' / 'state.js').read_text(encoding='utf-8')
    game_js = JS_DIR / 'modules' / 'screens' / 'game.js'
    game_code = (
        game_js.read_text(encoding='utf-8') if game_js.exists() else (JS_DIR / 'app.js').read_text(encoding='utf-8')
    )
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')

    # 1. state.js tracks currentScreen, lastReveal, and passConfirmed
    assert 'currentScreen: state.currentScreen ?? null' in state_js
    assert 'lastReveal: state.lastReveal ?? null' in state_js
    assert 'passConfirmed: Boolean(state.passConfirmed)' in state_js

    # 2. app.js restores reveal UI without skipping round if reloading on reveal screen
    assert 'if (session.currentScreen === "reveal" && session.lastReveal)' in app_js
    assert 'activeMode.renderReveal(el.revealUi, session.lastReveal);' in app_js

    # 3. game.js / app.js remembers whether pass-device was already confirmed for active question
    assert (
        'session.activeQuestionId === data.question_id && session.passConfirmed' in game_code
        or 'session.activeQuestionId === data.question_id && session.passConfirmed' in app_js
    )

    # 4. pinpoint.js restores quizImage.src from revealData on reload
    pinpoint_js = (JS_DIR / 'modules' / 'modes' / 'pinpoint.js').read_text(encoding='utf-8')
    assert 'el.quizImage.src = mediaUrl;' in pinpoint_js

    # 5. album_shuffle.js hides single-photo mediaFrame on reveal
    shuffle_js = (JS_DIR / 'modules' / 'modes' / 'album_shuffle.js').read_text(encoding='utf-8')
    assert 'if (el.mediaFrame) el.mediaFrame.classList.add("hidden");' in shuffle_js


def test_prepare_game_flow_and_modal_regression() -> None:
    """Verify that Prepare Game launch button, 2-tab modal, and removal of challenges-page-create-btn are respected."""
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    admin_js = (JS_DIR / 'modules' / 'admin.js').read_text(encoding='utf-8')
    challenges_page_js = read_challenges_page_js()
    en_us = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')

    # 1. Prepare Game button is present on setup card
    assert 'id="prepare-game-btn"' in index_html, 'prepare-game-btn missing from index.html'
    assert 'challenges-page-create-btn' not in index_html, (
        'challenges-page-create-btn should be removed from index.html'
    )
    assert 'challenges-page-create-btn' not in challenges_page_js, (
        'challenges-page-create-btn should be removed from challenges_page.js'
    )

    # 2. Prepare Game modal structure has 2 tabs: local and challenge
    assert 'id="prepare-game-modal"' in index_html
    assert 'id="tab-local-game"' in index_html
    assert 'id="tab-challenge-game"' in index_html
    assert 'id="pane-local-game"' in index_html
    assert 'id="pane-challenge-game"' in index_html

    # 3. Local tab contains player input component and start match button
    assert 'id="player-input-root"' in index_html
    assert 'id="player-count-badge"' in index_html
    assert 'id="start-match-btn"' in index_html

    # 4. Challenge tab contains creator name, title, and expiration
    assert 'id="challenge-creator-name-input"' in index_html
    assert 'id="challenge-title-input"' in index_html
    assert 'id="challenge-expiration"' in index_html
    assert 'id="challenge-generate-btn"' in index_html

    # 5. admin.js provides auto-title generation
    assert 'generateAutoChallengeTitle' in admin_js

    # 6. Localization keys exist
    assert '"setup.prepare_game_btn"' in en_us
    assert '"setup.tab_local"' in en_us
    assert '"setup.tab_challenge"' in en_us
    assert '"setup.prepare_modal_title"' in en_us


def test_challenge_share_qr_code_regression() -> None:
    """Verify that QR Code button is placed beside copy link button, and QR component/translations exist."""
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    admin_js = (JS_DIR / 'modules' / 'admin.js').read_text(encoding='utf-8')
    challenge_js = read_challenge_bundle_js()
    qrcode_js = (JS_DIR / 'modules' / 'components' / 'qrcode.js').read_text(encoding='utf-8')
    en_us = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')
    pt_br = (JS_DIR / 'modules' / 'locales' / 'pt_BR.js').read_text(encoding='utf-8')
    modals_css = (STATIC_DIR / 'css' / 'components' / 'modals.css').read_text(encoding='utf-8')

    # 1. QR Code button is positioned alongside Copy Link button in share-url-container
    assert 'id="challenge-copy-link-btn"' in index_html
    assert 'class="copy-btn-text"' in index_html
    assert 'id="challenge-qr-btn"' in index_html
    assert 'class="qr-btn-text"' in index_html
    assert 'id="challenge-qr-container"' in index_html
    assert 'id="challenge-qr-code"' in index_html

    # 2. qrcode.js exports createQRCodeSvg and renderQRCode
    assert 'export function createQRCodeSvg' in qrcode_js
    assert 'export function renderQRCode' in qrcode_js

    # 3. admin.js imports and uses renderQRCode
    assert 'import { renderQRCode } from "./components/qrcode.js"' in admin_js
    assert 'renderQRCode(_qrCodeEl, playUrl' in admin_js

    # 4. challenge module imports and uses renderQRCode
    assert 'renderQRCode' in challenge_js and 'qrcode.js' in challenge_js
    assert 'renderQRCode(inviteQrCode, playUrl' in challenge_js

    # 5. Locales define QR code keys
    for locale in (en_us, pt_br):
        assert '"challenge.qr_code"' in locale
        assert '"challenge.qr_code_title"' in locale
        assert '"challenge.scan_qr_hint"' in locale

    # 6. CSS includes QR container and responsive button styling
    assert '.btn-qr-code' in modals_css
    assert '.challenge-qr-container' in modals_css
    assert '.challenge-qr-display' in modals_css


def test_challenge_mode_disallows_game_restart() -> None:
    """Verify that restart buttons and actions are disallowed during non-local / challenge matches."""
    challenge_js = read_challenge_bundle_js()
    album_shuffle_js = (JS_DIR / 'modules' / 'modes' / 'album_shuffle.js').read_text(encoding='utf-8')
    setup_js = (JS_DIR / 'modules' / 'screens' / 'setup.js').read_text(encoding='utf-8')
    common_js = (JS_DIR / 'modules' / 'screens' / 'common.js').read_text(encoding='utf-8')
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')

    # 1. challenge.js hides restart buttons in question and reveal screens, and restores on reset
    assert 'if (el.gameRestartBtn) el.gameRestartBtn.classList.add("hidden");' in challenge_js
    assert 'if (el.revealRestartBtn) el.revealRestartBtn.classList.add("hidden");' in challenge_js
    assert 'if (el.gameRestartBtn) el.gameRestartBtn.classList.remove("hidden");' in challenge_js
    assert 'if (el.revealRestartBtn) el.revealRestartBtn.classList.remove("hidden");' in challenge_js

    # 2. album_shuffle.js does not append restartBtn when challenge is active
    assert 'if (!challenge || !challenge.isActive()) {' in album_shuffle_js
    assert 'actionsDiv.append(restartBtn, exitBtn);' in album_shuffle_js
    assert 'actionsDiv.append(exitBtn);' in album_shuffle_js

    # 3. setup.js guards restartSameGame and handleAbandonGame
    assert 'state.startingMatch || (challenge && challenge.isActive())' in setup_js
    assert 'action === "restart" && challenge && challenge.isActive()' in setup_js

    # 4. common.js guards confirmAbandonMatch
    assert 'action === "restart" && challenge' in common_js

    # 5. app.js binds guards on restart buttons and keyboard shortcuts
    assert 'bindClick(el.gameRestartBtn, () => {\n  if (challenge.isActive()) return;' in app_js
    assert 'bindClick(el.revealRestartBtn, () => {\n  if (challenge.isActive()) return;' in app_js
    assert 'onRestartMatch: () => {\n    if (challenge.isActive()) {\n      return;' in app_js


def test_challenges_hub_list_updates_language_dynamically() -> None:
    """Verify that challenges-hub-list and hero stats are dynamically updated when language changes."""
    challenges_page_js = read_challenges_page_js()
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')
    index_html = INDEX_HTML.read_text(encoding='utf-8')

    # 1. challenges_page.js exports refreshChallengesPageLanguage
    assert 'export function refreshChallengesPageLanguage()' in challenges_page_js
    assert 'updateHeroStats();' in challenges_page_js
    assert 'renderChallenges();' in challenges_page_js

    # 2. app.js imports and calls refreshChallengesPageLanguage in refreshActiveScreenLanguage
    assert 'refreshChallengesPageLanguage' in app_js
    assert 'refreshChallengesPageLanguage();' in app_js

    # 3. index.html has data-i18n attributes on challenges page components
    assert 'id="challenges-hub-list"' in index_html
    assert 'id="challenges-page-refresh-btn"' in index_html
    assert 'data-i18n-title="challenges_page.refresh_btn"' in index_html


def test_challenges_ui_streamlining_and_minimal_refresh_buttons() -> None:
    """Verify that challenges page hero stats, back button, and detailed top bar are removed,
    replaced by compact badges, and refresh buttons are minimalistic icons.
    """
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    challenges_page_js = read_challenges_page_js()
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')
    buttons_css = (STATIC_DIR / 'css' / 'components' / 'buttons.css').read_text(encoding='utf-8')

    # 1. Removal of hero stats grid & back button from index.html and JS
    assert 'challenges-hero-stats' not in index_html
    assert 'challenges-page-back-btn' not in index_html
    assert 'challenges-hero-stats' not in challenge_css
    assert '_backBtnEl' not in challenges_page_js
    assert 'stat-active-challenges' not in challenges_page_js

    # 2. Compact total badge is inside challenges-toolbar and updated by updateHeroStats
    assert 'id="challenges-page-total-badge"' in index_html
    toolbar_section = index_html[
        index_html.find('class="challenges-toolbar"') : index_html.find('id="challenges-hub-list"')
    ]
    assert 'id="challenges-page-total-badge"' in toolbar_section
    assert '_totalBadgeEl.textContent =' in challenges_page_js

    # 3. Detailed challenge card restructured (top-bar removed, status pill before title, card-time-status in host row)
    assert 'detailed-card-top-bar' not in challenges_page_js
    assert 'card-header-row' in challenges_page_js
    assert 'card-title-wrap' in challenges_page_js
    assert '${statusPillHtml}' in challenges_page_js
    assert 'card-host-row' in challenges_page_js
    assert '${timeStatusHtml}' in challenges_page_js

    # 4. Filter pill prevents line breaking
    assert 'white-space: nowrap;' in challenge_css

    # 5. Minimalistic icon refresh buttons
    assert 'id="challenges-page-refresh-btn" class="btn-icon-action"' in index_html
    assert 'id="refresh-leaderboard" class="btn-icon-action"' in index_html
    assert '.btn-icon-action' in buttons_css


def test_challenge_invite_counter_clarity() -> None:
    """Verify that challenge invite counter expresses count as 'You + this many friends',
    supports zero/one/other pluralization, and updates dynamically on language switch.
    """
    challenge_js = read_challenge_bundle_js()
    i18n_js = (JS_DIR / 'modules' / 'i18n.js').read_text(encoding='utf-8')
    en_us = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')
    pt_br = (JS_DIR / 'modules' / 'locales' / 'pt_BR.js').read_text(encoding='utf-8')

    # 1. challenge.js calculates friends count relative to the current player
    assert 'const friendsCount =' in challenge_js
    assert 'sessionPlayerName' in challenge_js
    assert 'Math.max(0, finishedCount - 1)' in challenge_js
    assert 't("challenge.finisher_count", friendsCount)' in challenge_js

    # 2. challenge.js exposes refreshLanguage for dynamic updates
    assert 'refreshLanguage()' in challenge_js

    # 3. i18n.js supports forms.zero in plural() and t()
    assert 'if (n === 0 && forms.zero)' in i18n_js
    assert '"zero" in entry' in i18n_js

    # 4. English locale defines clear You + friends strings with zero/one/other
    assert '"challenge.finisher_count": {' in en_us
    assert '"zero": "You + 0 friends have finished"' in en_us
    assert '"one": "You + 1 friend has finished"' in en_us
    assert '"other": "You + {count} friends have finished"' in en_us

    # 5. Portuguese locale defines clear Você + amigos strings com zero/one/other
    assert '"challenge.finisher_count": {' in pt_br
    assert '"zero": "Você + 0 amigos concluíram"' in pt_br
    assert '"one": "Você + 1 amigo concluiu"' in pt_br
    assert '"other": "Você + {count} amigos concluíram"' in pt_br

    # 6. challenge-invite screen is shown to all finishers (no auto-transition bypass)
    assert 'finishedCount >= 2' not in challenge_js


def test_home_leaderboard_play_mode_and_accordion_meta() -> None:
    """Verify that home page leaderboard has a PlayMode column and accordion shows match-meta-items."""
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    leaderboard_js = (JS_DIR / 'modules' / 'leaderboard.js').read_text(encoding='utf-8')
    setup_filters_js = (JS_DIR / 'modules' / 'setup_filters.js').read_text(encoding='utf-8')
    filters_css = (STATIC_DIR / 'css' / 'components' / 'filters.css').read_text(encoding='utf-8')
    leaderboard_css = (STATIC_DIR / 'css' / 'components' / 'leaderboard.css').read_text(encoding='utf-8')
    en_us = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')
    pt_br = (JS_DIR / 'modules' / 'locales' / 'pt_BR.js').read_text(encoding='utf-8')

    # 1. Leaderboard table has data-sort="play_mode"
    assert '<th data-sort="play_mode" data-i18n="leaderboard.col_play_mode">' in index_html
    assert 'getPlayModeInfo' in leaderboard_js
    assert 'cellPlayMode' in leaderboard_js
    assert 'col-play-mode' in leaderboard_js
    assert '.playmode-badge' in leaderboard_css
    assert '.playmode-badge.mode-local' in leaderboard_css
    assert '.playmode-badge.mode-challenge' in leaderboard_css
    assert '.playmode-badge.mode-room' in leaderboard_css

    # 2. Locale strings for play mode
    assert '"leaderboard.col_play_mode": "Mode"' in en_us
    assert '"leaderboard.col_play_mode": "Modo"' in pt_br
    assert '"leaderboard.mode_local": "Local"' in en_us
    assert '"leaderboard.mode_challenge": "Challenge"' in en_us
    assert '"leaderboard.mode_challenge": "Desafio"' in pt_br

    # 3. Accordion toggle contains match-meta-items container
    assert 'id="filters-accordion-meta"' in index_html
    assert 'class="match-meta-items filters-accordion-meta"' in index_html
    assert '.filters-accordion-meta' in filters_css
    assert '.filters-accordion.expanded .filters-accordion-meta' in filters_css
    assert 'getMatchMetaCategories' in setup_filters_js
    assert 'renderMatchMetaItemsHtml' in setup_filters_js
    assert 'filters-accordion-meta' in setup_filters_js


def test_reveal_and_all_map_fullscreen_controls() -> None:
    """Verify that reveal-map-fullscreen and all map fullscreen controls are properly wired,
    handled, and bound to shortcuts and click events.
    """
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    state_js = (JS_DIR / 'modules' / 'state.js').read_text(encoding='utf-8')
    maps_js = (JS_DIR / 'modules' / 'maps.js').read_text(encoding='utf-8')
    pinpoint_js = (JS_DIR / 'modules' / 'modes' / 'pinpoint.js').read_text(encoding='utf-8')
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')

    # 1. Elements exist in HTML and state.js
    assert 'id="reveal-map-fullscreen"' in index_html
    assert 'id="guess-map-fullscreen"' in index_html
    assert 'id="journey-map-fullscreen"' in index_html
    assert 'revealMapFullscreen' in state_js
    assert 'revealMapShell' in state_js
    assert 'journeyMapFullscreen' in state_js
    assert 'journeyMapShell' in state_js

    # 2. ensureMapFullscreenButton sets click handler on existing or dynamic button
    assert 'btn.onclick = (e) =>' in maps_js
    assert 'toggleMapFullscreen(shell)' in maps_js

    # 3. toggleMapFullscreen supports active screen shells and document.fullscreenElement exit
    assert 'targetShell =' in maps_js
    assert 'el.revealMapShell' in maps_js
    assert 'el.journeyMapShell' in maps_js
    assert 'el.guessMapShell' in maps_js

    # 4. Global initialization and event listeners
    assert 'initMapFullscreenControls' in maps_js
    assert 'initMapFullscreenControls()' in app_js
    assert 'fullscreenchange' in maps_js
    assert 'syncFullscreenButtons()' in maps_js

    # 5. pinpoint.js wires up revealMapFullscreen and guessMapFullscreen
    assert 'el.revealMapFullscreen.onclick =' in pinpoint_js
    assert 'el.guessMapFullscreen.onclick =' in pinpoint_js
    assert 'L.DomEvent.disableClickPropagation(el.revealMapFullscreen)' in pinpoint_js

    # 6. app.js shortcut handles reveal and summary screens
    assert 'onToggleFullscreen:' in app_js
    assert 'toggleMapFullscreen(el.revealMapShell)' in app_js
    assert 'toggleMapFullscreen(el.journeyMapShell)' in app_js


def test_match_meta_item_time_limit_and_config_support() -> None:
    """Verify that match_meta.js supports reading round_length, game_mode, location_mode,
    and date_mode from both top-level fields and nested data.config (as returned by MatchSummaryResponse),
    and localizes timer values via setup.round_{rawRoundLen}.
    """
    match_meta_js = (JS_DIR / 'modules' / 'components' / 'match_meta.js').read_text(encoding='utf-8')

    # 1. Inspects data.config fallback for round_length, game_mode, location_mode, date_mode
    assert 'const filterConfig = data.config || data;' in match_meta_js
    assert 'data.game_mode || filterConfig.game_mode' in match_meta_js
    assert 'data.location_mode !== undefined ? data.location_mode : filterConfig.location_mode' in match_meta_js
    assert 'data.date_mode !== undefined ? data.date_mode : filterConfig.date_mode' in match_meta_js
    assert 'data.round_length || filterConfig.round_length' in match_meta_js

    # 2. Uses setup.round_{rawRoundLen} translation key for friendly labels (e.g. '2 min')
    assert 'const timerKey = `setup.round_${rawRoundLen}`;' in match_meta_js
    assert 't(timerKey)' in match_meta_js or 'tOr(timerKey' in match_meta_js
    assert 'meta.time_unlimited' in match_meta_js


def test_challenge_error_card_i18n_and_language_refresh() -> None:
    """Verify that challenge-error screen embeds data-i18n attributes and dynamically refreshes
    on language toggle via challenge.refreshLanguage().
    """
    challenge_js = read_challenge_bundle_js()
    en_us = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')
    pt_br = (JS_DIR / 'modules' / 'locales' / 'pt_BR.js').read_text(encoding='utf-8')

    # 1. Error screen embeds data-i18n attributes for title, back button, and error message
    assert 'data-i18n="challenge.error_title"' in challenge_js
    assert 'data-i18n="challenge.back_home"' in challenge_js
    assert 'data-i18n="${key}"' in challenge_js or 'data-i18n=' in challenge_js

    # 2. Tracks current error state and resolves i18n keys
    assert 'this.currentError =' in challenge_js
    assert '"challenge.error_expired"' in challenge_js

    # 4. English and Portuguese define localized error strings
    for locale_content in (en_us, pt_br):
        assert '"challenge.error_title"' in locale_content
        assert '"challenge.error_expired"' in locale_content
        assert '"challenge.back_home"' in locale_content


def test_challenges_page_share_drawer_and_results_button() -> None:
    """Verify that challenges_page.js uses an intuitive share button, expandable QR/link share drawer,
    and converts inactive play buttons into results deep links without duplicate buttons.
    """
    challenges_page_js = read_challenges_page_js()
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')
    en_us = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')
    pt_br = (JS_DIR / 'modules' / 'locales' / 'pt_BR.js').read_text(encoding='utf-8')

    # 1. Imports and invokes renderQRCode for zero-dependency client-side QR generation
    assert 'renderQRCode' in challenges_page_js and 'qrcode.js' in challenges_page_js
    assert 'renderQRCode(' in challenges_page_js

    # 2. Intuitive share button in header with SVG icon & state tracking
    assert 'btn-share-challenge-hub' in challenges_page_js
    assert '.btn-share-challenge-hub' in challenge_css
    assert 'toggleChallengeShare' in challenges_page_js
    assert '_expandedShareDrawers' in challenges_page_js

    # 3. Expandable Share Drawer with QR code display and direct link copying
    assert 'challenge-hub-share-drawer' in challenges_page_js
    assert '.challenge-hub-share-drawer' in challenge_css
    assert 'share-qr-display' in challenges_page_js
    assert 'btn-copy-share-url' in challenges_page_js

    # 4. Challenge cards render Results button (both active & inactive) deep linking to /play/:token/summary
    assert 'btn-results-challenge' in challenges_page_js
    assert '.btn-results-challenge' in challenge_css
    assert 'btn-play-challenge' in challenges_page_js
    assert '/play/${ch.capability_token}/summary' in challenges_page_js
    assert 'navigate(`/play/${token}/summary`)' in challenges_page_js
    assert 'navigate(`/play/${token}`)' in challenges_page_js

    # 5. Redundant footer copy button removed
    assert '.footer-left-actions .btn-copy-challenge-link' not in challenge_css

    # 6. Locale strings for share & results exist in both locales
    for locale in (en_us, pt_br):
        assert '"challenges_page.share_btn"' in locale
        assert '"challenges_page.results_btn"' in locale
        assert '"challenges_page.share_drawer_title"' in locale
        assert '"challenges_page.scan_qr_hint"' in locale


def test_challenge_carousel_layout_standardization_and_mobile_optimization() -> None:
    """Verify that carousel-photo-shell standardizes layout with media-frame,
    uses map-fullscreen-btn, and challenge summary includes mobile responsiveness.
    """
    challenge_js = read_challenge_bundle_js()
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')

    # 1. Carousel photo shell uses media-frame class and SVG map-fullscreen-btn
    assert 'media-frame carousel-photo-shell' in challenge_js
    assert 'map-fullscreen-btn carousel-photo-zoom-btn' in challenge_js
    assert 'viewBox="0 0 24 24"' in challenge_js

    # 2. Grand reveal standings table hides accuracy column on mobile screens and excludes unnecessary avg-round column
    assert '<th class="col-accuracy text-right hide-on-mobile">' in challenge_js
    assert '<td class="col-accuracy text-right hide-on-mobile">' in challenge_js
    assert 'col-avg-round' not in challenge_js
    assert 'summary.col_avg_round' not in challenge_js

    # 3. Carousel photo shell and scatter map shell layout styling in challenge.css
    assert '.carousel-photo-shell {' in challenge_css
    assert 'background: #eef2fb;' in challenge_css
    assert 'border: 1px solid #d5dcec;' in challenge_css
    assert 'height: var(--quiz-map-height, 420px);' in challenge_css

    # 4. Mobile responsive rules defined for grand reveal, carousel, table, and summary actions
    assert '.challenge-grand-reveal' in challenge_css
    assert '.carousel-nav-controls' in challenge_css
    assert '#grand-reveal-table' in challenge_css
    assert '.summary-actions' in challenge_css


def test_challenges_page_standings_rank_column_formatting() -> None:
    """Verify that challenges_page.js correctly formats rank via formatRank instead of formatPlace,
    preventing 'unknown' place string fallback in the standings drawer table.
    """
    formatters_js = (JS_DIR / 'modules' / 'formatters.js').read_text(encoding='utf-8')
    challenges_page_js = read_challenges_page_js()
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')

    # 1. formatters.js exports formatRank function
    assert 'export function formatRank(rank, options = {})' in formatters_js

    # 2. challenges_page.js imports formatRank and does not mis-import formatPlace
    assert 'formatRank' in challenges_page_js
    assert 'formatPlace' not in challenges_page_js

    # 3. challenges_page.js computes rankBadge with formatRank
    assert 'const rankBadge = formatRank(e.rank || idx + 1);' in challenges_page_js
    assert '<td class="col-rank">${rankBadge}</td>' in challenges_page_js

    # 4. Standings table header has matching col-rank class
    assert '<th class="col-rank">${t("challenges_page.rank_col")}</th>' in challenges_page_js

    # 5. challenge.css defines col-rank with width and nowrap
    assert '.col-rank {' in challenge_css
    assert 'width: 50px;' in challenge_css
    assert 'white-space: nowrap;' in challenge_css


def test_standardized_leaderboard_elements_and_layout() -> None:
    """Verify that leaderboard/standings elements (rank badge, player cell, rounds badge,
    table classes) are standardized and reused across leaderboard, summary, and challenge views.
    """
    formatters_js = (JS_DIR / 'modules' / 'formatters.js').read_text(encoding='utf-8')
    leaderboard_js = (JS_DIR / 'modules' / 'leaderboard.js').read_text(encoding='utf-8')
    summary_table_js = (JS_DIR / 'modules' / 'summary' / 'table.js').read_text(encoding='utf-8')
    challenge_js = read_challenge_bundle_js()
    challenges_page_js = read_challenges_page_js()
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')

    # 1. Centralized formatters exist in formatters.js
    assert 'export function createRankBadge(rank, options = {})' in formatters_js
    assert 'export function formatRankBadge(rank, options = {})' in formatters_js
    assert 'export function formatRoundsBadge(completedRounds, totalRounds, isFinished = false)' in formatters_js
    assert 'export function formatPlayerCellHtml(playerName, options = {})' in formatters_js

    # 2. leaderboard.js reuses createRankBadge
    assert 'createRankBadge' in leaderboard_js

    # 3. summary/table.js reuses createRankBadge and standardized classes
    assert 'createRankBadge' in summary_table_js
    assert 'col-rank' in summary_table_js
    assert 'col-player' in summary_table_js

    # 4. challenge.js and challenges_page.js reuse formatRoundsBadge and formatPlayerCellHtml
    assert 'formatRoundsBadge' in challenge_js
    assert 'formatPlayerCellHtml' in challenge_js
    assert 'standings-table' in challenge_js

    assert 'formatRoundsBadge' in challenges_page_js
    assert 'formatPlayerCellHtml' in challenges_page_js
    assert 'standings-table-wrap table-scroll' in challenges_page_js

    # 5. Shared styling in challenge.css
    assert '.standings-table tr.winner-row' in challenge_css
    assert '.winner-crown' in challenge_css
    assert '.col-progress' in challenge_css
    assert '.col-rounds' in challenge_css


def test_card_header_actions_containment_and_share_icon_simplification() -> None:
    """Verify that card-header-actions (share button & deactivate button) are always contained
    inside card-header-row with flex-wrap: nowrap, and btn-share-challenge-hub is simplified
    to just the symbol icon across all screen widths.
    """
    challenges_page_js = read_challenges_page_js()
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')

    # 1. btn-share-text is removed from JavaScript rendering and CSS rules
    assert 'btn-share-text' not in challenges_page_js
    assert 'btn-share-text' not in challenge_css

    # 2. Share button has svg icon, title and accessibility aria-label
    assert 'btn-share-challenge-hub' in challenges_page_js
    assert 'share-icon' in challenges_page_js
    assert 'aria-label="${t("challenges_page.share_btn")}"' in challenges_page_js

    # 3. Deactivate button has icon, title and aria-label
    assert 'btn-deactivate-challenge-hub' in challenges_page_js
    assert 'aria-label="${t("challenges_page.deactivate_btn")}"' in challenges_page_js

    # 4. card-header-row enforces nowrap containment
    assert '.card-header-row {' in challenge_css
    card_header_row_css = challenge_css[
        challenge_css.find('.card-header-row {') : challenge_css.find('.card-title-wrap {')
    ]
    assert 'flex-wrap: nowrap;' in card_header_row_css

    # 5. card-header-actions has flex-shrink: 0 and flex-wrap: nowrap
    assert '.card-header-actions {' in challenge_css
    card_header_actions_css = challenge_css[
        challenge_css.find('.card-header-actions {') : challenge_css.find('.btn-action-icon {')
    ]
    assert 'flex-shrink: 0;' in card_header_actions_css
    assert 'flex-wrap: nowrap;' in card_header_actions_css

    # 6. btn-share-challenge-hub is styled uniformly as 34x34 icon button
    assert '.btn-share-challenge-hub {' in challenge_css
    share_btn_css = challenge_css[
        challenge_css.find('.btn-share-challenge-hub {') : challenge_css.find('.btn-share-challenge-hub svg {')
    ]
    assert 'width: 34px !important;' in share_btn_css
    assert 'height: 34px !important;' in share_btn_css


def test_challenge_gameplay_flow_and_label_integrity() -> None:
    """Verify that date comparison chips use true_date and reveal.js updates state.lastReveal."""
    challenge_dir = JS_DIR / 'modules' / 'challenge'
    summary_js = (challenge_dir / 'summary.js').read_text(encoding='utf-8')
    reveal_js = (challenge_dir / 'reveal.js').read_text(encoding='utf-8')
    en_us_js = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')
    pt_br_js = (JS_DIR / 'modules' / 'locales' / 'pt_BR.js').read_text(encoding='utf-8')

    # 1. Carousel date chip uses challenge.true_date instead of true_location
    assert '${t("challenge.true_date")}:' in summary_js
    assert '${t("challenge.true_location")}:' not in summary_js

    # 2. Grand Reveal summary includes Challenges Hub navigation button
    assert 'grand-reveal-hub-btn' in summary_js
    assert 'navigate("/challenges");' in summary_js

    # 3. reveal.js updates state.lastReveal for state consistency
    assert 'state.lastReveal = formattedReveal;' in reveal_js

    # 4. Translations for true_date and challenges_hub exist in both locales
    assert '"challenge.true_date": "Actual Date"' in en_us_js
    assert '"challenge.true_date": "Data Real"' in pt_br_js
    assert '"challenge.challenges_hub": "Challenges Hub"' in en_us_js
    assert '"challenge.challenges_hub": "Central de Desafios"' in pt_br_js


def test_leaderboard_hidden_during_round_reviews() -> None:
    """Verify that leaderboardCard is hidden in showCard and round review screen modules."""
    common_js = (JS_DIR / 'modules' / 'screens' / 'common.js').read_text(encoding='utf-8')
    screens_reveal_js = (JS_DIR / 'modules' / 'screens' / 'reveal.js').read_text(encoding='utf-8')
    challenge_reveal_js = (JS_DIR / 'modules' / 'challenge' / 'reveal.js').read_text(encoding='utf-8')

    # 1. showCard includes el.leaderboardCard in default card hiding list
    assert 'el.leaderboardCard' in common_js

    # 2. Local reveal explicitly hides leaderboardCard
    assert 'el.leaderboardCard.classList.add("hidden");' in screens_reveal_js

    # 3. Challenge reveal explicitly hides leaderboardCard
    assert 'el.leaderboardCard.classList.add("hidden");' in challenge_reveal_js


def test_dynamic_multiplayer_live_feedback_features() -> None:
    """Verify Options 1 to 4 dynamic real-time feedback implementations across JS, CSS, and locales."""
    toast_js = (JS_DIR / 'modules' / 'components' / 'activity_toast.js').read_text(encoding='utf-8')
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')
    reveal_js = (JS_DIR / 'modules' / 'challenge' / 'reveal.js').read_text(encoding='utf-8')
    summary_js = (JS_DIR / 'modules' / 'challenge' / 'summary.js').read_text(encoding='utf-8')
    en_us_js = (JS_DIR / 'modules' / 'locales' / 'en_US.js').read_text(encoding='utf-8')
    pt_br_js = (JS_DIR / 'modules' / 'locales' / 'pt_BR.js').read_text(encoding='utf-8')

    # 1. Option 1: Activity Toast Component & CSS
    assert 'export function showActivityToast' in toast_js
    assert 'export function clearActivityToasts' in toast_js
    assert '.activity-toast-container' in challenge_css
    assert '.activity-toast' in challenge_css

    # 2. Option 2: Animated Table Row Flash
    assert '.row-arrival-flash' in challenge_css
    assert '@keyframes rowArrivalPulse' in challenge_css
    assert 'flashOpponentRows' in reveal_js
    assert 'row-arrival-flash' in summary_js

    # 3. Option 3: Live Header Activity Badges
    assert '.challenge-live-pill' in challenge_css
    assert 'ensureLivePill' in reveal_js
    assert 'challenge-round-live-pill' in reveal_js
    assert 'grand-reveal-live-pill' in summary_js

    # 4. Option 4: Background Polling for Game Results (Grand Reveal)
    assert 'startSummaryPolling' in summary_js
    assert 'updateSummaryLive' in summary_js
    assert 'renderStandingsRows' in summary_js

    # 5. Locales
    assert '"challenge.player_submitted_round":' in en_us_js
    assert '"challenge.player_submitted_round":' in pt_br_js
    assert '"challenge.player_finished_challenge":' in en_us_js
    assert '"challenge.player_finished_challenge":' in pt_br_js
    assert '"challenge.live_answered_tally":' in en_us_js
    assert '"challenge.live_answered_tally":' in pt_br_js
    assert '"challenge.live_finished_tally":' in en_us_js
    assert '"challenge.live_finished_tally":' in pt_br_js


def test_past_opponent_submissions_do_not_trigger_notifications() -> None:
    """Verify past submissions during initial screen load do not fire activity toasts or row flashes."""
    reveal_js = (JS_DIR / 'modules' / 'challenge' / 'reveal.js').read_text(encoding='utf-8')
    summary_js = (JS_DIR / 'modules' / 'challenge' / 'summary.js').read_text(encoding='utf-8')

    # 1. reveal.js startPolling tracks isInitial and passes it to updateRoundReveal
    assert 'let isInitial = true;' in reveal_js
    assert 'this.updateRoundReveal(data, roundIndex, { isInitial });' in reveal_js
    assert 'isInitial = false;' in reveal_js

    # 2. reveal.js updateRoundReveal guards toasts and row flashes with !isInitial
    assert 'if (!isInitial) {' in reveal_js
    assert 'this.flashOpponentRows(newOpponents);' in reveal_js
    assert 'showActivityToast({' in reveal_js

    # 3. summary.js startSummaryPolling tracks isInitial and passes it to updateSummaryLive
    assert 'let isInitial = true;' in summary_js
    assert 'this.updateSummaryLive(data, { isInitial });' in summary_js
    assert 'if (!isInitial) {' in summary_js


def test_page_buttons_are_standard_links_and_not_toggles() -> None:
    """Verify home and challenges buttons act as normal links with hrefs, allowing open in new tab and not toggling."""
    index_html = INDEX_HTML.read_text(encoding='utf-8')
    buttons_css = (STATIC_DIR / 'css' / 'components' / 'buttons.css').read_text(encoding='utf-8')
    app_js = (JS_DIR / 'app.js').read_text(encoding='utf-8')

    # 1. index.html uses <a> anchors with valid href targets
    assert re.search(r'<a\s+href="/"[^>]*id="home-nav-btn"', index_html) or re.search(
        r'<a\s+[^>]*id="home-nav-btn"[^>]*href="/"', index_html
    )
    assert re.search(r'<a\s+href="/challenges"[^>]*id="challenges-nav-btn"', index_html) or re.search(
        r'<a\s+[^>]*id="challenges-nav-btn"[^>]*href="/challenges"', index_html
    )

    # 2. They are no longer <button> elements
    assert '<button type="button" id="home-nav-btn"' not in index_html
    assert '<button type="button" id="challenges-nav-btn"' not in index_html

    # 3. buttons.css styles header-icon-btn anchors cleanly without text decoration
    assert 'text-decoration: none;' in buttons_css
    assert 'color: inherit;' in buttons_css

    # 4. app.js does not intercept with toggle logic or router.navigate
    assert 'current.type === RouteType.CHALLENGES' not in app_js
    assert 'bindClick(el.homeNavBtn' not in app_js
    assert 'bindClick(el.challengesNavBtn' not in app_js


def test_challenge_album_shuffle_opponent_guesses_display() -> None:
    """Verify that challenge reveal groups round guesses by player and populates album_shuffle_guesses."""
    reveal_js = (JS_DIR / 'modules' / 'challenge' / 'reveal.js').read_text(encoding='utf-8')
    shuffle_js = (JS_DIR / 'modules' / 'modes' / 'album_shuffle.js').read_text(encoding='utf-8')

    # 1. reveal.js groups round_guesses by player and builds albumShuffleGuesses for opponents
    assert 'const guessesByPlayer = new Map();' in reveal_js
    assert 'guessesByPlayer.set(guess.player_name, []);' in reveal_js
    assert 'const isAlbumShuffle =' in reveal_js
    assert 'album_shuffle_guesses: albumShuffleGuesses.length > 0 ? albumShuffleGuesses : null' in reveal_js
    assert 'photo_id: g.asset_id' in reveal_js
    assert 'assigned_pin_id: g.assigned_pin_id || null' in reveal_js
    assert 'assigned_timeline_index:' in reveal_js

    # 2. album_shuffle.js matches photo_id with robust string equality
    assert 'String(g.photo_id) === String(item.photo_id)' in shuffle_js


def test_player_name_cell_and_col_player_nowrap() -> None:
    """Verify that playerNameCell has player-cell class and col-player prevents multi-line wrapping."""
    formatters_js = (JS_DIR / 'modules' / 'formatters.js').read_text(encoding='utf-8')
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')

    # playerNameCell assigns wrap.className = "player-cell"
    assert 'wrap.className = "player-cell";' in formatters_js

    # challenge.css .col-player has white-space: nowrap
    assert '.col-player {\n  font-weight: 600;\n  white-space: nowrap;\n}' in challenge_css


def test_format_month_error_derives_year_month_diff() -> None:
    """Verify that formatMonthError calculates year and month diffs when part breakdown is omitted."""
    formatters_js = (JS_DIR / 'modules' / 'formatters.js').read_text(encoding='utf-8')

    assert '(years === undefined || months === undefined) && result.guessed_year' in formatters_js
    assert 'Math.abs((result.guessed_year - actYear) * 12' in formatters_js
    assert 'if (result.date_diff_days >= 30)' in formatters_js


def test_summary_build_player_stats_supports_batch_modes_and_correct_flags() -> None:
    """Verify that summary.js evaluates perfect rounds across batch guesses using correctness flags."""
    summary_js = (JS_DIR / 'modules' / 'challenge' / 'summary.js').read_text(encoding='utf-8')

    assert 'g.is_correct_location ||' in summary_js
    assert 'g.is_correct_date_order ||' in summary_js
    assert 'const playerRoundGuesses = new Map();' in summary_js
    assert 'allLocPerfect && allDatePerfect && (isLocationEnabled || isDateEnabled)' in summary_js


def test_challenge_title_auto_generation_truncation() -> None:
    """Verify that admin.js smart-truncates auto-generated challenge titles to prevent HTTP 422 errors."""
    admin_js = (JS_DIR / 'modules' / 'admin.js').read_text(encoding='utf-8')

    assert 'maxSummaryLen = 100 - suffix.length;' in admin_js
    assert 'cleanSummary.slice(0, Math.max(10, maxSummaryLen - 1)).trimEnd() + "…"' in admin_js
    assert 'if (title.length > 100)' in admin_js


def test_carousel_photo_img_fit_contain_no_scale_clipping() -> None:
    """Verify that carousel-photo-img uses object-fit: contain without hover scale clipping."""
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')

    assert 'width: auto;\n  height: auto;\n  max-width: 100%;\n  max-height: 100%;' in challenge_css
    assert '.carousel-photo-img:hover {\n  opacity: 0.95;\n}' in challenge_css
    assert '.carousel-photo-img:hover {\n  transform: scale(1.02);\n}' not in challenge_css


def test_challenge_carousel_round_date_comparison_table() -> None:
    """Verify that summary.js renders a structured comparison table instead of chips."""
    summary_js = (JS_DIR / 'modules' / 'challenge' / 'summary.js').read_text(encoding='utf-8')
    challenge_css = (STATIC_DIR / 'css' / 'components' / 'challenge.css').read_text(encoding='utf-8')

    # Verify table markup and sorting in summary.js
    assert 'table class="summary-table round-date-table"' in summary_js
    assert 'date-comp-truth' in summary_js
    assert 'formatMonthError(guessWithActual)' in summary_js
    assert 'formatPlayerCellHtml(g.player_name' in summary_js
    assert 'sort((a, b) => (b.date_points || 0) - (a.date_points || 0)' in summary_js

    # Verify CSS rules exist for table and mobile responsiveness
    assert '.round-date-table {' in challenge_css
    assert '.date-comp-truth {' in challenge_css
    assert '.date-table-scroll {' in challenge_css
    assert '.round-date-table .player-name-text {' in challenge_css
