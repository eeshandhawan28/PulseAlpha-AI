import pytest
from unittest.mock import patch
from connectors.nav import NAVConnector


@pytest.mark.asyncio
async def test_nav_returns_float_nav():
    with patch("connectors.nav.Mftool") as M:
        M.return_value.get_scheme_quote.return_value = {
            "scheme_name": "Mirae Large Cap",
            "nav": "95.432",
            "date": "23-May-2026",
        }
        result = await NAVConnector().fetch("118533")
    assert result.source == "mftool_nav"
    assert result.data["nav"] == 95.432
    assert result.ok
