"""
Unit tests for internal UMLS package.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit
from knowledge_lookup.umls.auth import UMLSAuthenticator
from knowledge_lookup.umls.main_client import OptimizedUMLSClient


class TestUMLSPackage:
    """Tests for UMLS internal clients."""

    @pytest.mark.asyncio
    async def test_umls_auth(self):
        """Test UMLS authentication."""
        auth = UMLSAuthenticator(api_key="test_key")

        mock_get_st = AsyncMock(return_value="ST-123")
        with patch.object(auth, "get_service_ticket", mock_get_st):
            st = await auth.get_service_ticket()
            assert st == "ST-123"

    @pytest.mark.asyncio
    async def test_umls_main_client(self):
        """Test UMLS main client initialization."""
        client = OptimizedUMLSClient(api_key="test_key")
        assert client.api_key == "test_key"
