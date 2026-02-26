import pytest

from api.common.services.bicep_transformer import transform_image_to_bicep
from api.common.services.blob_storage import (
    mock_blob_storage,
    mock_blob_download,
    mock_blob_list,
)


@pytest.mark.asyncio
async def test_bicep_transform_returns_bicep():
    result = await transform_image_to_bicep(b"dummy", "arch.png")
    assert isinstance(result, str)
    assert "resource" in result


@pytest.mark.asyncio
async def test_blob_storage_upload_and_download():
    info = await mock_blob_storage("hello bicep", container="test")
    assert info["container"] == "test"
    assert info["size"] > 0

    data = await mock_blob_download("test", info["blob_name"])
    assert data == "hello bicep"


@pytest.mark.asyncio
async def test_blob_storage_list():
    await mock_blob_storage("data1", container="listtest", blob_name="a.bicep")
    await mock_blob_storage("data2", container="listtest", blob_name="b.bicep")
    items = mock_blob_list("listtest")
    names = [i["blob_name"] for i in items]
    assert "a.bicep" in names
    assert "b.bicep" in names


@pytest.mark.asyncio
async def test_blob_download_missing():
    result = await mock_blob_download("nocontainer", "nofile")
    assert result is None
