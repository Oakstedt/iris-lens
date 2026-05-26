import pytest
from unittest.mock import MagicMock

from ui.actions import ActionManager


@pytest.fixture
def mock_window() -> MagicMock:
    """Creates a fake MainWindow with mocked UI components."""
    window = MagicMock()
    
    # Mock the UI elements that ActionManager interacts with
    window.warning_label = MagicMock()
    window.lbl_tenant = MagicMock()
    window.bucket_combo = MagicMock()
    window.btn_read = MagicMock()
    window.file_browser = MagicMock()
    window.status = MagicMock()
    
    return window


@pytest.fixture
def mock_session() -> MagicMock:
    """Creates a fake SessionManager."""
    session = MagicMock()
    
    # Define default fake behaviors
    session.has_credentials.return_value = False
    session.client.connected = False
    
    return session


def test_refresh_state_no_credentials(mock_window: MagicMock, mock_session: MagicMock) -> None:
    """
    TEST: When no credentials exist, the warning label should be visible 
    and the read buttons should be disabled.
    """
    # 1. Setup the fake window's session attribute
    mock_window.session = mock_session
    
    # 2. Instantiate the ActionManager with our fakes
    action_manager = ActionManager(mock_window)
    
    # 3. Execute the method we want to test
    action_manager.refresh_state()
    
    # 4. Assert that the ActionManager did exactly what it was supposed to do
    mock_window.warning_label.setVisible.assert_called_once_with(True)
    mock_window.bucket_combo.setEnabled.assert_called_once_with(False)
    mock_window.btn_read.setEnabled.assert_called_once_with(False)


def test_refresh_state_with_credentials_and_connection(mock_window: MagicMock, mock_session: MagicMock) -> None:
    """
    TEST: When credentials exist and the client is connected, the warning 
    label should hide and the UI should enable.
    """
    # 1. Configure the fake session to simulate a successful connection
    mock_session.has_credentials.return_value = True
    mock_session.client.connected = True
    mock_session.get_tenant_label.return_value = "Connected to Tenant: https://fake-hcp.com"
    mock_session.is_secure_tenant.return_value = True
    mock_session.get_bucket_list.return_value = ["bucket-1", "bucket-2"]
    
    mock_window.session = mock_session
    action_manager = ActionManager(mock_window)
    
    # 2. Execute
    action_manager.refresh_state()
    
    # 3. Assert the UI updated correctly
    mock_window.warning_label.setVisible.assert_called_once_with(False)
    mock_window.lbl_tenant.setText.assert_called_once_with("Connected to Tenant: https://fake-hcp.com")
    mock_window.bucket_combo.setEnabled.assert_called_once_with(True)
    mock_window.btn_read.setEnabled.assert_called_once_with(True)
    
    # Assert that the buckets were actually added to the combo box
    mock_window.bucket_combo.addItems.assert_called_once_with(["bucket-1", "bucket-2"])