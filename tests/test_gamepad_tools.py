import sys
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


@pytest.fixture(autouse=True)
def _reset_gamepad_state():
    """Reset the module-level _active_gamepad between tests."""
    import src.tools.gamepad as gp_mod

    gp_mod._active_gamepad = None
    yield
    gp_mod._active_gamepad = None


class TestGamepadConnect:
    @patch("src.tools.gamepad.vgamepad")
    def test_connect_creates_controller(self, mock_vg):
        from src.tools.gamepad import gamepad_connect

        mock_vg.VX360Gamepad.return_value = MagicMock()
        result = gamepad_connect()
        assert result["success"] is True
        assert "connected" in result["message"].lower()
        mock_vg.VX360Gamepad.assert_called_once()

    @patch("src.tools.gamepad.vgamepad")
    def test_connect_twice_returns_already_connected(self, mock_vg):
        from src.tools.gamepad import gamepad_connect

        mock_vg.VX360Gamepad.return_value = MagicMock()
        gamepad_connect()
        result = gamepad_connect()
        assert result["success"] is True
        assert "already" in result["message"].lower()
        # Should only have created the gamepad once
        mock_vg.VX360Gamepad.assert_called_once()

    @patch("src.tools.gamepad.vgamepad", None)
    def test_connect_without_vgamepad_installed(self):
        from src.tools.gamepad import gamepad_connect

        result = gamepad_connect()
        assert result["success"] is False
        assert "not installed" in result["error"].lower()
        assert "suggestion" in result

    @patch("src.tools.gamepad.vgamepad")
    def test_connect_handles_driver_error(self, mock_vg):
        from src.tools.gamepad import gamepad_connect

        mock_vg.VX360Gamepad.side_effect = Exception("ViGEmBus not found")
        result = gamepad_connect()
        assert result["success"] is False
        assert "ViGEmBus" in result["error"]
        assert "suggestion" in result


class TestGamepadInput:
    @patch("src.tools.gamepad.vgamepad")
    def test_input_without_connect_returns_error(self, mock_vg):
        from src.tools.gamepad import gamepad_input

        result = gamepad_input(buttons=["A"])
        assert result["success"] is False
        assert "no gamepad" in result["error"].lower()

    @patch("src.tools.gamepad.vgamepad")
    def test_input_presses_buttons(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_input

        mock_pad = MagicMock()
        gp_mod._active_gamepad = mock_pad

        # Set up button enum values on the mock vgamepad
        mock_vg.XUSB_BUTTON.XUSB_GAMEPAD_A = "BTN_A"
        mock_vg.XUSB_BUTTON.XUSB_GAMEPAD_X = "BTN_X"

        result = gamepad_input(buttons=["A", "X"])
        assert result["success"] is True
        assert mock_pad.press_button.call_count == 2
        mock_pad.update.assert_called_once()

    @patch("src.tools.gamepad.vgamepad")
    def test_input_sets_left_stick(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_input

        mock_pad = MagicMock()
        gp_mod._active_gamepad = mock_pad

        result = gamepad_input(left_stick={"x": 0.5, "y": -0.3})
        assert result["success"] is True
        mock_pad.left_joystick_float.assert_called_once_with(
            x_value_float=0.5, y_value_float=-0.3
        )

    @patch("src.tools.gamepad.vgamepad")
    def test_input_sets_right_stick(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_input

        mock_pad = MagicMock()
        gp_mod._active_gamepad = mock_pad

        result = gamepad_input(right_stick={"x": -1.0, "y": 1.0})
        assert result["success"] is True
        mock_pad.right_joystick_float.assert_called_once_with(
            x_value_float=-1.0, y_value_float=1.0
        )

    @patch("src.tools.gamepad.vgamepad")
    def test_input_sets_triggers(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_input

        mock_pad = MagicMock()
        gp_mod._active_gamepad = mock_pad

        result = gamepad_input(left_trigger=0.8, right_trigger=0.5)
        assert result["success"] is True
        mock_pad.left_trigger_float.assert_called_once_with(value_float=0.8)
        mock_pad.right_trigger_float.assert_called_once_with(value_float=0.5)

    @patch("src.tools.gamepad.vgamepad")
    def test_input_clamps_stick_values(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_input

        mock_pad = MagicMock()
        gp_mod._active_gamepad = mock_pad

        result = gamepad_input(left_stick={"x": 5.0, "y": -5.0})
        assert result["success"] is True
        mock_pad.left_joystick_float.assert_called_once_with(
            x_value_float=1.0, y_value_float=-1.0
        )

    @patch("src.tools.gamepad.vgamepad")
    def test_input_clamps_trigger_values(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_input

        mock_pad = MagicMock()
        gp_mod._active_gamepad = mock_pad

        result = gamepad_input(left_trigger=2.0, right_trigger=-0.5)
        assert result["success"] is True
        mock_pad.left_trigger_float.assert_called_once_with(value_float=1.0)
        mock_pad.right_trigger_float.assert_called_once_with(value_float=0.0)

    @patch("src.tools.gamepad.vgamepad")
    def test_input_ignores_unknown_buttons(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_input

        mock_pad = MagicMock()
        gp_mod._active_gamepad = mock_pad

        result = gamepad_input(buttons=["NONEXISTENT"])
        assert result["success"] is True
        mock_pad.press_button.assert_not_called()


class TestGamepadDisconnect:
    def test_disconnect_without_connect_returns_success(self):
        from src.tools.gamepad import gamepad_disconnect

        result = gamepad_disconnect()
        assert result["success"] is True
        assert "no gamepad" in result["message"].lower()

    @patch("src.tools.gamepad.vgamepad")
    def test_disconnect_resets_and_clears_gamepad(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_disconnect

        mock_pad = MagicMock()
        gp_mod._active_gamepad = mock_pad

        result = gamepad_disconnect()
        assert result["success"] is True
        assert "disconnected" in result["message"].lower()
        mock_pad.reset.assert_called_once()
        mock_pad.update.assert_called_once()
        assert gp_mod._active_gamepad is None

    @patch("src.tools.gamepad.vgamepad")
    def test_disconnect_handles_error_and_clears_gamepad(self, mock_vg):
        import src.tools.gamepad as gp_mod
        from src.tools.gamepad import gamepad_disconnect

        mock_pad = MagicMock()
        mock_pad.reset.side_effect = Exception("Device error")
        gp_mod._active_gamepad = mock_pad

        result = gamepad_disconnect()
        assert result["success"] is False
        assert "Device error" in result["error"]
        # Should still clear the reference even on error
        assert gp_mod._active_gamepad is None
