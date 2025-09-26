#!/usr/bin/env python3
"""Convert an existing PKCS8 VAPID private key PEM into a Traditional EC PRIVATE KEY PEM.

This helps downstream libraries that expect the EC private key header.
"""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import sys
import os

ROOT = os.path.join(os.path.dirname(__file__), '..')
PRIV = os.path.join(ROOT, 'vapid_private.key')

if __name__ == '__main__':
    if not os.path.exists(PRIV):
        print('no vapid_private.key found at', PRIV)
        sys.exit(1)
    with open(PRIV, 'rb') as f:
        data = f.read()
    # Load private key (supports PKCS8)
    priv = serialization.load_pem_private_key(data, password=None, backend=default_backend())
    # Re-serialize as TraditionalOpenSSL (EC PRIVATE KEY)
    out = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    # Backup original
    with open(PRIV + '.bak', 'wb') as f:
        f.write(data)
    with open(PRIV, 'wb') as f:
        f.write(out)
    print('rewrote', PRIV, 'and saved backup', PRIV + '.bak')
