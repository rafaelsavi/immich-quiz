import re
from pathlib import Path

STATIC_DIR = Path(__file__).parent.parent / 'static'
PLAYER_INPUT_JS = STATIC_DIR / 'js' / 'modules' / 'components' / 'player_input.js'
PLAYER_INPUT_CSS = STATIC_DIR / 'css' / 'components' / 'player_input.css'
INDEX_HTML = STATIC_DIR / 'index.html'


def test_player_input_js_exists_and_exports_class() -> None:
    assert PLAYER_INPUT_JS.exists(), f'{PLAYER_INPUT_JS} does not exist'
    content = PLAYER_INPUT_JS.read_text(encoding='utf-8')
    assert 'export class PlayerInput' in content


def test_player_input_has_required_methods() -> None:
    content = PLAYER_INPUT_JS.read_text(encoding='utf-8')
    required_methods = [
        '_renderBaseDom',
        '_bindEvents',
        '_isDuplicate',
        '_showFeedback',
        '_clearFeedback',
        'addPlayer',
        'removePlayer',
        'setPlayers',
        'getPlayers',
        '_sync',
        '_renderChips',
        '_updateBadge',
        'focus',
        'showEmptyError',
        'updateLanguage',
    ]
    for method in required_methods:
        pattern = rf'\b{method}\s*\('
        assert re.search(pattern, content), f"Method '{method}' not found in PlayerInput class"


def test_player_input_mobile_and_accessibility_attributes() -> None:
    content = PLAYER_INPUT_JS.read_text(encoding='utf-8')

    # Mobile virtual keyboard attributes
    assert 'autocapitalize="words"' in content
    assert 'autocomplete="off"' in content
    assert 'autocorrect="off"' in content
    assert 'spellcheck="false"' in content
    assert 'enterkeyhint="done"' in content

    # Accessibility attributes
    assert 'role="alert"' in content
    assert 'aria-live="polite"' in content
    assert 'aria-label' in content


def test_player_input_keyboard_and_paste_handling() -> None:
    content = PLAYER_INPUT_JS.read_text(encoding='utf-8')

    assert 'Enter' in content
    assert 'Backspace' in content
    assert 'paste' in content
    assert 'stopPropagation' in content
    assert 'preventDefault' in content


def test_player_input_css_covers_all_component_classes() -> None:
    assert PLAYER_INPUT_CSS.exists(), f'{PLAYER_INPUT_CSS} does not exist'
    css_content = PLAYER_INPUT_CSS.read_text(encoding='utf-8')

    required_classes = [
        '.player-input-group',
        '.player-count-badge',
        '.player-input-container',
        '.player-chip',
        '.player-chip-avatar',
        '.player-chip-name',
        '.player-chip-remove',
        '.player-input-entry-wrap',
        '.player-text-input',
        '.player-add-btn',
        '.player-input-feedback',
    ]

    for class_name in required_classes:
        assert class_name in css_content, f"Class '{class_name}' missing from player_input.css"


def test_player_input_markup_in_index_html() -> None:
    content = INDEX_HTML.read_text(encoding='utf-8')
    assert 'id="player-input-root"' in content
    assert 'id="player-count-badge"' in content
    assert 'id="players"' in content
