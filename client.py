# client.py
import asyncio
import websockets
import json
import argparse
import base64
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

def b64(b: bytes) -> str:
    return base64.b64encode(b).decode('ascii')

def ub64(s: str) -> bytes:
    return base64.b64decode(s.encode('ascii'))

def derive_shared_key(priv: x25519.X25519PrivateKey, peer_pub_bytes: bytes) -> bytes:
    peer_pub = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)
    shared = priv.exchange(peer_pub)
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'secure-chat')
    return hkdf.derive(shared)

async def interact(uri, username):
    priv = x25519.X25519PrivateKey.generate()
    pub = priv.public_key()
    pub_bytes = pub.public_bytes()

    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type":"register","username":username,"pubkey": b64(pub_bytes)}))
        print(await ws.recv())

        async def receiver():
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                t = msg.get('type')
                if t == 'forward':
                    sender = msg.get('sender')
                    sender_pub = ub64(msg.get('sender_pub'))
                    nonce = ub64(msg.get('nonce'))
                    ciphertext = ub64(msg.get('ciphertext'))
                    key = derive_shared_key(priv, sender_pub)
                    aead = ChaCha20Poly1305(key)
                    plaintext = aead.decrypt(nonce, ciphertext, None)
                    print(f"\\n[{sender}] -> {plaintext.decode()}\\n> ", end='')
                elif t == 'list':
                    print("Online users:", msg['users'])
                elif t == 'error':
                    print("Error:", msg['msg'])
                else:
                    print("Server:", msg)

        async def sender_loop():
            while True:
                line = await asyncio.get_event_loop().run_in_executor(None, lambda: input('> '))
                if line.startswith('/list'):
                    await ws.send(json.dumps({"type":"list"}))
                elif line.startswith('/send '):
                    parts = line.split(' ', 2)
                    if len(parts) < 3:
                        print("Usage: /send <user> <message>")
                        continue
                    to, message = parts[1], parts[2]
                    await ws.send(json.dumps({"type":"get_pub","username":to}))
                    resp = json.loads(await ws.recv())
                    if resp.get('type') != 'pubkey':
                        print("User not found or offline.")
                        continue
                    peer_pub_b64 = resp['pubkey']
                    key = derive_shared_key(priv, ub64(peer_pub_b64))
                    aead = ChaCha20Poly1305(key)
                    nonce = ChaCha20Poly1305.generate_key()[:12]
                    ct = aead.encrypt(nonce, message.encode(), None)
                    payload = {
                        "type":"forward",
                        "to":to,
                        "sender":username,
                        "sender_pub":b64(pub_bytes),
                        "nonce":b64(nonce),
                        "ciphertext":b64(ct)
                    }
                    await ws.send(json.dumps(payload))
                elif line.startswith('/quit'):
                    print("Goodbye!")
                    await ws.close()
                    return

        await asyncio.gather(receiver(), sender_loop())

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', required=True)
    parser.add_argument('--server', default='ws://localhost:8765')
    args = parser.parse_args()
    asyncio.run(interact(args.server, args.username))
