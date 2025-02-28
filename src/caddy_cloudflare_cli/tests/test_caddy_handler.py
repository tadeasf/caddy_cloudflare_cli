"""
Tests for Caddy proxy handler
"""
import os
import signal
import subprocess
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, mock_open

from caddy_cloudflare_cli.lib.proxy.caddy import CaddyProxy
from caddy_cloudflare_cli.lib.proxy.base import ProxyConfig, ProxyError
from caddy_cloudflare_cli.lib.config import Config

@pytest.fixture
def config():
    """Mock configuration"""
    return Config(domain="example.com", cloudflare_token="test-token")

@pytest.fixture
def proxy_config():
    """Mock proxy configuration"""
    return ProxyConfig(
        domain="test.example.com",
        target="localhost:8080",
        ssl=True,
        additional_config=None
    )

@pytest.fixture
def proxy_handler(config):
    """Mock proxy handler"""
    return CaddyProxy(config)

@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file"""
    config_file = tmp_path / "Caddyfile"
    config_file.write_text("test config")
    return config_file

def test_init(proxy_handler, config):
    """Test initialization"""
    assert proxy_handler.config == config
    assert proxy_handler.binary_path == config.get_binary_path()
    assert proxy_handler.dirs == config.get_proxy_dirs()

def test_restore_process_no_pid(proxy_handler):
    """Test process restoration with no PID file"""
    with patch('pathlib.Path.exists', return_value=False):
        proxy_handler._restore_process()
        assert proxy_handler._process is None

def test_restore_process_invalid_pid(proxy_handler):
    """Test process restoration with invalid PID"""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value="invalid"), \
         patch('pathlib.Path.unlink'):
        proxy_handler._restore_process()
        assert proxy_handler._process is None

def test_restore_process_nonexistent_pid(proxy_handler):
    """Test process restoration with nonexistent PID"""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.read_text', return_value="99999"), \
         patch('os.kill', side_effect=ProcessLookupError), \
         patch('pathlib.Path.unlink'):
        proxy_handler._restore_process()
        assert proxy_handler._process is None

def test_generate_config_success(proxy_handler, proxy_config):
    """Test successful configuration generation"""
    with patch('pathlib.Path.write_text') as mock_write:
        config_path = proxy_handler.generate_config(proxy_config)
        assert mock_write.called
        assert "test.example.com" in mock_write.call_args[0][0]
        assert "localhost:8080" in mock_write.call_args[0][0]
        assert str(config_path).endswith('Caddyfile')

def test_validate_config_success(proxy_handler, temp_config_file):
    """Test successful configuration validation"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        assert proxy_handler.validate_config(str(temp_config_file)) is True

def test_validate_config_failure(proxy_handler, temp_config_file):
    """Test configuration validation failure"""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, [], stderr="Invalid config")
        assert proxy_handler.validate_config(str(temp_config_file)) is False

def test_start_success(proxy_handler, temp_config_file):
    """Test successful server start"""
    with patch('subprocess.Popen') as mock_popen, \
         patch('time.sleep'):
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        status = proxy_handler.start(temp_config_file)

        assert status.running is True
        assert status.pid == 12345
        assert status.config_file == temp_config_file

def test_start_failure(proxy_handler, temp_config_file):
    """Test server start failure"""
    with patch('subprocess.Popen') as mock_popen, \
         patch('time.sleep'):
        mock_process = Mock()
        mock_process.poll.return_value = 1
        mock_process.stderr.read.return_value = b"Start failed"
        mock_popen.return_value = mock_process

        status = proxy_handler.start(temp_config_file)

        assert status.running is False
        assert status.error == "Failed to start Caddy: Start failed"

def test_stop_success(proxy_handler):
    """Test successful server stop"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        assert proxy_handler.stop() is True

def test_stop_failure(proxy_handler):
    """Test server stop failure"""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, [], stderr="Stop failed")
        assert proxy_handler.stop() is False

def test_reload_success(proxy_handler):
    """Test successful configuration reload"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        assert proxy_handler.reload() is True

def test_reload_failure(proxy_handler):
    """Test configuration reload failure"""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, [], stderr="Reload failed")
        assert proxy_handler.reload() is False

def test_status_running(proxy_handler):
    """Test status when server running"""
    mock_process = Mock()
    mock_process.poll.return_value = None
    mock_process.pid = 12345
    proxy_handler._process = mock_process
    
    status = proxy_handler.status()
    assert status.running is True
    assert status.pid == 12345
    assert status.error is None

def test_status_not_running(proxy_handler):
    """Test status when server not running"""
    status = proxy_handler.status()
    assert status.running is False
    assert status.pid is None

def test_install_success(proxy_handler):
    """Test successful installation"""
    with patch('pathlib.Path.chmod'), \
         patch('pathlib.Path.symlink_to'), \
         patch('pathlib.Path.unlink'), \
         patch('caddy_cloudflare_cli.lib.utils.download_file', return_value=True):
        assert proxy_handler.install() is True

def test_install_download_failure(proxy_handler):
    """Test installation with download failure"""
    with patch('caddy_cloudflare_cli.lib.utils.download_file', return_value=False):
        assert proxy_handler.install() is False

def test_uninstall_success(proxy_handler):
    """Test successful uninstallation"""
    with patch('pathlib.Path.unlink'):
        assert proxy_handler.uninstall() is True

def test_uninstall_failure(proxy_handler):
    """Test uninstallation failure"""
    with patch('pathlib.Path.unlink', side_effect=OSError):
        assert proxy_handler.uninstall() is False
