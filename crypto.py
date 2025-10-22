# crypto.py
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

def generate_keypair():
    priv = x25519.X25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub

def derive_shared_key(priv, peer_pub_bytes):
    peer_pub = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)
    shared = priv.exchange(peer_pub)
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'secure-chat')
    return hkdf.derive(shared)
