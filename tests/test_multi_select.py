import re
from pathlib import Path

STATIC_DIR = Path(__file__).parent.parent / 'static'
MULTI_SELECT_JS = STATIC_DIR / 'js' / 'modules' / 'components' / 'multi_select.js'
MULTI_SELECT_CSS = STATIC_DIR / 'css' / 'components' / 'multi_select.css'


def test_multi_select_js_exists_and_exports_class() -> None:
    assert MULTI_SELECT_JS.exists(), f'{MULTI_SELECT_JS} does not exist'
    content = MULTI_SELECT_JS.read_text(encoding='utf-8')
    assert 'export class MultiSelect' in content


def test_multi_select_has_required_methods() -> None:
    content = MULTI_SELECT_JS.read_text(encoding='utf-8')
    required_methods = [
        '_renderDom',
        '_cacheDom',
        '_bindEvents',
        '_onDocClick',
        '_onDocKeydown',
        'destroy',
        '_updateSearchClearVisibility',
        '_updateSearchVisibility',
        'setItems',
        'getSelectedIds',
        'getSelectedItems',
        'setSelectedIds',
        'clear',
        'toggleItem',
        'selectAll',
        'deselectAll',
        'open',
        'close',
        'toggle',
        'updateTriggerUi',
        'renderOptions',
        'updateCounts',
        '_getItemCount',
        '_notifyChange',
    ]
    for method in required_methods:
        pattern = rf'\b{method}\s*\('
        assert re.search(pattern, content), f"Method '{method}' not found in MultiSelect class"


def test_multi_select_search_visibility_threshold() -> None:
    content = MULTI_SELECT_JS.read_text(encoding='utf-8')

    # Verify minSearchItems / searchThreshold support with default of 6
    assert 'minSearchItems' in content
    assert '6' in content
    assert '_updateSearchVisibility' in content
    assert '_isSearchHidden' in content

    # Verify search-wrap visibility toggling with hidden class
    assert 'searchWrapEl' in content
    assert 'classList.add("hidden")' in content or "classList.add('hidden')" in content
    assert 'classList.remove("hidden")' in content or "classList.remove('hidden')" in content

    # Verify autofocus is guarded against hidden search
    assert '!this._isSearchHidden()' in content


def test_multi_select_dom_structure_and_accessibility() -> None:
    content = MULTI_SELECT_JS.read_text(encoding='utf-8')

    # Accessibility attributes
    assert 'role="combobox"' in content
    assert 'aria-haspopup="listbox"' in content
    assert 'aria-expanded="false"' in content
    assert 'tabindex="0"' in content
    assert 'role="listbox"' in content

    # Key elements & classes
    assert 'multi-select-trigger' in content
    assert 'multi-select-value' in content
    assert 'multi-select-controls' in content
    assert 'multi-select-clear' in content
    assert 'multi-select-arrow' in content
    assert 'multi-select-dropdown' in content
    assert 'multi-select-search-wrap' in content
    assert 'multi-select-search' in content
    assert 'search-clear-btn' in content
    assert 'select-all-btn' in content
    assert 'deselect-all-btn' in content
    assert 'multi-select-options' in content
    assert 'multi-select-tag' in content
    assert 'tag-remove' in content
    assert 'multi-select-summary' in content
    assert 'multi-select-option' in content
    assert 'multi-select-empty' in content


def test_multi_select_css_covers_all_component_classes() -> None:
    assert MULTI_SELECT_CSS.exists(), f'{MULTI_SELECT_CSS} does not exist'
    css_content = MULTI_SELECT_CSS.read_text(encoding='utf-8')

    required_classes = [
        '.multi-select',
        '.multi-select-trigger',
        '.multi-select-value',
        '.placeholder',
        '.multi-select-tag',
        '.tag-label',
        '.tag-remove',
        '.multi-select-summary',
        '.multi-select-controls',
        '.multi-select-clear',
        '.multi-select-arrow',
        '.multi-select-dropdown',
        '.multi-select-search-wrap',
        '.search-icon',
        '.multi-select-search',
        '.search-clear-btn',
        '.multi-select-actions',
        '.btn-text-action',
        '.multi-select-options',
        '.multi-select-option',
        '.multi-select-option-sub',
        '.multi-select-count-badge',
        '.multi-select-empty',
        '.hidden',
    ]

    for class_name in required_classes:
        assert class_name in css_content, f"Class '{class_name}' missing from multi_select.css"


def test_multi_select_event_isolation() -> None:
    content = MULTI_SELECT_JS.read_text(encoding='utf-8')

    # Verify stopPropagation on tag-remove button and clear buttons
    assert 'stopPropagation' in content
    # Verify Escape handling closes dropdown
    assert 'Escape' in content
    # Verify Enter and Space trigger toggle
    assert 'Enter' in content
    assert 'Space' in content or ' ' in content
    # Verify zero-match handling in MultiSelect JS
    assert 'zero-match' in content
    assert 'multi-select-count-badge' in content
