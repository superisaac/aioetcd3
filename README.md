# aioetcd3
robust asyncio etcd3 client using grpclib

## install
```shell
pip install git+https://github.com/superisaac/aioetcd3.git
```

## examples

### using KV
```python
c = Client('http://127.0.0.1')
# collect all members of the cluster, when on member failed, try another
asyncio.ensure_future(c.collect_members())
await c.kv.put("helilo", "world")
print(await c.kv.get("hello"))
```

### using lease
```python
c = Client('http://127.0.0.1')
lease = await c.lease.grant(5) # TTL is 5 seconds
await c.kv.put("hello", "world", lease_id=lease.ID)
asyncio.ensure_future(c.lease.keep_alive(lease.ID))
```

### watch key
```python
c = Client(...)
async for resp in c.watch.open_stream(b'key1', 'key2', (b'key11', b'key12')):
    print(resp)
```

