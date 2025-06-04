import struct
from pdu_constants import *

#importing the header class
from qgp_header import qgp_header

#defining the error class
class qgp_errors:
    # defining the class variables
    def __init__(self, header, error_code, error_length, severity, error_message):
        self.header = header
        self.error_code = error_code
        self.error_length = error_length
        self.severity = severity
        self.error_message = error_message

    # defining the function to pack the values
    def pack(self):
        # packing the payload with the client id and client version
        payload = b''
        payload = struct.pack("!H H H", self.error_code, self.error_length, self.severity)

        # packing the capabilities
        err_msg_bytes = self.error_message.encode("utf-8")
        payload += struct.pack("!H", len(err_msg_bytes)) + err_msg_bytes

        # packing the headers
        self.header.msg_len = qgp_header.SIZE + len(payload)
        self.header.msg_type = QGP_MSG_CLIENT_HELLO

        # returning the packed payload
        return self.header.pack() + payload

    # defining the function to unpack the payload
    @classmethod
    def unpack(cls, header, payload):
        # defining the offset to know where everything is at
        offset = 0

        # getting the client id and version and updating the offset num
        func_error_code, func_error_length, func_severity = struct.unpack_from("!H H H", payload, offset)
        offset += struct.calcsize("!H H H")

        # getting the text length
        func_err_msg_bytes, = struct.unpack_from("!H", payload, offset)
        offset += struct.calcsize("!H")

        # getting the actual capabilities
        func_err_msg = payload[offset:offset + func_err_msg_bytes].decode("utf-8")
        offset += func_err_msg_bytes

        # checking the length of the message
        if header.msg_len != qgp_header.SIZE + offset:
            return "Length is not expected"

        # returning the PDU values
        return cls(header, func_error_code, func_error_length, func_severity, func_err_msg)

#defining debug function
if __name__ == "__main__":
    ############################################################################
    # TESTING THE QGP ERRORS
    ############################################################################
    # defining the text communication variables
    error_header = qgp_header(version=1, msg_type=0, msg_len=0, priority=0)
    error_code = 99
    severity = 1
    error_message = "code banana"
    error_length = len(error_message)

    error_class = qgp_errors(error_header, error_code, error_length, severity, error_message)

    # testing the packing
    error_packed = error_class.pack()
    print("error_packed", error_packed)

    # unpacking the header from the error hello
    error_headers, error_payload = qgp_header.unpack(error_packed)

    # testing the unpacking
    error_unpacked = error_class.unpack(error_headers, error_payload)
    print("error_unpacked", error_unpacked)
    print("header", error_unpacked.header)
    print("error text length", error_unpacked.error_length)
    print("error text", error_unpacked.error_message)
    print("error code", error_unpacked.error_code)
    print("error severity", error_unpacked.severity)