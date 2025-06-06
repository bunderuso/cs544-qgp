import struct


#defining the class for the qgp headers
#this includes packing and unpacking the headers
class qgp_header:
    FORMAT = "!B H I B"
    SIZE = struct.calcsize(FORMAT)

    #defining the header variables
    def __init__(self, version, msg_type, msg_len, priority):
        self.version = version
        self.msg_type = msg_type
        self.msg_len = msg_len
        self.priority = priority

    #defining function to package the headers
    def pack(self):
        print("Packing with", self.FORMAT, self.msg_type, self.msg_len, self.priority)
        return struct.pack(self.FORMAT, self.version, self.msg_type, self.msg_len, self.priority)

    @classmethod
    def unpack(cls, data):
        #making sure the header length is valid
        if len(data) < cls.SIZE:
            return "Header length not the valid length"

        #unpacking the header and saving to the class variables
        print("Unpacking with", cls.FORMAT)
        func_version, func_msg_type, func_msg_len, func_priority = struct.unpack(cls.FORMAT, data[:cls.SIZE])
        remaining_data = data[cls.SIZE:]
        return cls(func_version, func_msg_type, func_msg_len, func_priority), remaining_data