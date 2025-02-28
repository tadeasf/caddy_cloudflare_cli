"""
Tests for Cloudflare DNS handler
"""
import pytest
from unittest.mock import Mock, patch
from cloudflare import APIError
from caddy_cloudflare_cli.lib.dns.cloudflare_api_handler import CloudflareDNS
from caddy_cloudflare_cli.lib.dns.base import DNSError, DNSRecord
from caddy_cloudflare_cli.lib.config import Config

@pytest.fixture
def config():
    """Mock configuration"""
    return Config(
        domain="example.com",
        cloudflare_api_key="test-key",
        cloudflare_api_email="test@example.com"
    )

@pytest.fixture
def dns_handler(config):
    """Mock DNS handler"""
    return CloudflareDNS(config)

@pytest.fixture
def mock_cloudflare():
    """Mock Cloudflare client"""
    with patch('cloudflare.Cloudflare') as mock:
        mock_client = Mock()
        mock.return_value = mock_client
        yield mock_client

def test_init(config):
    """Test initialization with API key"""
    with patch('cloudflare.Cloudflare') as mock:
        dns = CloudflareDNS(config)
        mock.assert_called_once_with(
            api_key=config.cloudflare_api_key,
            api_email=config.cloudflare_api_email
        )

def test_init_with_token():
    """Test initialization with API token"""
    config = Config(
        domain="example.com",
        cloudflare_token="test-token"
    )
    with patch('cloudflare.Cloudflare') as mock:
        dns = CloudflareDNS(config)
        mock.assert_called_once_with(
            api_token=config.cloudflare_token
        )

def test_zone_id_caching(dns_handler, mock_cloudflare):
    """Test zone ID caching"""
    # Create mock response object with result attribute
    mock_response = Mock()
    # Use dictionary format for result items
    mock_result = [{'id': 'test-zone-id'}]
    mock_response.result = mock_result
    mock_cloudflare.zones.list.return_value = mock_response

    zone_id = dns_handler.zone_id
    assert zone_id == 'test-zone-id'

    # Second call should use cached value
    zone_id = dns_handler.zone_id
    mock_cloudflare.zones.list.assert_called_once()

def test_zone_id_not_found(dns_handler, mock_cloudflare):
    """Test zone ID not found"""
    # Create mock response object with empty result
    mock_response = Mock()
    mock_response.result = []
    mock_cloudflare.zones.list.return_value = mock_response

    with pytest.raises(DNSError, match="Domain example.com not found"):
        dns_handler.zone_id

def test_zone_id_api_error(dns_handler, mock_cloudflare):
    """Test zone ID API error"""
    mock_cloudflare.zones.list.side_effect = APIError("API Error")

    with pytest.raises(DNSError, match="Cloudflare API error"):
        dns_handler.zone_id

def test_create_record_success(dns_handler, mock_cloudflare):
    """Test successful record creation"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    # Setup DNS record mock
    mock_record = Mock()
    mock_record.id = 'test-record-id'
    mock_record.name = 'test.example.com'
    mock_record.type = 'A'
    mock_record.content = '1.2.3.4'
    mock_record.proxied = True
    mock_record.ttl = 1
    mock_cloudflare.zones.dns_records.post.return_value = mock_record
    
    # Setup existing records check - empty list
    mock_existing = Mock()
    mock_existing.result = []
    mock_cloudflare.zones.dns_records.list.return_value = mock_existing

    record = dns_handler.create_record('test', 'A', '1.2.3.4')

    assert record.id == 'test-record-id'
    assert record.name == 'test.example.com'
    assert record.type == 'A'
    assert record.content == '1.2.3.4'
    assert record.proxied is True
    assert record.ttl == 1

def test_create_record_api_error(dns_handler, mock_cloudflare):
    """Test record creation API error"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    # Setup existing records check - empty list
    mock_existing = Mock()
    mock_existing.result = []
    mock_cloudflare.zones.dns_records.list.return_value = mock_existing
    
    mock_cloudflare.zones.dns_records.post.side_effect = APIError("API Error")

    with pytest.raises(DNSError, match="Failed to create DNS record"):
        dns_handler.create_record('test', 'A', '1.2.3.4')

def test_delete_record_success(dns_handler, mock_cloudflare):
    """Test successful record deletion"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    mock_cloudflare.zones.dns_records.delete.return_value = None

    assert dns_handler.delete_record('test-record-id') is True

def test_delete_record_api_error(dns_handler, mock_cloudflare):
    """Test record deletion API error"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    mock_cloudflare.zones.dns_records.delete.side_effect = APIError("API Error")

    with pytest.raises(DNSError, match="Failed to delete DNS record"):
        dns_handler.delete_record('test-record-id')

def test_get_record_success(dns_handler, mock_cloudflare):
    """Test successful record retrieval"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    # Setup record mock
    mock_record = Mock()
    mock_record.id = 'test-record-id'
    mock_record.name = 'test.example.com'
    mock_record.type = 'A'
    mock_record.content = '1.2.3.4'
    mock_record.proxied = True
    mock_record.ttl = 1
    mock_cloudflare.zones.dns_records.get.return_value = mock_record

    record = dns_handler.get_record('test-record-id')

    assert record.id == 'test-record-id'
    assert record.name == 'test.example.com'
    assert record.type == 'A'
    assert record.content == '1.2.3.4'
    assert record.proxied is True
    assert record.ttl == 1

def test_get_record_not_found(dns_handler, mock_cloudflare):
    """Test record not found"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    mock_cloudflare.zones.dns_records.get.side_effect = APIError("Not Found")

    assert dns_handler.get_record('test-record-id') is None

def test_list_records_success(dns_handler, mock_cloudflare):
    """Test successful records listing"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    # Setup records list mock
    mock_record1 = Mock()
    mock_record1.id = 'test-record-id-1'
    mock_record1.name = 'test1.example.com'
    mock_record1.type = 'A'
    mock_record1.content = '1.2.3.4'
    mock_record1.proxied = True
    mock_record1.ttl = 1
    
    mock_record2 = Mock()
    mock_record2.id = 'test-record-id-2'
    mock_record2.name = 'test2.example.com'
    mock_record2.type = 'A'
    mock_record2.content = '5.6.7.8'
    mock_record2.proxied = True
    mock_record2.ttl = 1
    
    mock_records_response = Mock()
    mock_records_response.result = [mock_record1, mock_record2]
    mock_cloudflare.zones.dns_records.list.return_value = mock_records_response

    records = dns_handler.list_records()

    assert len(records) == 2
    assert records[0].id == 'test-record-id-1'
    assert records[0].name == 'test1.example.com'
    assert records[0].proxied is True
    assert records[0].ttl == 1
    assert records[1].id == 'test-record-id-2'
    assert records[1].name == 'test2.example.com'
    assert records[1].proxied is True
    assert records[1].ttl == 1

def test_list_records_filtered(dns_handler, mock_cloudflare):
    """Test filtered records listing"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    # Setup records list mock
    mock_record = Mock()
    mock_record.id = 'test-record-id-1'
    mock_record.name = 'test1.example.com'
    mock_record.type = 'A'
    mock_record.content = '1.2.3.4'
    mock_record.proxied = True
    mock_record.ttl = 1
    
    mock_records_response = Mock()
    mock_records_response.result = [mock_record]
    mock_cloudflare.zones.dns_records.list.return_value = mock_records_response

    records = dns_handler.list_records(record_type='A')

    assert len(records) == 1
    assert records[0].id == 'test-record-id-1'
    assert records[0].name == 'test1.example.com'
    assert records[0].proxied is True
    assert records[0].ttl == 1

def test_verify_propagation_success(dns_handler, mock_cloudflare):
    """Test successful propagation verification"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    # Setup record mock
    mock_record = Mock()
    mock_record.id = 'test-record-id'
    mock_record.name = 'test.example.com'
    mock_record.type = 'A'
    mock_record.content = '1.2.3.4'
    mock_record.proxied = True
    mock_record.ttl = 1
    mock_cloudflare.zones.dns_records.get.return_value = mock_record

    record = DNSRecord(
        id='test-record-id',
        name='test.example.com',
        type='A',
        content='1.2.3.4',
        proxied=True,
        ttl=1
    )

    assert dns_handler.verify_propagation(record, timeout=1) is True

def test_verify_propagation_timeout(dns_handler, mock_cloudflare):
    """Test propagation verification timeout"""
    # Setup zone ID mock
    mock_zone_response = Mock()
    mock_zone_response.result = [Mock(id='test-zone-id')]
    mock_cloudflare.zones.list.return_value = mock_zone_response
    
    mock_cloudflare.zones.dns_records.get.side_effect = APIError("Not Found")

    record = DNSRecord(
        id='test-record-id',
        name='test.example.com',
        type='A',
        content='1.2.3.4',
        proxied=True,
        ttl=1
    )

    assert dns_handler.verify_propagation(record, timeout=1) is False
