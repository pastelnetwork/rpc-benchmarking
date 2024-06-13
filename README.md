# RPC Benchmarking Script

This repository contains a Python script to benchmark the performance of various RPC calls to a Pastel network node. The script creates a new PastelID, signs messages, verifies signatures, and performs other demanding RPC tasks such as retrieving recent transactions and their details. The benchmarking results, including the number of successful concurrent RPC calls and calls per second, are logged to a file.

## Requirements

- Python 3.7 or later
- `httpx` library

## Installation

1. Clone this repository:

   ```sh
   git clone https://github.com/pastelnetwork/rpc-benchmarking.git
   cd rpc-benchmarking
   ```

2. Install the required Python packages:

   ```sh
   pip install -r requirements.txt
   ```

## Configuration

Ensure you have a `pastel.conf` file in the specified directory (`/home/ubuntu/.pastel/` by default) with the necessary RPC settings:

```
rpcuser=<your_rpc_username>
rpcpassword=<your_rpc_password>
rpchost=127.0.0.1
rpcport=19932
```

## Usage

1. Update the `passphrase` variable in the script with your desired passphrase for creating a new PastelID.

2. Run the script:

   ```sh
   python benchmark_rpc_calls.py
   ```

   The script will perform various RPC calls and write the benchmarking results to `rpc_benchmark_results.txt`.

## Benchmarking Details

The script benchmarks the following RPC calls:

- `pastelid newkey`: Creates a new PastelID.
- `pastelid sign`: Signs a message with the PastelID.
- `pastelid verify`: Verifies a signed message.
- `getbestblockhash`: Retrieves the best block hash.
- `getblock`: Retrieves details of a block.
- `getrawtransaction`: Retrieves raw transaction details.
- `masternode top`: Retrieves the masternode top list.

The benchmarking results include:

- The number of successful concurrent RPC calls.
- The number of RPC calls per second.

These results are logged with a UTC timestamp in ISO format.

## License

This project is licensed under the MIT License.
