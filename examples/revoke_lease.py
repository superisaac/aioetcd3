import time
import signal
import asyncio
import argparse
from aioetcd3.client import Client

async def main() -> None:
    # parse arguments
    parser = argparse.ArgumentParser(description='put k/v while retaining the lease')
    parser.add_argument('lease_id',
                        type=int,
                        help='lease ID to revoke')
    parser.add_argument('--etcd',
                        type=str,
                        default='http://127.0.0.1:2379',
                        help='etcd server url')
    args = parser.parse_args()

    c = Client(args.etcd)

    resp = await c.lease.revoke(args.lease_id)
    print('revoke resp', resp)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
