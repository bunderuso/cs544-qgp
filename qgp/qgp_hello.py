import struct
from pdu_constants import *

#importing the header class
from qgp_header import qgp_header

class qgp_client_hello:
    #importing the message type value
    MSG_TYPE = QGP_MSG_CLIENT_HELLO

    #defining the class variables
    def __init__(self, header, client_id, client_version, capabilities):
        self.header = header
        self.client_id = client_id
        self.client_version = client_version
        self.capabilities = capabilities

    #defining the function to pack the data
    def pack(self):

        #packing the payload with the client id and client version
        payload = b''
        payload = struct.pack("!H H", self.client_id, self.client_version)

        #packing the capabilities
        cap_bytes = self.capabilities.encode("utf-8")
        payload += struct.pack("!H", len(cap_bytes)) + cap_bytes

        #packing the headers
        self.header.msg_len = qgp_header.SIZE + len(payload)
        self.header.msg_type = QGP_MSG_CLIENT_HELLO

        #returning the packed payload
        return self.header.pack() + payload

    #defining the function to unpack the payload
    @classmethod
    def unpack(cls, header, payload):
        #defining the offset to know where everything is at
        offset = 0

        #getting the client id and version and updating the offset num
        func_client_id, func_client_version = struct.unpack_from("!H H", payload, offset)
        offset += struct.calcsize("!H H")

        #getting the capalities length
        func_cap_bytes, = struct.unpack_from("!H", payload, offset)
        offset += struct.calcsize("!H")

        #getting the actual capabilities
        func_caps = payload[offset:offset + func_cap_bytes].decode("utf-8")
        offset += func_cap_bytes

        #checking the length of the message
        if header.msg_len != qgp_header.SIZE + offset:
            return "Length is not expected"

        #returning the PDU values
        return cls(header, func_client_id, func_client_version, func_caps)

#defining the class for the qgp server hello
class qgp_server_hello:  # Renamed class for clarity
    MSG_TYPE = QGP_MSG_SERVER_HELLO
    # Payload fixed part: server_id (H), server_version (H), capabilities_length (H)
    PAYLOAD_FIXED_FORMAT = "!H H H"  # Using server_id as per your PDF for ServerHello
    PAYLOAD_FIXED_SIZE = struct.calcsize(PAYLOAD_FIXED_FORMAT)

    def __init__(self, header, server_id, server_software_version,
                 capabilities_str):  # Changed client_id to server_id, server_version to server_software_version
        self.header = header
        self.server_id = server_id  # ServerHello typically sends server's ID
        self.server_software_version = server_software_version  # Version of the server application
        self.capabilities_str = capabilities_str  # Renamed for clarity

    def pack(self):
        payload_fixed_part = struct.pack(
            self.PAYLOAD_FIXED_FORMAT,
            self.server_id,
            self.server_software_version,
            len(self.capabilities_str.encode("utf-8"))  # Length of the capabilities string
        )
        cap_bytes = self.capabilities_str.encode("utf-8")

        payload = payload_fixed_part + cap_bytes

        # Update header attributes before packing the header
        self.header.msg_len = qgp_header.SIZE + len(payload)  # Use header.message_length
        self.header.msg_type = self.MSG_TYPE

        return self.header.pack() + payload

    @classmethod
    def unpack(cls, header_obj, payload_bytes):  # Changed variable names for clarity
        if len(payload_bytes) < cls.PAYLOAD_FIXED_SIZE:
            raise ValueError("Payload too short for ServerHelloPDU fixed part")

        offset = 0
        # Unpack server_id, server_software_version, and the length of the capabilities string
        unpacked_server_id, unpacked_server_sw_version, caps_str_len = struct.unpack_from(
            cls.PAYLOAD_FIXED_FORMAT, payload_bytes, offset
        )
        offset += cls.PAYLOAD_FIXED_SIZE

        if len(payload_bytes) < offset + caps_str_len:
            raise ValueError("Payload too short for declared capabilities string")

        unpacked_caps_str = payload_bytes[offset: offset + caps_str_len].decode("utf-8")
        offset += caps_str_len  # Total bytes consumed from payload_bytes for this PDU's specific part

        # Validate the total length
        # header_obj.message_length is the total length of (header + this payload)
        # qgp_header.SIZE is the size of the header
        # offset is the size of *this specific PDU's payload* that we just parsed
        if header_obj.msg_len != qgp_header.SIZE + offset:
            # Return string is not ideal for error handling, raise ValueError instead
            raise ValueError(
                f"Length mismatch in ServerHelloPDU. Header declared total: {header_obj.msg_len}, "
                f"Expected total based on parsing: {qgp_header.SIZE + offset}"
            )

        return cls(header_obj, unpacked_server_id, unpacked_server_sw_version, unpacked_caps_str)


#defining debug function for testing these two classes
if __name__ == '__main__':
    ##############################################################################
    #TESTING THE QGP HEADER
    ##############################################################################
    #defining the header variables
    version = 1
    msg_type = 9999
    msg_len = qgp_header.SIZE
    priority = 0
    header = qgp_header(version, msg_type, msg_len, priority)

    #testing the header packing
    packed_header = header.pack()
    print("packed header", packed_header)

    #testing the unpacked header
    unpacked_header,_ = qgp_header.unpack(packed_header)
    print("unpacked header", unpacked_header)
    print("Version", unpacked_header.version)
    print("Msg Type", unpacked_header.msg_type)
    print("Msg Len", unpacked_header.msg_len)
    print("Priority", unpacked_header.priority)

    ############################################################################
    #TESTING THE QGP SERVER HELLO
    ############################################################################
    #defining the server variables
    server_header = qgp_header(version=1, msg_type=0, msg_len=0, priority=0)
    server_id = 1
    server_version = 1
    capabilities = "pizza-time"
    server_class = qgp_server_hello(server_header, server_id, server_version, capabilities)

    #testing the packing
    server_packed = server_class.pack()
    print("server_packed", server_packed)

    #unpacking the header from the server hello
    server_headers, server_payload= qgp_header.unpack(server_packed)

    #testing the unpacking
    server_unpacked = server_class.unpack(server_headers, server_payload)
    print("server_unpacked", server_unpacked)
    print("header", server_unpacked.header)
    print("server_id", server_unpacked.server_id)
    print("server_version", server_unpacked.server_software_version)
    print("capabilities", server_unpacked.capabilities_str)

    ############################################################################
    # TESTING THE QGP CLIENT HELLO
    ############################################################################
    # defining the client variables
    client_header = qgp_header(version=1, msg_type=0, msg_len=0, priority=0)
    client_id = 1
    client_version = 1
    capabilities = "taco-time"
    client_class = qgp_client_hello(client_header, client_id, client_version, capabilities)

    # testing the packing
    client_packed = client_class.pack()
    print("client_packed", client_packed)

    # unpacking the header from the client hello
    client_headers, client_payload = qgp_header.unpack(client_packed)

    # testing the unpacking
    client_unpacked = client_class.unpack(client_headers, client_payload)
    print("client_unpacked", client_unpacked)
    print("header", client_unpacked.header)
    print("client_id", client_unpacked.client_id)
    print("client_version", client_unpacked.client_version)
    print("capabilities", client_unpacked.capabilities)