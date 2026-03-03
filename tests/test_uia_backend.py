"""Tests for src.utils.uia_backend — UI Automation element discovery."""
import sys
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


# ---------------------------------------------------------------------------
# is_uia_available
# ---------------------------------------------------------------------------
class TestIsUiaAvailable:
    def test_returns_bool(self):
        from src.utils.uia_backend import is_uia_available
        result = is_uia_available()
        assert isinstance(result, bool)

    def test_graceful_when_not_installed(self):
        """Should return False without crashing if uiautomation isn't installed."""
        import src.utils.uia_backend as mod
        # Reset cached state
        mod._uia_checked = False
        mod._uia = None

        with patch.dict("sys.modules", {"uiautomation": None}):
            with patch("builtins.__import__", side_effect=ImportError("no module")):
                mod._uia_checked = False
                mod._uia = None
                result = mod.is_uia_available()
                assert result is False

        # Reset for other tests
        mod._uia_checked = False
        mod._uia = None


# ---------------------------------------------------------------------------
# _control_to_dict
# ---------------------------------------------------------------------------
class TestControlToDict:
    def test_converts_valid_control(self):
        from src.utils.uia_backend import _control_to_dict

        mock_ctrl = MagicMock()
        mock_rect = MagicMock()
        mock_rect.left = 100
        mock_rect.top = 200
        mock_rect.right = 300
        mock_rect.bottom = 250
        mock_rect.width.return_value = 200
        mock_rect.height.return_value = 50
        mock_ctrl.BoundingRectangle = mock_rect
        mock_ctrl.Name = "OK"
        mock_ctrl.ControlTypeName = "ButtonControl"
        mock_ctrl.ClassName = "Button"
        mock_ctrl.AutomationId = "btnOK"
        mock_ctrl.IsEnabled = True

        result = _control_to_dict(mock_ctrl)
        assert result is not None
        assert result["name"] == "OK"
        assert result["control_type"] == "button"
        assert result["class_name"] == "Button"
        assert result["automation_id"] == "btnOK"
        assert result["center"]["x"] == 200  # (100+200)/2 = 200
        assert result["center"]["y"] == 225  # (200+250)/2... wait 200+50/2=225
        assert result["is_enabled"] is True
        assert result["is_interactive"] is True

    def test_skips_zero_size_control(self):
        from src.utils.uia_backend import _control_to_dict

        mock_ctrl = MagicMock()
        mock_rect = MagicMock()
        mock_rect.width.return_value = 0
        mock_rect.height.return_value = 0
        mock_ctrl.BoundingRectangle = mock_rect

        result = _control_to_dict(mock_ctrl)
        assert result is None

    def test_skips_offscreen_control(self):
        from src.utils.uia_backend import _control_to_dict

        mock_ctrl = MagicMock()
        mock_rect = MagicMock()
        mock_rect.width.return_value = 100
        mock_rect.height.return_value = 30
        mock_rect.right = -10
        mock_rect.bottom = -10
        mock_ctrl.BoundingRectangle = mock_rect

        result = _control_to_dict(mock_ctrl)
        assert result is None

    def test_handles_exception_gracefully(self):
        from src.utils.uia_backend import _control_to_dict

        mock_ctrl = MagicMock()
        mock_ctrl.BoundingRectangle = PropertyMock(side_effect=Exception("access denied"))

        result = _control_to_dict(mock_ctrl)
        assert result is None

    def test_non_interactive_type(self):
        from src.utils.uia_backend import _control_to_dict

        mock_ctrl = MagicMock()
        mock_rect = MagicMock()
        mock_rect.left = 10
        mock_rect.top = 10
        mock_rect.right = 100
        mock_rect.bottom = 30
        mock_rect.width.return_value = 90
        mock_rect.height.return_value = 20
        mock_ctrl.BoundingRectangle = mock_rect
        mock_ctrl.Name = "Status"
        mock_ctrl.ControlTypeName = "TextControl"
        mock_ctrl.ClassName = "TextBlock"
        mock_ctrl.AutomationId = ""
        mock_ctrl.IsEnabled = True

        result = _control_to_dict(mock_ctrl)
        assert result is not None
        assert result["control_type"] == "text"
        assert result["is_interactive"] is False


# ---------------------------------------------------------------------------
# find_uia_elements (with mocked uiautomation)
# ---------------------------------------------------------------------------
class TestFindUiaElements:
    @patch("src.utils.uia_backend.is_uia_available", return_value=False)
    def test_raises_when_not_available(self, mock_avail):
        from src.utils.uia_backend import find_uia_elements

        with pytest.raises(ImportError, match="uiautomation is not installed"):
            find_uia_elements(hwnd=12345)

    @patch("src.utils.uia_backend._get_uia")
    def test_returns_empty_for_nonexistent_window(self, mock_get_uia):
        from src.utils.uia_backend import find_uia_elements

        mock_uia = MagicMock()
        mock_uia.ControlFromHandle.side_effect = Exception("not found")
        mock_get_uia.return_value = mock_uia

        result = find_uia_elements(hwnd=99999)
        assert result == []

    @patch("src.utils.uia_backend._get_uia")
    def test_returns_empty_when_no_elements(self, mock_get_uia):
        from src.utils.uia_backend import find_uia_elements

        mock_uia = MagicMock()
        mock_root = MagicMock()

        # Root has no children
        mock_root.GetFirstChildControl.return_value = None
        # Root itself has zero-size rect
        mock_rect = MagicMock()
        mock_rect.width.return_value = 0
        mock_rect.height.return_value = 0
        mock_root.BoundingRectangle = mock_rect

        mock_uia.ControlFromHandle.return_value = mock_root
        mock_get_uia.return_value = mock_uia

        result = find_uia_elements(hwnd=12345)
        assert result == []

    @patch("src.utils.uia_backend._get_uia")
    def test_finds_button_element(self, mock_get_uia):
        from src.utils.uia_backend import find_uia_elements

        mock_uia = MagicMock()

        # Create a root control with one button child
        mock_root = MagicMock()
        # Root rect (zero-size, won't be added)
        root_rect = MagicMock()
        root_rect.width.return_value = 0
        root_rect.height.return_value = 0
        mock_root.BoundingRectangle = root_rect
        mock_root.Name = ""
        mock_root.ControlTypeName = "WindowControl"
        mock_root.ClassName = ""
        mock_root.AutomationId = ""
        mock_root.IsEnabled = True

        # Button child
        mock_button = MagicMock()
        btn_rect = MagicMock()
        btn_rect.left = 50
        btn_rect.top = 100
        btn_rect.right = 150
        btn_rect.bottom = 130
        btn_rect.width.return_value = 100
        btn_rect.height.return_value = 30
        mock_button.BoundingRectangle = btn_rect
        mock_button.Name = "Save"
        mock_button.ControlTypeName = "ButtonControl"
        mock_button.ClassName = "Button"
        mock_button.AutomationId = "btnSave"
        mock_button.IsEnabled = True
        mock_button.GetFirstChildControl.return_value = None

        mock_root.GetFirstChildControl.return_value = mock_button
        mock_button.GetNextSiblingControl.return_value = None

        mock_uia.ControlFromHandle.return_value = mock_root
        mock_get_uia.return_value = mock_uia

        result = find_uia_elements(hwnd=12345)
        assert len(result) == 1
        assert result[0]["name"] == "Save"
        assert result[0]["control_type"] == "button"
        assert result[0]["center"]["x"] == 100
        assert result[0]["center"]["y"] == 115

    @patch("src.utils.uia_backend._get_uia")
    def test_respects_max_results(self, mock_get_uia):
        from src.utils.uia_backend import find_uia_elements

        mock_uia = MagicMock()
        mock_root = MagicMock()
        root_rect = MagicMock()
        root_rect.width.return_value = 0
        root_rect.height.return_value = 0
        mock_root.BoundingRectangle = root_rect
        mock_root.Name = ""
        mock_root.ControlTypeName = "WindowControl"
        mock_root.ClassName = ""
        mock_root.AutomationId = ""
        mock_root.IsEnabled = True

        # Create 5 sibling buttons
        buttons = []
        for i in range(5):
            btn = MagicMock()
            r = MagicMock()
            r.left = i * 100
            r.top = 10
            r.right = (i + 1) * 100
            r.bottom = 40
            r.width.return_value = 100
            r.height.return_value = 30
            btn.BoundingRectangle = r
            btn.Name = f"Button{i}"
            btn.ControlTypeName = "ButtonControl"
            btn.ClassName = "Button"
            btn.AutomationId = f"btn{i}"
            btn.IsEnabled = True
            btn.GetFirstChildControl.return_value = None
            buttons.append(btn)

        # Chain siblings
        for i, btn in enumerate(buttons):
            btn.GetNextSiblingControl.return_value = buttons[i + 1] if i + 1 < len(buttons) else None

        mock_root.GetFirstChildControl.return_value = buttons[0]
        mock_uia.ControlFromHandle.return_value = mock_root
        mock_get_uia.return_value = mock_uia

        result = find_uia_elements(hwnd=12345, max_results=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# find_uia_element_by_name
# ---------------------------------------------------------------------------
class TestFindUiaElementByName:
    @patch("src.utils.uia_backend.find_uia_elements")
    def test_returns_first_match(self, mock_find):
        from src.utils.uia_backend import find_uia_element_by_name

        mock_find.return_value = [
            {"name": "Save", "control_type": "button", "center": {"x": 100, "y": 50}},
        ]

        result = find_uia_element_by_name("Save", hwnd=12345)
        assert result is not None
        assert result["name"] == "Save"

    @patch("src.utils.uia_backend.find_uia_elements")
    def test_returns_none_when_not_found(self, mock_find):
        from src.utils.uia_backend import find_uia_element_by_name

        mock_find.return_value = []

        result = find_uia_element_by_name("NonExistent", hwnd=12345)
        assert result is None
