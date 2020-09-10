import pytest
from aioetcdm3.client import Client
from aioetcdm3.utils import ensure_bytes, prefix_range_end

@pytest.mark.asyncio
async def test_put_get():
    c = Client('http://127.0.0.1')
    await c.kv.put("hello", "nice")

    r = await c.kv.get("hello")
    assert r == b'nice'

@pytest.mark.asyncio
async def test_range_put_get():
    c = Client('http://127.0.0.1')
    for i in range(5):
        await c.kv.put(f'what{i}', f'ok{i}')

    end = prefix_range_end(b'what')
    print('end', end)
    resp = await c.kv.get_range('what', end)
    assert len(resp.kvs) == 5
    for i in range(5):
        assert resp.kvs[i].value == ensure_bytes(f'ok{i}')

@pytest.mark.asyncio
async def test_prefix_range_end():
    assert prefix_range_end(b'86') == b'87'
    assert prefix_range_end(b'ab\xff1\xff') == b'ab\xff2\xff'
    assert prefix_range_end(b'\xff\xff') == b'\xff\xff'



