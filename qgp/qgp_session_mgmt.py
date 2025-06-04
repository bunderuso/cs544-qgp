import struct
from pdu_constants import *

#importing the header class
from qgp_header import qgp_header

#defining class for a match starting
class qgp_game_start:
    # Fixed part of the payload format before the list count and list itself
    # match_id (I), match_type (I), match_duration (I), match_map (I),
    # match_mode (I), match_team (I), match_players (I)
    PAYLOAD_FIXED_PART_FORMAT = "!I I I I I I I"  # 7 unsigned ints
    PAYLOAD_FIXED_PART_SIZE = struct.calcsize(PAYLOAD_FIXED_PART_FORMAT)

    # Format for the length of the player_ids list
    PLAYER_ID_LIST_COUNT_FORMAT = "!I"  # An unsigned int for the count
    PLAYER_ID_LIST_COUNT_SIZE = struct.calcsize(PLAYER_ID_LIST_COUNT_FORMAT)

    PLAYER_ID_FORMAT = "!I"  # Each player ID is an unsigned int

    #defining the class variables
    def __init__(self, header, match_id, match_type, match_duration, match_map, match_mode, match_team, match_players, match_player_ids):
        self.header = header
        self.match_id = match_id
        self.match_type = match_type
        self.match_duration = match_duration
        self.match_map = match_map
        self.match_mode = match_mode
        self.match_team = match_team
        self.match_players = match_players
        self.match_player_ids = match_player_ids

    #defining the packing function
    def pack(self):
        #getting the length of the player id list
        len_player_list = len(self.match_player_ids)

        #packing the data without the list
        payload = struct.pack("!I I I I I I I", self.match_id, self.match_type, self.match_duration, self.match_map, self.match_mode, self.match_team, self.match_players)

        #packing the list
        payload += struct.pack("!I", len_player_list)
        int_format = "!" + (len_player_list * "I")

        payload += struct.pack(int_format, *self.match_player_ids)

        # Update header attributes before packing the header
        self.header.msg_len = qgp_header.SIZE + len(payload)  # Use header.message_length
        self.header.msg_type = QGP_MSG_GAME_START

        return self.header.pack() + payload

    #defining function to unpack
    @classmethod
    def unpack(cls, header_obj, payload_bytes):
        #if len(payload_bytes) < cls.PAYLOAD_FIXED_PART_SIZE:
         #   raise ValueError("Payload too short for qgp_game_start fixed part.")

        offset = 0

        # Unpack the fixed part of the payload
        match_id, match_type, match_duration, match_map, \
            match_mode, match_team, match_players = struct.unpack_from(
            cls.PAYLOAD_FIXED_PART_FORMAT, payload_bytes, offset
        )
        offset += cls.PAYLOAD_FIXED_PART_SIZE

        # Check if there's enough data for the player_id list count
        if len(payload_bytes) < offset + cls.PLAYER_ID_LIST_COUNT_SIZE:
            raise ValueError("Payload too short for player_id list count.")

        # Unpack the count of player_ids
        len_player_list, = struct.unpack_from(cls.PLAYER_ID_LIST_COUNT_FORMAT, payload_bytes, offset)
        offset += cls.PLAYER_ID_LIST_COUNT_SIZE

        # Unpack the player_ids themselves
        match_player_ids = []
        if len_player_list > 0:
            player_ids_bytes_expected = len_player_list * struct.calcsize(cls.PLAYER_ID_FORMAT)
            if len(payload_bytes) < offset + player_ids_bytes_expected:
                raise ValueError("Payload too short for the declared number of player_ids.")

            player_ids_format = "!" + (len_player_list * "I")  # Assuming each ID is 'I'
            unpacked_ids_tuple = struct.unpack_from(player_ids_format, payload_bytes, offset)
            match_player_ids = list(unpacked_ids_tuple)
            offset += player_ids_bytes_expected

        # Validate total length against header.message_length
        # header_obj.message_length is the total length (header + this specific payload)
        # qgp_header.SIZE is the size of the header
        # offset is the total size of THIS PDU's specific payload that we just parsed from payload_bytes
        if header_obj.msg_len != qgp_header.SIZE + offset:
            raise ValueError(
                f"Length mismatch in qgp_game_start. Header declared total: {header_obj.message_length}, "
                f"Expected total based on parsing current PDU payload: {qgp_header.SIZE + offset}"
            )

        return cls(header_obj, match_id, match_type, match_duration, match_map,
                   match_mode, match_team, match_players, match_player_ids)

#defining class for a match ending
#TODO: Finish this class
class qgp_game_end:
    # Fixed part of the payload format before the list count and list itself
    # match_id (I), match_type (I), match_duration (I), match_map (I),
    # match_mode (I), match_team (I), match_players (I)
    PAYLOAD_FIXED_PART_FORMAT = "!I I I I I I I"  # 7 unsigned ints
    PAYLOAD_FIXED_PART_SIZE = struct.calcsize(PAYLOAD_FIXED_PART_FORMAT)

    # Format for the length of the player_ids list
    PLAYER_ID_LIST_COUNT_FORMAT = "!I"  # An unsigned int for the count
    PLAYER_ID_LIST_COUNT_SIZE = struct.calcsize(PLAYER_ID_LIST_COUNT_FORMAT)

    PLAYER_ID_FORMAT = "!I"  # Each player ID is an unsigned int

    #defining the class variables
    def __init__(self, header, match_id, match_type, match_duration, match_map, match_mode, match_team, match_players, match_player_ids, match_player_kills, match_player_deaths, match_player_assists, match_player_teamkills, match_player_teamdeaths, match_player_teamassists):
        self.header = header
        self.match_id = match_id
        self.match_type = match_type
        self.match_duration = match_duration
        self.match_map = match_map
        self.match_mode = match_mode
        self.match_team = match_team
        self.match_players = match_players
        self.match_player_ids = match_player_ids
        self.match_player_kills = match_player_kills
        self.match_player_deaths = match_player_deaths
        self.match_player_assists = match_player_assists
        self.match_player_teamkills = match_player_teamkills
        self.match_player_teamdeaths = match_player_teamdeaths
        self.match_player_teamassists = match_player_teamassists

    #defining the packing function
    def pack(self):
        #getting the length of all lists
        len_player_list = len(self.match_player_ids)
        len_player_kills = len(self.match_player_kills)
        len_player_deaths = len(self.match_player_deaths)
        len_player_assists = len(self.match_player_assists)
        len_player_teamkills = len(self.match_player_teamkills)
        len_player_teamdeaths = len(self.match_player_teamdeaths)
        len_player_teamassists = len(self.match_player_teamassists)

        #packing the data without the list
        payload = struct.pack("!I I I I I I I", self.match_id, self.match_type, self.match_duration, self.match_map, self.match_mode, self.match_team, self.match_players)

        #packing the player id list
        payload += struct.pack("!I", len_player_list)
        payload += self.list_packer(len_player_list, self.match_player_ids)

        #packing the player kills list
        payload += struct.pack("!I", len_player_kills)
        payload += self.list_packer(len_player_kills, self.match_player_kills)

        #packing the players deaths list
        payload += struct.pack("!I", len_player_deaths)
        payload += self.list_packer(len_player_deaths, self.match_player_ids)

        #packing the player assists
        payload += struct.pack("!I", len_player_assists)
        payload += self.list_packer(len_player_assists, self.match_player_assists)

        #packing the player teamkills
        payload += struct.pack("!I", len_player_teamkills)
        payload += self.list_packer(len_player_teamkills, self.match_player_teamkills)

        #packing the player teamdeaths
        payload += struct.pack("!I", len_player_teamdeaths)
        payload += self.list_packer(len_player_teamdeaths, self.match_player_teamdeaths)

        #packing the player team assists
        payload += struct.pack("!I", len_player_teamassists)
        payload += self.list_packer(len_player_teamassists, self.match_player_teamassists)

        # Update header attributes before packing the header
        self.header.msg_len = qgp_header.SIZE + len(payload)  # Use header.message_length
        self.header.msg_type = QGP_MSG_GAME_START

        return self.header.pack() + payload

    #defining function to package the lists
    def list_packer(self, list_len, main_list):
        int_format = "!" + (list_len * "I")
        packer = struct.pack(int_format, *main_list)

        return packer

    #defining function to unpack
    @classmethod
    def unpack(cls, header_obj, payload_bytes):
        #if len(payload_bytes) < cls.PAYLOAD_FIXED_PART_SIZE:
         #   raise ValueError("Payload too short for qgp_game_start fixed part.")

        offset = 0

        # Unpack the fixed part of the payload
        match_id, match_type, match_duration, match_map, \
            match_mode, match_team, match_players = struct.unpack_from(
            cls.PAYLOAD_FIXED_PART_FORMAT, payload_bytes, offset
        )
        offset += cls.PAYLOAD_FIXED_PART_SIZE

        # Check if there's enough data for the player_id list count
        if len(payload_bytes) < offset + cls.PLAYER_ID_LIST_COUNT_SIZE:
            raise ValueError("Payload too short for player_id list count.")

        # Unpack the count of player_ids
        len_player_list, = struct.unpack_from(cls.PLAYER_ID_LIST_COUNT_FORMAT, payload_bytes, offset)
        offset += cls.PLAYER_ID_LIST_COUNT_SIZE

        # Unpack the player_ids themselves
        match_player_ids = []
        if len_player_list > 0:
            player_ids_bytes_expected = len_player_list * struct.calcsize(cls.PLAYER_ID_FORMAT)
            if len(payload_bytes) < offset + player_ids_bytes_expected:
                raise ValueError("Payload too short for the declared number of player_ids.")

            player_ids_format = "!" + (len_player_list * "I")  # Assuming each ID is 'I'
            unpacked_ids_tuple = struct.unpack_from(player_ids_format, payload_bytes, offset)
            match_player_ids = list(unpacked_ids_tuple)
            offset += player_ids_bytes_expected

        # Validate total length against header.message_length
        # header_obj.message_length is the total length (header + this specific payload)
        # qgp_header.SIZE is the size of the header
        # offset is the total size of THIS PDU's specific payload that we just parsed from payload_bytes
        if header_obj.msg_len != qgp_header.SIZE + offset:
            raise ValueError(
                f"Length mismatch in qgp_game_start. Header declared total: {header_obj.message_length}, "
                f"Expected total based on parsing current PDU payload: {qgp_header.SIZE + offset}"
            )

        return cls(header_obj, match_id, match_type, match_duration, match_map,
                   match_mode, match_team, match_players, match_player_ids)

#defining debug function
if __name__ == "__main__":
    ############################################################################
    # TESTING THE QGP START GAME
    ############################################################################
    # defining the text communication variables
    start_match_header = qgp_header(version=1, msg_type=0, msg_len=0, priority=0)
    start_match_id = 100
    start_match_type = 9000
    start_match_duration = 15
    start_match_map = 13289
    start_match_mode = 123
    start_match_team = 1
    start_match_players = 12
    start_match_player_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

    start_match_class = qgp_game_start(start_match_header, start_match_id, start_match_type, start_match_duration, start_match_map, start_match_mode, start_match_team, start_match_players, start_match_player_ids)

    # testing the packing
    start_match_packed = start_match_class.pack()
    print("start_match_packed", start_match_packed)

    # unpacking the header from the move hello
    start_match_headers, start_match_payload = qgp_header.unpack(start_match_packed)

    # testing the unpacking
    start_match_unpacked = start_match_class.unpack(start_match_headers, start_match_payload)
    print("move_unpacked", start_match_unpacked)
    print("header", move_unpacked.header)
    print("move player id", move_unpacked.player_id)
    print("move direction", move_unpacked.direction)
    print("move x", move_unpacked.x_position)
    print("move y", move_unpacked.y_position)
    print("move z", move_unpacked.z_position)
    print("move speed", move_unpacked.speed)
    print("move type", move_unpacked.movement_type)