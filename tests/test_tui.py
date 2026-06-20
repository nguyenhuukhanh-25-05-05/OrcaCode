import pytest
import re
from pathlib import Path
from core.tui import OrcaTUI
from config.settings import load_config

def test_tui_project_files_caching():
    config = load_config()
    app = OrcaTUI(config=config)
    
    # Verify cached project files behavior
    files = app.get_project_files()
    assert isinstance(files, list)
    
    # Cache should be populated
    assert app._project_files_cached is not None
    
    # Second call should return the cached list
    assert app.get_project_files() is app._project_files_cached

def test_autocomplete_regex_matching():
    # Simulate how OrcaTUI extracts typed pattern for autocomplete
    test_cases = [
        ("Please edit @ad", "ad"),
        ("Check the changes in @core/tui.py", "core/tui.py"),
        ("No suggestions here", None),
        ("Invalid file @@", None),
        ("Selected @file-name.html ", None), # space at the end should not match
        ("@", ""), # just @ should match empty string (displays all files)
    ]
    
    pattern = r'(?:(?<=^)|(?<=\s))@([a-zA-Z0-9_\-./\\]*)$'
    
    for text, expected in test_cases:
        match = re.search(pattern, text)
        if expected is None:
            assert match is None
        else:
            assert match is not None
            assert match.group(1) == expected

def test_composer_input_shortcuts(monkeypatch):
    import core.tui
    import core.tui.utils
    import core.tui.widgets
    clipboard_data = [""]
    _get = lambda: clipboard_data[0]
    _set = lambda text: clipboard_data.__setitem__(0, text) or True
    monkeypatch.setattr(core.tui, "get_clipboard_text", _get)
    monkeypatch.setattr(core.tui, "set_clipboard_text", _set)
    monkeypatch.setattr(core.tui.utils, "get_clipboard_text", _get)
    monkeypatch.setattr(core.tui.utils, "set_clipboard_text", _set)
    monkeypatch.setattr(core.tui.widgets, "get_clipboard_text", _get)
    monkeypatch.setattr(core.tui.widgets, "set_clipboard_text", _set)
    
    try:
        import PIL.ImageGrab
        monkeypatch.setattr(PIL.ImageGrab, "grabclipboard", lambda: None)
    except ImportError:
        pass
    
    from core.tui import ComposerInput, set_clipboard_text, get_clipboard_text
    
    orig = ""
    try:
        set_clipboard_text("test_shortcut")
        assert get_clipboard_text() == "test_shortcut"
        
        # Simulate on_key event
        input_widget = ComposerInput()
        input_widget.text = "Hello World"
        
        # Let's mock the event
        class MockEvent:
            def __init__(self, key):
                self.key = key
                self.prevent_default_called = False
                self.stop_called = False
                
            def prevent_default(self):
                self.prevent_default_called = True
                
            def stop(self):
                self.stop_called = True
                
        # Mocking suggestion list query
        class MockApp:
            def query_one(self, *args, **kwargs):
                raise Exception("no suggestions")
        
        monkeypatch.setattr(ComposerInput, "app", property(lambda self: MockApp()))
        
        # Test ctrl+a selects all
        event_a = MockEvent("ctrl+a")
        input_widget.on_key(event_a)
        assert event_a.prevent_default_called
        assert event_a.stop_called
        assert input_widget.selected_text == "Hello World"
        
        # Test ctrl+c on selection copies text
        set_clipboard_text("")
        event_c = MockEvent("ctrl+c")
        input_widget.on_key(event_c)
        assert event_c.prevent_default_called
        assert event_c.stop_called
        assert get_clipboard_text() == "Hello World"
        
        # Test ctrl+c without selection prevents default / stops but doesn't copy new text
        from textual.document._document import Selection
        input_widget.selection = Selection((0, 0), (0, 0))
        set_clipboard_text("preserved")
        event_c_no_sel = MockEvent("ctrl+c")
        input_widget.on_key(event_c_no_sel)
        assert event_c_no_sel.prevent_default_called
        assert event_c_no_sel.stop_called
        assert get_clipboard_text() == "preserved"
        
        # Restore selection for next tests
        input_widget.select_all()
        
        # Test ctrl+x cuts text
        event_x = MockEvent("ctrl+x")
        input_widget.on_key(event_x)
        assert event_x.prevent_default_called
        assert event_x.stop_called
        assert input_widget.text == ""
        assert get_clipboard_text() == "Hello World"
        
        # Test ctrl+v pastes text
        set_clipboard_text("Pasted Text")
        event_v = MockEvent("ctrl+v")
        input_widget.on_key(event_v)
        assert event_v.prevent_default_called
        assert event_v.stop_called
        assert input_widget.text == "Pasted Text"
    finally:
        set_clipboard_text(orig)


def test_chat_panel_copy_shortcuts(monkeypatch):
    import core.tui
    import core.tui.utils
    import core.tui.widgets
    clipboard_data = [""]
    _get = lambda: clipboard_data[0]
    _set = lambda text: clipboard_data.__setitem__(0, text) or True
    monkeypatch.setattr(core.tui, "get_clipboard_text", _get)
    monkeypatch.setattr(core.tui, "set_clipboard_text", _set)
    monkeypatch.setattr(core.tui.utils, "get_clipboard_text", _get)
    monkeypatch.setattr(core.tui.utils, "set_clipboard_text", _set)
    monkeypatch.setattr(core.tui.widgets, "get_clipboard_text", _get)
    monkeypatch.setattr(core.tui.widgets, "set_clipboard_text", _set)
    
    from core.tui import ChatPanel, set_clipboard_text, get_clipboard_text
    
    orig = ""
    try:
        chat = ChatPanel()
        
        # Mock screen selections
        class MockScreen:
            def __init__(self):
                self.selected_text = ""
                
            def get_selected_text(self):
                return self.selected_text
                
            def _select_all_in_widget(self, widget):
                self.selected_text = "All Chat Content"
                
        screen = MockScreen()
        monkeypatch.setattr(ChatPanel, "screen", property(lambda self: screen))
        
        # Mock write method to avoid side-effects
        written_logs = []
        monkeypatch.setattr(ChatPanel, "write", lambda self, content: written_logs.append(content))
        
        class MockEvent:
            def __init__(self, key):
                self.key = key
                self.prevent_default_called = False
                self.stop_called = False
                
            def prevent_default(self):
                self.prevent_default_called = True
                
            def stop(self):
                self.stop_called = True
                
        # 1. Test ctrl+a selects all in ChatPanel
        event_a = MockEvent("ctrl+a")
        chat.on_key(event_a)
        assert event_a.prevent_default_called
        assert event_a.stop_called
        assert screen.selected_text == "All Chat Content"
        assert any("Đã bôi đen" in log for log in written_logs)
        written_logs.clear()
        
        # 2. Test ctrl+c copies selected text from ChatPanel
        set_clipboard_text("")
        event_c = MockEvent("ctrl+c")
        chat.on_key(event_c)
        assert event_c.prevent_default_called
        assert event_c.stop_called
        assert get_clipboard_text() == "All Chat Content"
        assert any("Đã sao chép" in log for log in written_logs)
    finally:
        set_clipboard_text(orig)


def test_tui_loop_mode_warnings(monkeypatch):
    from core.tui import AutopilotWarningModal
    
    modal = AutopilotWarningModal()
    assert modal is not None
    
    class MockEvent:
        def __init__(self, button_id):
            class MockButton:
                def __init__(self, id):
                    self.id = id
            self.button = MockButton(button_id)
        
        def stop(self):
            pass
            
    dismissed_val = []
    monkeypatch.setattr(AutopilotWarningModal, "dismiss", lambda self, val: dismissed_val.append(val))
    
    modal.on_button_pressed(MockEvent("btn-warning-agree"))
    assert dismissed_val == [True]
    dismissed_val.clear()
    
    modal.on_button_pressed(MockEvent("btn-warning-back"))
    assert dismissed_val == [False]


