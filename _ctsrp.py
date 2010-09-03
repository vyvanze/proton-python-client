  # N    A large safe prime (N = 2q+1, where q is prime)
  #      All arithmetic is done modulo N.
  # g    A generator modulo N
  # k    Multiplier parameter (k = H(N, g) in SRP-6a, k = 3 for legacy SRP-6)
  # s    User's salt
  # I    Username
  # p    Cleartext Password
  # H()  One-way hash function
  # ^    (Modular) Exponentiation
  # u    Random scrambling parameter
  # a,b  Secret ephemeral values
  # A,B  Public ephemeral values
  # x    Private key (derived from p and s)
  # v    Password verifier
  
import os
import sys
import hashlib
import random
import ctypes
import atexit
import time


SHA256_DIGEST_LENGTH = 32

N_HEX  = "AC6BDB41324A9A9BF166DE5E1389582FAF72B6651987EE07FC3192943DB56050A37329CBB4A099ED8193E0757767A13DD52312AB4B03310DCD7F48A9DA04FD50E8083969EDB767B0CF6095179A163AB3661A05FBD5FAAAE82918A9962F0B93B855F97993EC975EEAA80D740ADBF4FF747359D041D5C33EA71D281E446B14773BCA97B43A23FB801676BD207A436C6481F1D2B9078717461A5B9D32E688F87748544523B524B0D57D5EA77A2775D2ECFA032CFBDBF52FB3786160279004E57AE6AF874E7303CE53299CCC041C7BC308D82A5698F3A8D0C38271AE35F8E9DBFBB694B5C803D89F7AE435DE236D525F54759B65E372FCD68EF20FA7111F9E4AFF73"
G_HEX  = "2"
HNxorg = None

dlls = list()

if 'win' in sys.platform:
    for d in ('libeay32.dll', 'libssl32.dll', 'ssleay32.dll'):
        try:
            dlls.append( ctypes.cdll.LoadLibrary(d) )
        except:
            pass
else:
    dlls.append( ctypes.cdll.LoadLibrary('libssl.so') )
        
    
class BIGNUM_Struct (ctypes.Structure):
    _fields_ = [ ("d",     ctypes.c_void_p),
                 ("top",   ctypes.c_int),
                 ("dmax",  ctypes.c_int),
                 ("neg",   ctypes.c_int),
                 ("flags", ctypes.c_int) ]

                 
class BN_CTX_Struct (ctypes.Structure):
    _fields_ = [ ("_", ctypes.c_byte) ]

    
BIGNUM = ctypes.POINTER( BIGNUM_Struct )
BN_CTX = ctypes.POINTER( BN_CTX_Struct )


def load_func( name, args, returns = ctypes.c_int):
    d = sys.modules[ __name__ ].__dict__
    f = None
    
    for dll in dlls:
        try:
            f = getattr(dll, name)
            f.argtypes = args
            f.restype  = returns
            d[ name ] = f
            return
        except:
            pass
    raise ImportError('Unable to load required functions from SSL dlls')
    
    
load_func( 'BN_new',   [],         BIGNUM )
load_func( 'BN_free',  [ BIGNUM ], None )
load_func( 'BN_init',  [ BIGNUM ], None )
load_func( 'BN_clear', [ BIGNUM ], None )

load_func( 'BN_CTX_new',  []        , BN_CTX )
load_func( 'BN_CTX_init', [ BN_CTX ], None   )
load_func( 'BN_CTX_free', [ BN_CTX ], None   )

load_func( 'BN_cmp',      [ BIGNUM, BIGNUM ], ctypes.c_int )

load_func( 'BN_num_bits', [ BIGNUM ], ctypes.c_int )

load_func( 'BN_add',     [ BIGNUM, BIGNUM, BIGNUM ] )
load_func( 'BN_sub',     [ BIGNUM, BIGNUM, BIGNUM ] )
load_func( 'BN_mul',     [ BIGNUM, BIGNUM, BIGNUM, BN_CTX ] )
load_func( 'BN_div',     [ BIGNUM, BIGNUM, BIGNUM, BIGNUM, BN_CTX ] )
load_func( 'BN_mod_exp', [ BIGNUM, BIGNUM, BIGNUM, BIGNUM, BN_CTX ] )

load_func( 'BN_rand',    [ BIGNUM, ctypes.c_int, ctypes.c_int, ctypes.c_int ] )

load_func( 'BN_bn2bin',  [ BIGNUM, ctypes.c_char_p ] )
load_func( 'BN_bin2bn',  [ ctypes.c_char_p, ctypes.c_int, BIGNUM ], BIGNUM )

load_func( 'BN_hex2bn',  [ ctypes.POINTER(BIGNUM), ctypes.c_char_p ] )
load_func( 'BN_bn2hex',  [ BIGNUM ], ctypes.c_char_p )

load_func( 'CRYPTO_free', [ ctypes.c_char_p ] )

load_func( 'RAND_seed', [ ctypes.c_char_p, ctypes.c_int ] )


def BN_num_bytes(a):
    return ((BN_num_bits(a)+7)/8)


def BN_mod(rem,m,d,ctx):
    return BN_div(None, rem, m, d, ctx)


def BN_is_zero( n ):
    return n[0].top == 0


def bn_to_bytes( n ):
    b = ctypes.create_string_buffer( BN_num_bytes(n) )
    BN_bn2bin(n, b)
    return b.raw

    
def bytes_to_bn( dest_bn, bytes ):
    BN_bin2bn(bytes, len(bytes), dest_bn)
    
 
def H_str( dest_bn, s ):
    d = hashlib.sha256(s).digest()
    buff = ctypes.create_string_buffer( s )
    BN_bin2bn(d, len(d), dest)


def H_bn( dest, n ):
    bin = ctypes.create_string_buffer( BN_num_bytes(n) )
    BN_bn2bin(n, bin)
    d = hashlib.sha256( bin.raw ).digest()
    BN_bin2bn(d, len(d), dest)
    
    
def H_bn_bn( dest, n1, n2 ):
    h    = hashlib.sha256()
    bin1 = ctypes.create_string_buffer( BN_num_bytes(n1) )
    bin2 = ctypes.create_string_buffer( BN_num_bytes(n2) )
    BN_bn2bin(n1, bin1)
    BN_bn2bin(n2, bin2)
    h.update( bin1.raw )
    h.update( bin2.raw )
    d = h.digest()
    BN_bin2bn(d, len(d), dest)
    
    
def H_bn_str( dest, n, s ):
    h   = hashlib.sha256()
    bin = ctypes.create_string_buffer( BN_num_bytes(n) )
    BN_bn2bin(n, bin)
    h.update( bin.raw )
    h.update( s )
    d = h.digest()
    BN_bin2bn(d, len(d), dest)
 
    
def calculate_x( dest, salt, username, password ):
    up = hashlib.sha256('%s:%s' % (username, password )).digest()
    H_bn_str( dest, salt, up )
    
    
def update_hash( ctx, n ):
    buff = ctypes.create_string_buffer( BN_num_bytes(n) )
    BN_bn2bin(n, buff)
    ctx.update( buff.raw )

    
def calculate_M( I, s, A, B, K ):
    h = hashlib.sha256()
    h.update( HNxorg )
    h.update( hashlib.sha256(I).digest() )
    update_hash( h, s )
    update_hash( h, A )
    update_hash( h, B )
    h.update( K )
    return h.digest()
    

def calculate_H_AMK( A, M, K ):
    h = hashlib.sha256()
    update_hash( h, A )
    h.update( M )
    h.update( K )
    return h.digest()

    
def calculate_HN_xor_Hg():
    global HNxorg
    
    bN = ctypes.create_string_buffer( BN_num_bytes(N) )
    bg = ctypes.create_string_buffer( BN_num_bytes(g) )
    
    BN_bn2bin(N, bN)
    BN_bn2bin(g, bg)
    
    hN = hashlib.sha256( bN.raw ).digest()
    hg = hashlib.sha256( bg.raw ).digest()
    
    HNxorg  = ''.join( chr( ord(hN[i]) ^ ord(hg[i]) ) for i in range(0,len(hN)) )
    
  
def gen_sv( username, password ):
    s    = BN_new()
    v    = BN_new()
    x    = BN_new()
    ctx  = BN_CTX_new()

    BN_rand(s, 32, -1, 0);
        
    calculate_x(x, s, username, password )
        
    BN_mod_exp(v, g, x, N, ctx)
    
    salt     = bn_to_bytes( s )
    verifier = bn_to_bytes( v )
    
    BN_free(s)
    BN_free(v)
    BN_free(x)
    BN_CTX_free(ctx)
    
    return salt, verifier
    
  

class Verifier (object):
    def __init__(self,  username, bytes_s, bytes_v, bytes_A):
        self.A     = BN_new()
        self.B     = BN_new()
        self.K     = None
        self.S     = BN_new()
        self.u     = BN_new()
        self.b     = BN_new()
        self.s     = BN_new()
        self.v     = BN_new()
        self.tmp1  = BN_new()
        self.tmp2  = BN_new()
        self.ctx   = BN_CTX_new()
        self.I     = username
        self.M     = None
        self.H_AMK = None
        self._authenticated = False
        
        self.safety_failed = False
        
        bytes_to_bn( self.s, bytes_s )
        bytes_to_bn( self.v, bytes_v )        
        bytes_to_bn( self.A, bytes_A )
        
        # SRP-6a safety check
        BN_mod(self.tmp1, self.A, N, self.ctx)
        
        if BN_is_zero(self.tmp1):
            self.safety_failed = True
        else:                    
            BN_rand(self.b, 256, -1, 0)
            
            # B = kv + g^b
            BN_mul(self.tmp1, k, self.v, self.ctx)
            BN_mod_exp(self.tmp2, g, self.b, N, self.ctx)
            BN_add(self.B, self.tmp1, self.tmp2)
            
            H_bn_bn(self.u, self.A, self.B)
            
            # S = (A *(v^u)) ^ b
            BN_mod_exp(self.tmp1, self.v, self.u, N, self.ctx)
            BN_mul(self.tmp2, self.A, self.tmp1, self.ctx)
            BN_mod_exp(self.S, self.tmp2, self.b, N, self.ctx)
            
            self.K = hashlib.sha256( bn_to_bytes(self.S) ).digest()
            
            self.M     = calculate_M( self.I, self.s, self.A, self.B, self.K )
            self.H_AMK = calculate_H_AMK( self.A, self.M, self.K )
        
        
    def __del__(self):
        BN_free(self.A)
        BN_free(self.B)
        BN_free(self.S)
        BN_free(self.u)
        BN_free(self.b)
        BN_free(self.s)
        BN_free(self.v)
        BN_free(self.tmp1)
        BN_free(self.tmp2)
        BN_CTX_free(self.ctx)
        
        
    def authenticated(self):
        return self._authenticated

    
    def get_username(self):
        return self.I
    
    
    def get_session_key(self):
        return self.K if self._authenticated else None
    
    
    # returns (bytes_s, bytes_B) on success, (None,None) if SRP-6a safety check fails
    def get_challenge(self):
        if self.safety_failed:
            return None, None
        else:
            return (bn_to_bytes(self.s), bn_to_bytes(self.B))
    
        
    def verify_session(self, user_M):
        if user_M == self.M:
            self._authenticated = True
            return self.H_AMK
        

        
    
class User (object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.a     = BN_new()
        self.A     = BN_new()
        self.B     = BN_new()
        self.s     = BN_new()
        self.S     = BN_new()
        self.u     = BN_new()
        self.x     = BN_new()
        self.v     = BN_new()
        self.tmp1  = BN_new()
        self.tmp2  = BN_new()
        self.tmp3  = BN_new()
        self.ctx   = BN_CTX_new()
        self.M     = None
        self.K     = None
        self.H_AMK = None
        self._authenticated = False
        
        BN_rand(self.a, 256, -1, 0)
        
        BN_mod_exp(self.A, g, self.a, N, self.ctx)
        
        
    def __del__(self):
        BN_free(self.a)
        BN_free(self.A)
        BN_free(self.B)
        BN_free(self.s)
        BN_free(self.S)
        BN_free(self.u)
        BN_free(self.x)
        BN_free(self.v)
        BN_free(self.tmp1)
        BN_free(self.tmp2)
        BN_free(self.tmp3)
        BN_CTX_free(self.ctx)

                    
    def authenticated(self):
        return self._authenticated

    
    def get_username(self):
        return self.username
    
    
    def get_session_key(self):
        return self.K if self._authenticated else None
        
        
    def start_authentication(self):
        return (self.username, bn_to_bytes(self.A))
        
        
    # Returns M or None if SRP-6a safety check is violated
    def process_challenge(self, bytes_s, bytes_B):
        
        bytes_to_bn( self.s, bytes_s )
        bytes_to_bn( self.B, bytes_B )
        
        # SRP-6a safety check
        if BN_is_zero(self.B):
            return None
            
        H_bn_bn(self.u, self.A, self.B)
        
        # SRP-6a safety check
        if BN_is_zero(self.u):
            return None
        
        calculate_x( self.x, self.s, self.username, self.password )
        
        BN_mod_exp(self.v, g, self.x, N, self.ctx)
        
        # S = (B - k*(g^x)) ^ (a + ux)

        BN_mul(self.tmp1, self.u, self.x, self.ctx)
        BN_add(self.tmp2, self.a, self.tmp1)            # tmp2 = (a + ux)
        BN_mod_exp(self.tmp1, g, self.x, N, self.ctx)
        BN_mul(self.tmp3, k, self.tmp1, self.ctx)       # tmp3 = k*(g^x)
        BN_sub(self.tmp1, self.B, self.tmp3)            # tmp1 = (B - K*(g^x))
        BN_mod_exp(self.S, self.tmp1, self.tmp2, N, self.ctx)

        self.K     = hashlib.sha256( bn_to_bytes(self.S) ).digest()
        self.M     = calculate_M( self.username, self.s, self.A, self.B, self.K )
        self.H_AMK = calculate_H_AMK( self.A, self.M, self.K )

        return self.M
        
        
    def verify_session(self, host_HAMK):
        if self.H_AMK == host_HAMK:
            self._authenticated = True
        
#---------------------------------------------------------
# Init
#
N      = BN_new()
g      = BN_new()
k      = BN_new()
HNxorg = None

BN_hex2bn( N, N_HEX )
BN_hex2bn( g, G_HEX )
H_bn_bn(k, N, g)

calculate_HN_xor_Hg()

RAND_seed( os.urandom(32), 32 )

def cleanup():
    BN_free( N )
    BN_free( g )
    BN_free( k )
    
atexit.register( cleanup )