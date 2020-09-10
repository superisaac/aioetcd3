import time
import signal
import asyncio
import argparse
from aioetcdm3.client import Client

async def main() -> Client:
    # parse arguments
    parser = argparse.ArgumentParser(description='put k/v while retaining the lease')
    parser.add_argument('key',
                        type=str,
                        help='the key to put')
    parser.add_argument('value', type=str,
                        help='the value to put')
    parser.add_argument('--etcd',
                        type=str,
                        default='http://127.0.0.1:2379',
                        help='etcd server url')
    args = parser.parse_args()

    c = Client(args.etcd)

    lease1 = await c.lease.grant(5)
    print('got lease 1', lease1.ID)

    lease2 = await c.lease.grant(5)
    print('got lease 2', lease2.ID)

    await c.kv.put(args.key, args.value, lease_id=lease2.ID)
    await c.lease.keep_alive(lease1.ID, lease2.ID)
    return c

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
