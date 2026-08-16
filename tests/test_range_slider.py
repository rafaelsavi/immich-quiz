import re
from pathlib import Path

STATIC_DIR = Path(__file__).parent.parent / 'static'
RANGE_SLIDER_JS = STATIC_DIR / 'js' / 'modules' / 'components' / 'range_slider.js'
RANGE_SLIDER_CSS = STATIC_DIR / 'css' / 'components' / 'range_slider.css'
FILTERS_CSS = STATIC_DIR / 'css' / 'components' / 'filters.css'
STYLE_CSS = STATIC_DIR / 'css' / 'style.css'
INDEX_HTML = STATIC_DIR / 'index.html'
I18N_JS = STATIC_DIR / 'js' / 'modules' / 'i18n.js'


def test_range_slider_js_exists_and_exports_class() -> None:
    assert RANGE_SLIDER_JS.exists(), f'{RANGE_SLIDER_JS} does not exist'
    content = RANGE_SLIDER_JS.read_text(encoding='utf-8')
    assert 'export class DateRangeSlider' in content


def test_range_slider_has_required_methods() -> None:
    content = RANGE_SLIDER_JS.read_text(encoding='utf-8')
    required_methods = [
        '_bindEvents',
        'destroy',
        '_generateMonthSpan',
        '_formatMonth',
        'setBounds',
        'setSelectedRange',
        'getSelectedRange',
        'updateVisuals',
        'reset',
    ]
    for method in required_methods:
        pattern = rf'\b{method}\s*\('
        assert re.search(pattern, content), f"Method '{method}' not found in DateRangeSlider class"


def test_range_slider_month_span_logic() -> None:
    content = RANGE_SLIDER_JS.read_text(encoding='utf-8')

    # Verify generateMonthSpan logic in JS
    assert 'startYear' in content or 'split("-")' in content
    assert 'curMonth' in content or 'curYear' in content
    assert 'padStart(2, "0")' in content

    # Verify date calculation for start of month and last day of month
    assert '-01' in content
    assert 'Date.UTC' in content


def test_range_slider_crossover_prevention_and_bounds() -> None:
    content = RANGE_SLIDER_JS.read_text(encoding='utf-8')

    # Thumbs crossover protection
    assert 'minVal > maxVal' in content
    assert 'maxVal < minVal' in content

    # Full span returns null dates
    assert 'minDate: null, maxDate: null' in content
    assert 'isFullSpan' in content or 'minIdx === 0' in content


def test_range_slider_css_classes() -> None:
    assert RANGE_SLIDER_CSS.exists(), f'{RANGE_SLIDER_CSS} does not exist'
    content = RANGE_SLIDER_CSS.read_text(encoding='utf-8')

    required_classes = [
        '.date-slider-group',
        '.field-head-inline',
        '.slider-value-readout',
        '.range-slider-wrap',
        '.range-slider-track',
        '.range-slider-fill',
        '.range-thumb',
        '.range-slider-ticks',
    ]
    for cls in required_classes:
        assert cls in content, f"Class '{cls}' missing from range_slider.css"


def test_filters_css_classes() -> None:
    assert FILTERS_CSS.exists(), f'{FILTERS_CSS} does not exist'
    content = FILTERS_CSS.read_text(encoding='utf-8')

    required_classes = [
        '.filters-accordion',
        '.filters-accordion-header',
        '.accordion-title-wrap',
        '.accordion-icon',
        '.accordion-meta-wrap',
        '.filters-summary-badge',
        '.accordion-arrow',
        '.filters-accordion-content',
        '.filters-sub-grid',
        '.filters-footer-actions',
        '.people-mode-toggle',
        '.people-mode-btn',
    ]
    for cls in required_classes:
        assert cls in content, f"Class '{cls}' missing from filters.css"


def test_style_css_imports_filter_components() -> None:
    assert STYLE_CSS.exists(), f'{STYLE_CSS} does not exist'
    content = STYLE_CSS.read_text(encoding='utf-8')
    assert '@import "./components/filters.css";' in content
    assert '@import "./components/range_slider.css";' in content


def test_index_html_contains_accordion_and_filter_containers() -> None:
    assert INDEX_HTML.exists(), f'{INDEX_HTML} does not exist'
    content = INDEX_HTML.read_text(encoding='utf-8')

    required_ids = [
        'filters-accordion',
        'filters-toggle-btn',
        'filters-summary-badge',
        'filters-accordion-content',
        'library',
        'album-multi-select',
        'date-slider-readout',
        'date-range-slider',
        'date-slider-fill',
        'date-slider-min',
        'date-slider-max',
        'date-slider-bound-min',
        'date-slider-bound-max',
        'country-multi-select',
        'city-multi-select',
        'people-mode-toggle',
        'people-multi-select',
        'reset-filters-btn',
        'preflight-count',
    ]
    for elem_id in required_ids:
        assert f'id="{elem_id}"' in content, f"Element id='{elem_id}' missing from index.html"

    # Preflight count is nested inside filters accordion
    content_idx = content.find('id="filters-accordion-content"')
    assert content_idx != -1, 'filters-accordion-content div not found'
    next_group_idx = content.find('class="form-group mode-selection-group"', content_idx)
    accordion_section = content[content_idx:next_group_idx]
    assert 'id="preflight-count"' in accordion_section, (
        'preflight-count element must be inside filters-accordion-content'
    )

    # Accessibility & Mode buttons
    assert 'aria-expanded="false"' in content
    assert 'data-people-mode="ANY"' in content
    assert 'data-people-mode="ALL"' in content


def test_bilingual_i18n_keys_present() -> None:
    assert I18N_JS.exists(), f'{I18N_JS} does not exist'
    content = I18N_JS.read_text(encoding='utf-8')

    required_keys = [
        'setup.filters_heading',
        'setup.filters_summary_default',
        'setup.filters_active_count',
        'setup.reset_filters',
        'setup.date_range_label',
        'setup.all_dates',
        'setup.countries_label',
        'setup.all_countries',
        'setup.country_search_placeholder',
        'setup.no_countries_found',
        'setup.countries_selected',
        'setup.cities_label',
        'setup.all_cities',
        'setup.city_search_placeholder',
        'setup.no_cities_found',
        'setup.cities_selected',
        'setup.people_label',
        'setup.all_people',
        'setup.people_search_placeholder',
        'setup.no_people_found',
        'setup.people_selected',
        'setup.people_mode_any',
        'setup.people_mode_all',
        'setup.filter_people',
        'setup.filter_people_all',
        'setup.filter_countries',
        'setup.filter_cities',
        'setup.filter_date_range',
        'setup.challenges_hint',
        'mode.pinpoint.goal_location_desc',
        'mode.pinpoint.goal_date_desc',
        'mode.album_shuffle.goal_location_desc',
        'mode.album_shuffle.goal_date_desc',
        'setup.preflight_count_both',
        'setup.preflight_count_gps',
        'setup.preflight_count_date',
        'setup.preflight_count_all',
        'setup.preflight_count_breakdown_tooltip',
    ]

    for key in required_keys:
        matches = len(re.findall(rf'"{re.escape(key)}":', content))
        assert matches >= 2, f"Key '{key}' should exist in both EN and PT dictionaries (found {matches} occurrences)"
