"""Regression tests for the setup-card Bento Control Deck and Prepare Game modal architecture."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT_DIR / 'static' / 'index.html'
CARDS_CSS = ROOT_DIR / 'static' / 'css' / 'components' / 'cards.css'
MODALS_CSS = ROOT_DIR / 'static' / 'css' / 'components' / 'modals.css'
SETUP_FILTERS_JS = ROOT_DIR / 'static' / 'js' / 'modules' / 'setup_filters.js'
ADMIN_JS = ROOT_DIR / 'static' / 'js' / 'modules' / 'admin.js'


def test_setup_card_layout_and_filter_relocation_architecture():
    """Verify that setup-card stacks mode and game settings vertically.

    Also retains relocated filters and segmented controls.
    """
    content = INDEX_HTML.read_text(encoding='utf-8')

    # 1. Vertical group stacking: Mode Selection -> Game Settings -> Match Settings -> Filters -> Actions
    assert 'class="setup-bento-grid"' not in content, 'setup-bento-grid container should be removed'
    mode_idx = content.find('class="form-group mode-selection-group"')
    guess_idx = content.find('class="form-group game-settings-group"')
    match_idx = content.find('class="form-group match-settings-group"')
    filters_idx = content.find('id="filters-accordion"')
    actions_idx = content.find('class="setup-actions-group"')

    assert mode_idx != -1
    assert guess_idx != -1
    assert match_idx != -1
    assert filters_idx != -1
    assert actions_idx != -1

    # Form groups must stack vertically in this exact order
    assert mode_idx < guess_idx < match_idx < filters_idx < actions_idx, (
        'Expected vertical stack: mode-selection -> game-settings -> match-settings -> filters -> actions'
    )

    # 2. Tactile Segmented Controls
    assert 'id="round-count"' in content
    assert 'id="round-length"' in content
    assert 'class="segmented-control"' in content
    assert '<button type="button" class="segmented-btn" data-value="5">5</button>' in content
    assert '<button type="button" class="segmented-btn active" data-value="10">10</button>' in content
    assert '<button type="button" class="segmented-btn" data-value="20">20</button>' in content

    # 3. Prepare game action button
    assert 'id="prepare-game-btn"' in content
    assert 'class="btn-primary btn-prepare-game"' in content

    # 4. Game Mode Help "?" buttons
    assert 'class="mode-option"' in content
    assert 'id="help-pinpoint-btn"' in content
    assert 'id="help-album-shuffle-btn"' in content
    assert 'class="mode-help-btn"' in content


def test_prepare_game_modal_enhancements():
    """Verify modal sheet handle and native share button with share SVG icon."""
    content = INDEX_HTML.read_text(encoding='utf-8')

    assert 'class="modal-sheet-handle"' in content, 'Missing modal-sheet-handle in index.html'
    assert 'id="challenge-share-native-btn"' in content, 'Missing challenge-share-native-btn in index.html'
    assert '<circle cx="18" cy="5" r="3"' in content, 'Missing share icon circle in challenge-share-native-btn'


def test_css_and_js_layout_support():
    """Verify that CSS tokens and JS module bindings support the layout."""
    cards_css = CARDS_CSS.read_text(encoding='utf-8')
    modals_css = MODALS_CSS.read_text(encoding='utf-8')
    setup_filters = SETUP_FILTERS_JS.read_text(encoding='utf-8')
    admin = ADMIN_JS.read_text(encoding='utf-8')

    assert '#setup-card' in cards_css
    assert '#setup-card {\n  overflow: visible;\n}' in cards_css
    assert '.mode-buttons' in cards_css
    assert 'repeat(2, 1fr)' in cards_css
    assert '.segmented-control' in cards_css
    assert '.segmented-btn' in cards_css
    assert '.mode-option' in cards_css
    assert '.mode-help-btn' in cards_css

    assert '.modal-sheet-handle' in modals_css
    assert '@keyframes sheetSlideUp' in modals_css

    assert 'initSegmentedControls' in setup_filters
    assert 'help-pinpoint-btn' in setup_filters
    assert 'help-album-shuffle-btn' in setup_filters
    assert 'challenge-share-native-btn' in admin
