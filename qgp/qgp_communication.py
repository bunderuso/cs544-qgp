import struct
#importing the libraries in a way so this file can be ran in isolation for testing
try:
    from pdu_constants import *
    from qgp_header import qgp_header
except:
    from qgp.pdu_constants import *
    from qgp.qgp_header import qgp_header

#defining class for qgp text chat
class qgp_text_chat:
    #defining the class variables
    def __init__(self, header, text_length, text):
        self.header = header
        self.text_length = text_length
        self.text = text

    #defining the function to pack the values
    def pack(self):
        # packing the payload with the client id and client version
        payload = b''
        payload = struct.pack("!H", self.text_length)

        # packing the capabilities
        text_bytes = self.text.encode("utf-8")
        payload += struct.pack("!H", len(text_bytes)) + text_bytes

        # packing the headers
        self.header.msg_len = qgp_header.SIZE + len(payload)
        #self.header.msg_type = QGP_MSG_TEXT_CHAT

        # returning the packed payload
        return self.header.pack() + payload


    #defining the function to unpack the payload
    @classmethod
    def unpack(cls, header, payload):
        #defining the offset to know where everything is at
        offset = 0

        #getting the client id and version and updating the offset num
        func_text_length  = struct.unpack_from("!H", payload, offset)
        offset += struct.calcsize("!H")

        #getting the text length
        func_text_bytes, = struct.unpack_from("!H", payload, offset)
        offset += struct.calcsize("!H")

        #getting the actual capabilities
        func_text = payload[offset:offset + func_text_bytes].decode("utf-8")
        offset += func_text_bytes

        #checking the length of the message
        if header.msg_len != qgp_header.SIZE + offset:
            return "Length is not expected"

        #returning the PDU values
        return cls(header, func_text_length, func_text)

#defining the debug function for testing
if __name__ == "__main__":
    ############################################################################
    # TESTING THE QGP TEXT COMMUNICATION
    ############################################################################
    # defining the text communication variables
    text_com_header = qgp_header(version=1, msg_type=0, msg_len=0, priority=0)
    message = "its pizza time!"
    message_len = len(message)

    text_com_class = qgp_text_chat(text_com_header, text_length=message_len, text=message)

    # testing the packing
    text_com_packed = text_com_class.pack()
    print("text_com_packed", text_com_packed)

    # unpacking the header from the text_com hello
    text_com_headers, text_com_payload = qgp_header.unpack(text_com_packed)

    # testing the unpacking
    text_com_unpacked = text_com_class.unpack(text_com_headers, text_com_payload)
    print("text_com_unpacked", text_com_unpacked)
    print("header", text_com_unpacked.header)
    print("text_com text length", text_com_unpacked.text_length)
    print("text_com text", text_com_unpacked.text)