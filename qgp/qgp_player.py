import struct
#importing the libraries in a way so this file can be ran in isolation for testing
try:
    from pdu_constants import *
    from qgp_header import qgp_header
except:
    from qgp.pdu_constants import *
    from qgp.qgp_header import qgp_header

#defining a class for player movement
class qgp_player_movement:
    FORMAT = "!I I I I I I I"

    #defining the class variables
    def __init__(self, header, player_id, movement_type, direction, x_position, y_position, z_position, speed):
        self.header = header
        self.player_id = player_id
        self.movement_type = movement_type
        self.direction = direction
        self.x_position = x_position
        self.y_position = y_position
        self.z_position = z_position
        self.speed = speed
        
    #defining function to pack the variables
    def pack(self):
        #packing the payload
        payload = struct.pack(self.FORMAT, self.player_id, self.movement_type, self.direction, self.x_position, self.y_position,self.z_position, self.speed)
        
        #creating the headers
        self.header.msg_len = qgp_header.SIZE + len(payload)
        self.header.msg_type = QGP_MSG_PLAYER_MOVEMENT
        
        
        return self.header.pack() + payload
    
    #defining function to unpack the variables 
    @classmethod
    def unpack(cls, header, payload):
        # defining the offset to know where everything is at
        offset = 0

        # getting the client id and version and updating the offset num
        func_player_id, func_movement_type, func_direction, func_x_position, func_y_position, func_z_position, func_speed = struct.unpack_from("!I I I I I I I", payload, offset)
        offset += struct.calcsize("!I I I I I I I")

        # getting the capalities length
        #func_cap_bytes, = struct.unpack_from("!H", payload, offset)
        #offset += struct.calcsize("!H")

        # getting the actual capabilities
        #func_caps = payload[offset:offset + func_cap_bytes].decode("utf-8")
        #offset += func_cap_bytes

        # checking the length of the message
        if header.msg_len != qgp_header.SIZE + offset:
            return "Length is not expected"

        # returning the PDU values
        return cls(header, func_player_id, func_movement_type, func_direction, func_x_position, func_y_position, func_z_position, func_speed)

#defining class to join a match
class qgp_player_join:
    FORMAT = "!I I I"

    #defining the class variables
    def __init__(self, header, player_id, match_id, player_team):
        self.header = header
        self.player_id = player_id
        self.match_id = match_id
        self.player_team = player_team

    #defining the packing class
    def pack(self):
        payload = struct.pack(self.FORMAT, self.player_id, self.match_id, self.player_team)
        self.header.msg_len = qgp_header.SIZE + len(payload)
        self.header.msg_type = QGP_MSG_PLAYER_JOIN
        return self.header.pack() + payload

    #defining the unpacking class
    @classmethod
    def unpack(cls, header, payload):
        offset = 0
        func_player_id, func_match_id, func_player_team = struct.unpack_from(cls.FORMAT, payload, offset)
        offset += struct.calcsize(cls.FORMAT)

        # checking the length of the message
        if header.msg_len != qgp_header.SIZE + offset:
            return "Length is not expected"

        #returning the unpacked values
        return cls(header, func_player_id, func_match_id, func_player_team)

#defining the class for player leaving
class qgp_player_leave:
    FORMAT = "!I I I"

    # defining the class variables
    def __init__(self, header, player_id, match_id, player_team):
        self.header = header
        self.player_id = player_id
        self.match_id = match_id
        self.player_team = player_team

    # defining the packing class
    def pack(self):
        payload = struct.pack(self.FORMAT, self.player_id, self.match_id, self.player_team)
        self.header.msg_len = qgp_header.SIZE + len(payload)
        self.header.msg_type = QGP_MSG_PLAYER_LEAVE
        return self.header.pack() + payload

    # defining the unpacking class
    @classmethod
    def unpack(cls, header, payload):
        offset = 0
        func_player_id, func_match_id, func_player_team = struct.unpack_from(cls.FORMAT, payload, offset)
        offset += struct.calcsize(cls.FORMAT)

        # checking the length of the message
        if header.msg_len != qgp_header.SIZE + offset:
            return "Length is not expected"

        # returning the unpacked values
        return cls(header, func_player_id, func_match_id, func_player_team)

#defining class for the player status
class qgp_player_status:
    FORMAT = "!I I I"

    #defining the class variables
    def __init__(self, header, player_id, player_health, player_dmg_taken):
        self.header = header
        self.player_id = player_id
        self.player_health = player_health
        self.player_dmg_taken = player_dmg_taken

    #defining class to pack these values
    def pack(self):
        payload = struct.pack(self.FORMAT, self.player_id, self.player_health, self.player_dmg_taken)
        self.header.msg_len = qgp_header.SIZE + len(payload)
        self.header.msg_type = QGP_MSG_PLAYER_STATUS
        return self.header.pack() + payload

    @classmethod
    def unpack(cls, header, payload):
        offset = 0
        func_player_id, func_health, func_dmg_taken = struct.unpack_from(cls.FORMAT, payload, offset)
        offset += struct.calcsize(cls.FORMAT)

        #checking the length is expected
        if header.msg_len != qgp_header.SIZE + offset:
            return "Length is not expected"

        #returning the unpacked data
        return cls(header, func_player_id, func_health, func_dmg_taken)

    
#defining debug function
if __name__ == "__main__":
    ############################################################################
    # TESTING THE QGP PLAYER MOVEMENT
    ############################################################################
    # defining the text communication variables
    move_header = qgp_header(version=1, msg_type=0, msg_len=0, priority=0)
    move_player_id = 1
    move_direction = 1
    move_x_position = 7
    move_y_position = 8
    move_z_position = 9
    move_speed = 10
    move_type = 100

    move_class = qgp_player_movement(move_header, move_player_id, move_type, move_direction, move_x_position, move_y_position, move_z_position, move_speed)

    # testing the packing
    move_packed = move_class.pack()
    print("move_packed", move_packed)

    # unpacking the header from the move hello
    move_headers, move_payload = qgp_header.unpack(move_packed)

    # testing the unpacking
    move_unpacked = move_class.unpack(move_headers, move_payload)
    print("move_unpacked", move_unpacked)
    print("header", move_unpacked.header)
    print("move player id", move_unpacked.player_id)
    print("move direction", move_unpacked.direction)
    print("move x", move_unpacked.x_position)
    print("move y", move_unpacked.y_position)
    print("move z", move_unpacked.z_position)
    print("move speed", move_unpacked.speed)
    print("move type", move_unpacked.movement_type)

