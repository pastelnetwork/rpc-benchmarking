import asyncio
import base64
import decimal
import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib import parse as urlparse
from httpx import AsyncClient, Timeout, Limits

# Set logging level for httpx to WARNING to suppress info logs
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MAXIMUM_NUMBER_OF_CONCURRENT_RPC_REQUESTS = 1000

class JSONRPCException(Exception):
    def __init__(self, rpc_error):
        parent_args = []
        try:
            parent_args.append(rpc_error['message'])
        except Exception as e:
            logger.error(f"Error occurred in JSONRPCException: {e}")
            pass
        Exception.__init__(self, *parent_args)
        self.error = rpc_error
        self.code = rpc_error['code'] if 'code' in rpc_error else None
        self.message = rpc_error['message'] if 'message' in rpc_error else None

    def __str__(self):
        return '%d: %s' % (self.code, self.message)

    def __repr__(self):
        return '<%s \'%s\'>' % (self.__class__.__name__, self)

def EncodeDecimal(o):
    if isinstance(o, decimal.Decimal):
        return float(round(o, 8))
    raise TypeError(repr(o) + " is not JSON serializable")

class AsyncAuthServiceProxy:
    _semaphore = asyncio.BoundedSemaphore(MAXIMUM_NUMBER_OF_CONCURRENT_RPC_REQUESTS)
    def __init__(self, service_url, service_name=None, reconnect_timeout=15, reconnect_amount=2, request_timeout=90):
        self.service_url = service_url
        self.service_name = service_name
        self.url = urlparse.urlparse(service_url)        
        self.client = AsyncClient(timeout=Timeout(request_timeout), limits=Limits(max_connections=200, max_keepalive_connections=10))
        self.id_count = 0
        user = self.url.username
        password = self.url.password
        authpair = f"{user}:{password}".encode('utf-8')
        self.auth_header = b'Basic ' + base64.b64encode(authpair)
        self.reconnect_timeout = reconnect_timeout
        self.reconnect_amount = reconnect_amount
        self.request_timeout = request_timeout

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError
        if self.service_name is not None:
            name = f"{self.service_name}.{name}"
        return AsyncAuthServiceProxy(self.service_url, name)

    async def __call__(self, *args):
        async with self._semaphore:
            self.id_count += 1
            postdata = json.dumps({
                'version': '1.1',
                'method': self.service_name,
                'params': args,
                'id': self.id_count
            }, default=EncodeDecimal)
            headers = {
                'Host': self.url.hostname,
                'User-Agent': "AuthServiceProxy/0.1",
                'Authorization': self.auth_header,
                'Content-type': 'application/json'
            }
            for i in range(self.reconnect_amount):
                try:
                    if i > 0:
                        logger.warning(f"Reconnect try #{i+1}")
                        sleep_time = self.reconnect_timeout * (2 ** i)
                        logger.info(f"Waiting for {sleep_time} seconds before retrying.")
                        await asyncio.sleep(sleep_time)
                    response = await self.client.post(
                        self.service_url, headers=headers, data=postdata)
                    break
                except Exception as e:
                    logger.error(f"Error occurred in __call__: {e}")
                    err_msg = f"Failed to connect to {self.url.hostname}:{self.url.port}"
                    rtm = self.reconnect_timeout
                    if rtm:
                        err_msg += f". Waiting {rtm} seconds."
                    logger.exception(err_msg)
            else:
                logger.error("Reconnect tries exceeded.")
                return
            response_json = response.json()
            if response_json['error'] is not None:
                raise JSONRPCException(response_json['error'])
            elif 'result' not in response_json:
                raise JSONRPCException({
                    'code': -343, 'message': 'missing JSON-RPC result'})
            else:
                return response_json['result']

def get_local_rpc_settings_func(directory_with_pastel_conf=os.path.expanduser("/home/ubuntu/.pastel/")):
    with open(os.path.join(directory_with_pastel_conf, "pastel.conf"), 'r') as f:
        lines = f.readlines()
    other_flags = {}
    rpchost = '127.0.0.1'
    rpcport = '19932'
    rpcuser = None
    rpcpassword = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value is value.strip()
            if key == 'rpcport':
                rpcport = value
            elif key == 'rpcuser':
                rpcuser = value
            elif key == 'rpcpassword':
                rpcpassword = value
            elif key == 'rpchost':
                rpchost = value
            else:
                other_flags[key] = value
    return rpchost, rpcport, rpcuser, rpcpassword, other_flags

async def verify_message_with_pastelid_func(pastelid, message_to_verify, pastelid_signature_on_message) -> str:
    global rpc_connection
    verification_result = await rpc_connection.pastelid('verify', message_to_verify, pastelid_signature_on_message, pastelid, 'ed448')
    return verification_result['verification']

async def sign_message_with_pastelid_func(pastelid, message_to_sign, passphrase) -> str:
    global rpc_connection
    results_dict = await rpc_connection.pastelid('sign', message_to_sign, pastelid, passphrase, 'ed448')
    return results_dict['signature']

async def create_new_pastelid(passphrase):
    global rpc_connection
    response = await rpc_connection.pastelid('newkey', passphrase)
    pastelid = response['pastelid']
    return pastelid

async def get_current_pastel_block_height_func():
    global rpc_connection
    best_block_hash = await rpc_connection.getbestblockhash()
    best_block_details = await rpc_connection.getblock(best_block_hash)
    current_block_height = best_block_details['height']
    return current_block_height

async def check_masternode_top_func():
    global rpc_connection
    masternode_top_command_output = await rpc_connection.masternode('top')
    return masternode_top_command_output

async def get_recent_transactions_func(blocks=5):
    global rpc_connection
    recent_txids = []
    best_block_hash = await rpc_connection.getbestblockhash()
    best_block_details = await rpc_connection.getblock(best_block_hash)
    current_block_height = best_block_details['height']
    for height in range(current_block_height - blocks + 1, current_block_height + 1):
        block_hash = await rpc_connection.getblockhash(height)
        block_details = await rpc_connection.getblock(block_hash)
        recent_txids.extend(block_details['tx'])
    return recent_txids

async def get_raw_transaction_func(txid):
    global rpc_connection
    raw_transaction = await rpc_connection.getrawtransaction(txid)
    return raw_transaction

async def benchmark_rpc_calls(pastelid, passphrase):
    async def rpc_call():
        message_to_sign = "some_message"
        return await sign_message_with_pastelid_func(pastelid, message_to_sign, passphrase)

    async def block_height_call():
        return await get_current_pastel_block_height_func()

    async def masternode_call():
        return await check_masternode_top_func()

    async def recent_tx_call():
        txids = await get_recent_transactions_func()
        return await asyncio.gather(*[get_raw_transaction_func(txid) for txid in txids])

    max_concurrent_calls = 25
    step = 10
    max_successful_calls = 0

    with open("rpc_benchmark_results.txt", "a") as f:
        while True:
            tasks = [rpc_call() for _ in range(max_concurrent_calls)]
            tasks += [block_height_call() for _ in range(max_concurrent_calls)]
            tasks += [masternode_call() for _ in range(max_concurrent_calls)]
            tasks += [recent_tx_call() for _ in range(max_concurrent_calls)]
            try:
                start_time = time.time()
                await asyncio.gather(*tasks)
                elapsed_time = time.time() - start_time
                calls_per_second = (max_concurrent_calls * 4) / elapsed_time
                max_successful_calls = max_concurrent_calls
                timestamp = datetime.now(timezone.utc).isoformat()
                f.write(f"{timestamp}: Successfully completed {max_concurrent_calls * 4} concurrent RPC calls.\n")
                f.write(f"{timestamp}: RPC calls per second: {calls_per_second}\n")
                logger.info(f"Successfully completed {max_concurrent_calls * 4} concurrent RPC calls.")
                logger.info(f"RPC calls per second: {calls_per_second}")
                max_concurrent_calls += step
            except Exception as e:
                timestamp = datetime.now(timezone.utc).isoformat()
                f.write(f"{timestamp}: Failed at {max_concurrent_calls*4} concurrent RPC calls. Error: {e}\n")
                logger.error(f"Failed at {max_concurrent_calls*4} concurrent RPC calls. Error: {e}")
                break

        f.write(f"{timestamp}: Maximum successful concurrent RPC calls: {max_successful_calls*4}\n")
        logger.info(f"Maximum successful concurrent RPC calls: {max_successful_calls*4}")

if __name__ == "__main__":
    rpc_host, rpc_port, rpc_user, rpc_password, other_flags = get_local_rpc_settings_func()
    rpc_connection = AsyncAuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}")

    passphrase = "your_passphrase_here"
    pastelid = asyncio.run(create_new_pastelid(passphrase))

    asyncio.run(benchmark_rpc_calls(pastelid, passphrase))
