#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try:
    from Crypto.Cipher import AES
    from hashlib import md5
    import os, sys, base64
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)
#=======================================================
# K
#=======================================================
def K(p, s, k, i):
    dtot = md5(p + s).digest()
    d = [dtot]
    while len(dtot) < i + k:
        d.append(md5(d[-1] + p + s).digest())
        dtot += d[-1]
    return (dtot[:k], dtot[k:k + i])
#=======================================================
# Salted Password for IMC
#=======================================================
def E(ps, pa):
    s = os.urandom(8)
    k, i = K(ps, s, 32, 16)
    pl = 16 - len(pa) % 16
    if isinstance(pa, str):
        pp = pa + chr(pl) * pl
    else: pp = pa + bytearray([pl] * pl)
    c = AES.new(k, AES.MODE_CBC, i)
    ct = c.encrypt(pp)
    ep = base64.b64encode(b'Salted__' + s + ct)
    if type(ep) is not str: ep = ep.decode('utf8')
    return ep
