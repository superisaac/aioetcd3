from typing import Union, Optional, Any
from grpclib.client import Channel
import asyncio
from asyncio import Queue

from aioetcd3.pb.etcdserverpb import rpc_pb2 as pb2
from aioetcd3.pb.mvccpb import kv_pb2
from aioetcd3.pb.etcdserverpb.rpc_grpc import (
    KVStub, WatchStub, LeaseStub, ClusterStub,
    MaintenanceStub, AuthStub)

from .utils import ensure_bytes, prefix_range_end

class Client:
    channel: Channel
    _kv: 'KVClient' = None
    _lease: 'LeaseClient' = None
    _watch: 'WatchClient' = None
    continue_stream: bool = True

    def __init__(self, *args, **kwargs):
        self.channel = Channel(*args, **kwargs)

    @property
    def kv(self):
        if self._kv is None:
            self._kv = KVClient(self)
        return self._kv

    @property
    def lease(self):
        if self._lease is None:
            self._lease = KVClient(self)
        return self._lease

    @property
    def watch(self):
        if self._watch is None:
            self._watch = KVClient(self)
        return self._watch

class KVClient:
    client: 'Client'
    def __init__(self, client: 'Client'):
        self.client = client
        self._stub = KVStub(self.client.channel)

    async def put(self,
                  key: Union[bytes, str],
                  value: Union[bytes, str],
                  lease_id: int=0,
                  prev_kv: bool=False) -> bytes:

        key = ensure_bytes(key)
        value = ensure_bytes(value)

        resp = await self._stub.Put(
            pb2.PutRequest(
                key=key,
                value=value,
                lease=lease_id,
                prev_kv=prev_kv
            ))
        return resp.prev_kv.value

    async def get(self,
                  key: Union[bytes, str]) -> Optional[bytes]:
        key = ensure_bytes(key)

        resp = await self.get_range(key, b"")
        if resp.kvs:
            return resp.kvs[0].value
        else:
            return None

    async def get_range(self,
                        start: Union[bytes, str],
                        end: Union[bytes, str],
                        limit: int=0,
                        sort_by: Union[None, str]=None
    ) -> pb2.RangeResponse:

        start = ensure_bytes(start)

        end = ensure_bytes(end)

        if sort_by in (None, ''):
            sort_order = pb2.RangeRequest.SortOrder.NONE
            sort_t = 'key'
        elif sort_by.startswith('-'):
            sort_order = pb2.RangeRequest.SortOrder.DESCEND
            sort_t = sort_by[1:]
        else:
            sort_order = pb2.RangeRequest.SortOrder.ASCEND
            sort_t = sort_by

        assert sort_t.lower() in ('key', 'version', 'create', 'mod', 'value')

        sort_target = getattr(pb2.RangeRequest.SortTarget,
                              sort_t.upper())



        resp = await self._stub.Range(
            pb2.RangeRequest(
                key=start,
                range_end=end,
                limit=limit,
                sort_order=sort_order,
                sort_target=sort_target
            ))
        return resp

class LeaseClient:
    client: 'Client'
    def __init__(self, client: Client):
        self.client = client
        self._stub = LeaseStub(self.client.channel)

    async def grant(self, ttl: int, lease_id: int=0) -> int:
        resp = await self._stub.LeaseGrant(
            pb2.LeaseGrantRequest(
                TTL=ttl,
                ID=lease_id))
        return resp.ID

    async def revoke(self, lease_id: int) -> None:
        await self._stub.LeaseRevoke(
            pb2.LeaseRevokeRequest(
                ID=lease_id))

    async def keep_alive(self, lease_id: int, sleep_interval:float=1) -> None:
        async with self._stub.LeaseKeepAlive.open() as stream:
            await stream.send_message(
                pb2.LeaseKeepAliveRequest(
                    ID=lease_id))
            await asyncio.sleep(sleep_interval)

    # TODO: TimeToLive and Lease and Leases

class Watcher:
    def __init__(self):
        self._queue = Queue()

    async def put(self, value:Any) -> None:
        await self._queue.put(value)

    async def get(self) -> pb2.WatchResponse:
        resp = await self._queue.get()
        assert isinstance(resp, WatchResponse)
        return resp

class WatchClient:
    client: 'Client'
    #stream: Stream
    def __init__(self, client: Client):
        self.client = client
        self._stub = WatchStub(self.client.channel)
        self.pending_watchers = Queue()
        self.created_watchers = Queue()
        self.canceled_watchers = Queue()
        self.stream = None
        self.watchers = {}

    async def handle_messages(self):
        while self.client.continue_stream:
            resp = await self.stream.recv_message()
            if resp.created:
                watcher = self.pending_watchers.get_nowait()
                assert watcher
                watcher.id = resp.watch_id
                self.created_watchers.put(watcher)
                self.watchers[watcher.id] = watcher
            elif resp.canceled:
                watcher = self.watchers.pop(resp.watch_id)
                self.canceled_watchers.put(watcher)
            else:
                watcher = self.watchers[resp.watch_id]
                await watcher.put(resp)

    async def watch(self,
                    key: Union[bytes, str],
                    range_end: Union[bytes, str]=''
    ) -> Watcher:
        if self.stream is None:
            self.stream = self._stub.Watch.open()
            asyncio.ensure_future(self.handle_messages())

        watcher = Watcher()
        self.pending_watchers.put(watcher)

        await self.stream.send_message(pb2.WatchRequest(
            create_request=pb2.WatchCreateRequest(
                key=ensure_bytes(key),
                range_end=ensure_bytes(range_end))))

        created_w  = await self.created_watchers.get()
        return created_w

    async def cancel_watcher(self, watch_id: int) -> Watcher:
        if self.stream is None:
            self.stream = self._stub.Watch.open()

        watcher = Watcher()
        self.pending_watchers.put(watcher)

        await self.stream.send_message(pb2.WatchRequest(
            cancel_request=pb2.WatchCancelRequest(
                watch_id=watch_id)))

        canceled_w = await self.canceled_watchers.get()
        return canceled_w
