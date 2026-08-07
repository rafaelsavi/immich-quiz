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
        return

    syntax_errors: list[str] = []
    for js_file in JS_DIR.rglob('*.js'):
        res = subprocess.run([node_bin, '--check', str(js_file)], capture_output=True, text=True)
        if res.returncode != 0:
            rel_file = js_file.relative_to(STATIC_DIR)
            syntax_errors.append(f'{rel_file}: {res.stderr.strip()}')

    assert not syntax_errors, f'JavaScript syntax errors found:\n{chr(10).join(syntax_errors)}'
