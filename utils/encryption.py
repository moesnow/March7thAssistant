import ctypes

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', ctypes.c_uint), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

def wdp_encrypt(data_bytes: bytes) -> bytes:
    blob_in = DATA_BLOB(len(data_bytes), ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_ubyte)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise ctypes.WinError()
    encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return encrypted

def wdp_decrypt(enc_bytes: bytes) -> bytes:
    blob_in = DATA_BLOB(len(enc_bytes), ctypes.cast(ctypes.create_string_buffer(enc_bytes), ctypes.POINTER(ctypes.c_ubyte)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise ctypes.WinError()
    decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return decrypted