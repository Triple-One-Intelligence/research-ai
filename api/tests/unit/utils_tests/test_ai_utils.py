"""Tests for ai_utils — config constants, send_async_ai_request, and async_embed."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.utils.ai_utils.ai_utils import (
    AI_SERVICE_URL,
    CHAT_MAX_TOKENS,
    CHAT_MODEL,
    EMBED_DIMENSIONS,
    EMBED_MODEL,
    EMBED_NUM_GPU,
    async_embed,
    send_async_ai_request,
)


# ---------------------------------------------------------------------------
# Config constants
# ---------------------------------------------------------------------------
class TestConfigDefaults:
    """Verify that module-level config constants pick up env / defaults."""

    def test_ai_service_url_from_env(self):
        assert AI_SERVICE_URL == os.environ["AI_SERVICE_URL"]

    def test_chat_model_default(self):
        expected = os.getenv("CHAT_MODEL", "command-r:35b")
        assert CHAT_MODEL == expected

    def test_embed_model_default(self):
        expected = os.getenv("EMBED_MODEL", "snowflake-arctic-embed2")
        assert EMBED_MODEL == expected

    def test_embed_dimensions_default(self):
        expected = int(os.getenv("EMBED_DIMENSIONS", "1024"))
        assert EMBED_DIMENSIONS == expected

    def test_chat_max_tokens_default(self):
        expected = int(os.getenv("CHAT_MAX_TOKENS", "2048"))
        assert CHAT_MAX_TOKENS == expected

    def test_embed_num_gpu_default(self):
        expected = int(os.getenv("EMBED_NUM_GPU", "0"))
        assert EMBED_NUM_GPU == expected


# ---------------------------------------------------------------------------
# send_async_ai_request
# ---------------------------------------------------------------------------
class TestSendAsyncAiRequest:
    @pytest.mark.asyncio
    async def test_successful_request(self):
        mock_response = AsyncMock()
        mock_response.json = lambda: {"result": "ok"}
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.utils.ai_utils.ai_utils.httpx.AsyncClient", return_value=mock_client):
            result = await send_async_ai_request("http://fake/api", {"key": "val"})

        assert result == {"result": "ok"}
        mock_client.post.assert_called_once_with(
            "http://fake/api", json={"key": "val"}, timeout=60.0
        )

    @pytest.mark.asyncio
    async def test_request_error_raises_503(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("connection failed", request=None)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.utils.ai_utils.ai_utils.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await send_async_ai_request("http://fake/api", {})

        assert exc_info.value.status_code == 503
        assert "Error connecting to AI service" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_http_status_error_raises_502(self):
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json = lambda: {"error": "fail"}
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("server error", request=None, response=mock_response)
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.utils.ai_utils.ai_utils.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await send_async_ai_request("http://fake/api", {})

        assert exc_info.value.status_code == 502
        assert "AI service returned an error." in exc_info.value.detail


# ---------------------------------------------------------------------------
# async_embed
# ---------------------------------------------------------------------------
class TestAsyncEmbed:
    @pytest.mark.asyncio
    async def test_returns_embedding_vector(self):
        fake_vector = [0.1, 0.2, 0.3]

        with patch(
            "app.utils.ai_utils.ai_utils.send_async_ai_request",
            new_callable=AsyncMock,
            return_value={"embeddings": [fake_vector]},
        ):
            result = await async_embed("hello world")

        assert result == fake_vector

    @pytest.mark.asyncio
    async def test_builds_correct_request(self):
        mock_send = AsyncMock(return_value={"embeddings": [[0.1]]})

        with patch("app.utils.ai_utils.ai_utils.send_async_ai_request", mock_send):
            await async_embed("test input")

        mock_send.assert_called_once_with(
            f"{AI_SERVICE_URL}/api/embed",
            {
                "input": "test input",
                "model": EMBED_MODEL,
                "options": {"num_gpu": EMBED_NUM_GPU},
            },
        )

    @pytest.mark.asyncio
    async def test_empty_embeddings_raises_502(self):
        with patch(
            "app.utils.ai_utils.ai_utils.send_async_ai_request",
            new_callable=AsyncMock,
            return_value={"embeddings": []},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await async_embed("hello")

        assert exc_info.value.status_code == 502
        assert "empty embeddings" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_none_embeddings_raises_502(self):
        with patch(
            "app.utils.ai_utils.ai_utils.send_async_ai_request",
            new_callable=AsyncMock,
            return_value={"embeddings": None},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await async_embed("hello")

        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_empty_inner_list_raises_502(self):
        with patch(
            "app.utils.ai_utils.ai_utils.send_async_ai_request",
            new_callable=AsyncMock,
            return_value={"embeddings": [[]]},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await async_embed("hello")

        assert exc_info.value.status_code == 502
