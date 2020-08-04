from typing import Union, Optional, Any, List, Tuple, Dict, Type, AsyncGenerator
import logging
from urllib.parse import urlparse
import asyncio
from asyncio import Queue

from random import choice
from functools import wraps

from grpclib.client import Channel, Stream
from grpclib.exceptions import StreamTerminatedError

from aioetcd3.pb.etcdserverpb import rpc_pb2 as pb2
from aioetcd3.pb.mvccpb import kv_pb2
from aioetcd3.pb.etcdserverpb.rpc_grpc import (
    KVStub, WatchStub, LeaseStub, ClusterStub,
    MaintenanceStub, AuthStub)

from .utils import ensure_bytes, prefix_range_end

logger = logging.getLogger(__name__)

KeyRange = Tuple[Union[bytes, str], Union[bytes, str]]

class Client:
    channel: Channel
    status: str = 'alive'
    _kv: Optional['KVClient'] = None
    _lease: Optional['LeaseClient'] = None
    _watch: Optional['WatchClient'] = None
    _cluster: Optional['ClusterClient'] = None
    _server_urls: List[str]
    _current_server_url: str = ''
    _etcd_args: Dict[str, Any]

    def __init__(self, server_url, **kwargs):
        self._server_urls = [server_url]
        self._etcd_args = kwargs
        self.select_server()

    def select_server(self):
        assert self._server_urls
        self._current_server_url = choice(self._server_urls)
        logger.info('selected etcd server %s', self._current_server_url)
        parsed = urlparse(self._current_server_url)
        if ':' in parsed.netloc:
            host, port = parsed.netloc.split(':')
            port = int(port)
        else:
            host = parsed.netloc
            port = 2379
        # TODO: handle ssl
        self.channel = Channel(host, port, **self._etcd_args)

    def is_alive(self) -> bool:
        return self.status == 'alive'

    def close(self) -> None:
        self.status = 'closed'
        self.channel.close()
        print('cccc')

    async def collect_members(self, sleep_interval: float=60.0):
        '''\
        Periodly collect members, when one member failed, try to connect
        others.
        '''
        while self.is_alive():
            try:
                server_urls = []
                for member in await self.cluster.list_members():
                    server_urls.extend(member.clientURLs)
                    self._server_urls = server_urls
                    logger.info('current members %s', self._server_urls)
                await asyncio.sleep(sleep_interval)
            except RuntimeError as e:
                print('runtime error', e)
                logging.warning('runtime error %s', e)
                break

    @property
    def kv(self) -> 'KVClient':
        if self._kv is None:
            self._kv = KVClient(self)
        return self._kv

    @property
    def lease(self) -> 'LeaseClient':
        if self._lease is None:
            self._lease = LeaseClient(self)
        return self._lease

    @property
    def watch(self) -> 'WatchClient':
        if self._watch is None:
            self._watch = WatchClient(self)
        return self._watch

    @property
    def cluster(self) -> 'ClusterClient':
        if self._cluster is None:
            self._cluster = ClusterClient(self)
        return self._cluster


class ClientSection:
    client: 'Client'
    stub_cls: Type

    def __init__(self, client: 'Client'):
        self.client = client

    @property
    def stub(self) -> Any:
        return self.stub_cls(self.client.channel)

def section_retry(n:int=10):
    def outer(func):
        @wraps(func)
        async def wrapped(section, *args, **kwargs) -> Any:
            for retry_times in range(n):
                try:
                    return await func(section, *args, **kwargs)
                except OSError:
                    if retry_times < n - 1:
                        logger.warning('etcd function %s failed, retry times %s',
                                       func, retry_times)
                        await asyncio.sleep(1)
                        section.client.select_server()
                    else:
                        raise
        return wrapped
    return outer

class KVClient(ClientSection):
    stub_cls = KVStub

    @section_retry()
    async def put(self,
                  key: Union[bytes, str],
                  value: Union[bytes, str],
                  lease_id: int=0,
                  prev_kv: bool=False) -> bytes:

        key = ensure_bytes(key)
        value = ensure_bytes(value)

        resp = await self.stub.Put(
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

    @section_retry()
    async def get_range(self,
                        start: Union[bytes, str],
                        end: Union[bytes, str],
                        limit: int=0,
                        sort_by: str='') -> pb2.RangeResponse:
        start = ensure_bytes(start)

        end = ensure_bytes(end)

        if not sort_by:
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

        resp = await self.stub.Range(
            pb2.RangeRequest(
                key=start,
                range_end=end,
                limit=limit,
                sort_order=sort_order,
                sort_target=sort_target
            ))
        return resp

class LeaseClient(ClientSection):
    stub_cls = LeaseStub
    lease_ids: List[int]

    def __init__(self, *args, **kwargs):
        super(LeaseClient, self).__init__(*args, **kwargs)
        self.lease_ids = []

    @section_retry()
    async def grant(self, ttl: int, lease_id: int=0) -> pb2.LeaseGrantResponse:
        resp = await self.stub.LeaseGrant(
            pb2.LeaseGrantRequest(
                TTL=ttl,
                ID=lease_id))
        return resp

    @section_retry()
    async def revoke(self, lease_id: int) -> None:
        await self.stub.LeaseRevoke(
            pb2.LeaseRevokeRequest(
                ID=lease_id))

    @section_retry()
    async def keep_alive(self, lease_id:int, sleep_interval:float=1) -> None:
        while self.client.is_alive():
            async with self.stub.LeaseKeepAlive.open() as stream:
                await stream.send_message(
                    pb2.LeaseKeepAliveRequest(
                        ID=lease_id), end=True)
                resp = await stream.recv_message()
            await asyncio.sleep(sleep_interval)

    # TODO: TimeToLive and Lease and Leases

class WatchClient(ClientSection):
    stub_cls = WatchStub

    async def keep_watching(self,
                            *key_ranges:KeyRange
    ) -> AsyncGenerator[pb2.WatchResponse, None]:
        while self.client.is_alive():
            try:
                async for resp in self.open_stream(*key_ranges):
                    yield resp
            except OSError as e:
                # ConnectionRefusedError
                logger.warning('watching failed, %s', e)
                self.client.select_server()
                await asyncio.sleep(1)

    async def open_stream(self,
                   *key_ranges:KeyRange
    ) -> AsyncGenerator[pb2.WatchResponse, None]:

        async with self.stub.Watch.open() as stream:
            logging.info('stream %s opened to watch %s', stream, key_ranges)
            for key, range_end in key_ranges:
                await stream.send_message(pb2.WatchRequest(
                    create_request=pb2.WatchCreateRequest(
                        key=ensure_bytes(key),
                        range_end=ensure_bytes(range_end))))

            watch_id: int = 0
            while self.client.is_alive():
                try:
                    resp = await stream.recv_message()
                except StreamTerminatedError:
                    logger.warning('stream watching terminated %s', stream)
                    break
                if resp.created:
                    watch_id = resp.watch_id
                elif resp.canceled:
                    await stream.send_request(end=True)
                    break
                else:
                    yield resp

class ClusterClient(ClientSection):
    stub_cls = ClusterStub

    @section_retry()
    async def list_members(self) -> List[pb2.Member]:
        resp = await self.stub.MemberList(
            pb2.MemberListRequest())
        return resp.members
