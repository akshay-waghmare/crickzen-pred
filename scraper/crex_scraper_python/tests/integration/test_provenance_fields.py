import pytest
from unittest.mock import AsyncMock, patch
from crex_scraper_python.src.adapters.crex_adapter import CrexAdapter

@pytest.mark.asyncio
async def test_provenance_fields_added():
    adapter = CrexAdapter()
    
    # Mock context and page
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_context.new_page.return_value = mock_page
    
    # Mock page content
    mock_page.content.return_value = "<html></html>"
    
    # Patch the parser
    with patch('crex_scraper_python.src.adapters.crex_adapter.extract_match_dom_fields') as mock_extract:
        mock_extract.return_value = {"match_name": "Test Match"}
        
        url = "http://example.com/match/123"
        data = await adapter.fetch_match(mock_context, url)
        
        # Verify provenance fields
        assert "adapter" in data
        assert data["adapter"] == "crex"
        assert "source_url" in data
        assert data["source_url"] == url
        assert data["match_name"] == "Test Match"
