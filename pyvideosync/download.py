"""
Download folders from Remote

Usage:
- export SSH_PASSWORD=*******
- specify remote paths in config.yaml
- python download.py Elias-yewen
"""

import os
import yaml
import paramiko
from scp import SCPClient
import argparse
import sys


def create_ssh_client(hostname, username, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy)
    client.connect(hostname, username=username, password=password)
    return client


def download_folder(ssh_client, remote_path, local_path):
    os.makedirs(local_path, exist_ok=True)
    with SCPClient(ssh_client.get_transport()) as scp:
        scp.get(remote_path, local_path, recursive=True)
    print(f"Downloaded {remote_path} to {local_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Download folders from a specified SSH host."
    )
    parser.add_argument(
        "host_name", type=str, help="The name of the host to download from"
    )

    args = parser.parse_args()
    host_name = args.host_name

    with open("config.yaml", "r") as config_file:
        config = yaml.safe_load(config_file)

    host_config = next(
        (host for host in config["hosts"] if host["name"] == host_name), None
    )

    if host_config is None:
        print(f"No configuration found for host: {host_name}")
        sys.exit(1)

    hostname = host_config["hostname"]
    username = host_config["username"]
    password = host_config["password"]
    base_local_path = host_config["base_local_path"]
    paths = host_config["paths"]

    print(f"Connecting to {hostname} as {username}")
    ssh_client = create_ssh_client(hostname, username, password)

    for path in paths:
        remote_path = path["remote_path"]
        print(f"Preparing to download from {remote_path} to {base_local_path}...")
        download_folder(ssh_client, remote_path, base_local_path)
        print(f"Completed download from {remote_path} to {base_local_path}")

    ssh_client.close()
    print("All downloads completed.")


if __name__ == "__main__":
    main()
