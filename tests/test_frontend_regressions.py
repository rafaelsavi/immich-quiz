from pathlib import Path


def test_ready_btn_element_binding_is_defined() -> None:
    state_source = Path('static/js/modules/state.js').read_text(encoding='utf-8')

    assert 'get readyBtn()' in state_source
    assert 'document.getElementById("ready-btn")' in state_source


def test_ready_btn_event_binding_is_guarded() -> None:
    app_source = Path('static/js/app.js').read_text(encoding='utf-8')

    assert 'if (el.readyBtn)' in app_source
