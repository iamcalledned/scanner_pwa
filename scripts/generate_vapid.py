#!/usr/bin/env python3
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64
import os

# generate private key
priv = ec.generate_private_key(ec.SECP256R1(), default_backend())
# private key as PEM
priv_pem = priv.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
# get public key in uncompressed point format (04 || X || Y)
pub = priv.public_key()
numbers = pub.public_numbers()
x = numbers.x.to_bytes(32, 'big')
Y = numbers.y.to_bytes(32, 'big')
raw = b'\x04' + x + Y
# base64url
pub_b64 = base64.urlsafe_b64encode(raw).rstrip(b"=")

root = os.path.join(os.path.dirname(__file__), '..')
with open(os.path.join(root, 'vapid_private.key'), 'wb') as f:
    f.write(priv_pem)
with open(os.path.join(root, 'vapid_public.key'), 'wb') as f:
    f.write(pub_b64)

print('VAPID private written to vapid_private.key (PEM)')
print('VAPID public written to vapid_public.key (base64url)')
print('PUBLIC KEY (base64url):')
print(pub_b64.decode())
print('\nPRIVATE KEY (PEM):')
print(priv_pem.decode())
