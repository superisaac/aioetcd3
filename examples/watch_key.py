import time
import signal
import asyncio
import argparse
from aioetcdm3.client import Client

async def main() -> None:
    # parse arguments
    parser = argparse.ArgumentParser(description='watch key changes')
    parser.add_argument('key',
                        type=str,
                        help='the key to watch')
    parser.add_argument('--end',
                        type=str,
                        default='',
                        help='the key range end to watch')

    parser.add_argument('--etcd',
                        type=str,
                        default='http://127.0.0.1:2379',
                        help='etcd server url')
    args = parser.parse_args()

    c = Client(args.etcd)

    async for resp in c.watch.keep_watching((args.key, args.end)):
        print(resp)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
