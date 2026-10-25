#!/usr/bin/env python3
"""Write the Storage section (Cloudflare R2) of one Vault record, with the secrets typed hidden.

The record is <mount>/<product>/<env>/<service> (the layout of references/dotnet/vault-configuration.md). Only the
`Storage` section changes: BucketName, AccountId, AccessKey and SecretKey. Every other key of the record, and any
other key inside `Storage`, is kept. A value that is already in the record is not asked again unless --replace is
given. Nothing is written when a value is empty.

Run it in your own terminal, logged in to Vault (`vault login`), with the VPN on if the Vault needs one. The values
are never printed and never passed on a command line. The script prints the bucket name (not a secret) and the
character count of the other three values; a Cloudflare R2 account id has 32 characters, an Access Key ID 32 and a
Secret Access Key 64.

    python .pinq-doq/scripts/storage_keys.py --product <product> --env test --service <service>
"""
import argparse
import getpass
import json
import os
import subprocess
import sys

SECTION = "Storage"
EXPECTED_LENGTHS = {"AccountId": 32, "AccessKey": 32, "SecretKey": 64}
SECRET_PROMPTS = {
    "AccountId": "AccountId (Cloudflare, hidden): ",
    "AccessKey": "AccessKey (R2 Access Key ID, hidden): ",
    "SecretKey": "SecretKey (R2 Secret Access Key, hidden): ",
}


def data_path(mount, product, env, service):
    return f"{mount}/data/{product}/{env}/{service}"


def merge_storage(record, values):
    merged = dict(record)
    section = dict(merged.get(SECTION) or {})
    section.update(values)
    merged[SECTION] = section
    return merged


def length_report(values):
    parts = [f"BucketName ({values['BucketName']})"]
    for key in ("AccountId", "AccessKey", "SecretKey"):
        parts.append(f"{key} ({len(values[key])} characters, expected {EXPECTED_LENGTHS[key]})")
    return "Storage written: " + ", ".join(parts)


def read_record(vault, path):
    result = subprocess.run([vault, "read", "-format=json", path], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("Could not read Vault: " + last_line(result.stderr))
    return json.loads(result.stdout)["data"]["data"]


def write_record(vault, path, record):
    result = subprocess.run([vault, "write", path, "-"], input=json.dumps({"data": record}), capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("Could not write Vault: " + last_line(result.stderr))


def last_line(text):
    lines = text.strip().splitlines()
    return lines[-1] if lines else "no message"


def ask(existing, key, replace):
    if existing.get(key) and not replace:
        return existing[key]
    if key == "BucketName":
        return input("BucketName: ").strip()
    return getpass.getpass(SECRET_PROMPTS[key]).strip()


def main():
    parser = argparse.ArgumentParser(description="Write the Storage section of one Vault record with hidden input.")
    parser.add_argument("--product", required=True, help="lower case product name, first segment of the record path")
    parser.add_argument("--env", required=True, choices=["test", "prod", "local"])
    parser.add_argument("--service", required=True, help="record name, for example user-api")
    parser.add_argument("--mount", default="apps")
    parser.add_argument("--vault-bin", default="vault", help="path of the Vault CLI (default: vault from PATH)")
    parser.add_argument("--replace", action="store_true", help="ask again for values that are already in the record")
    args = parser.parse_args()

    if not os.environ.get("VAULT_ADDR"):
        sys.exit("Set VAULT_ADDR to the address of your Vault first.")
    path = data_path(args.mount, args.product, args.env, args.service)
    record = read_record(args.vault_bin, path)
    existing = record.get(SECTION) or {}

    values = {key: ask(existing, key, args.replace) for key in ("BucketName", "AccountId", "AccessKey", "SecretKey")}
    if not all(values.values()):
        sys.exit("A value is empty, nothing was changed.")

    write_record(args.vault_bin, path, merge_storage(record, values))
    print(length_report(values))


if __name__ == "__main__":
    main()
