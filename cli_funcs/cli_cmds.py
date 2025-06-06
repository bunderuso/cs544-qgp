from qgp.qgp_header import qgp_header
from qgp.qgp_errors import qgp_errors
from qgp.qgp_communication import qgp_text_chat
from qgp.pdu_constants import *
from qgp.qgp_player import qgp_player_movement, qgp_player_status, qgp_player_join, qgp_player_leave
from qgp.qgp_session_mgmt import qgp_game_start


#defining the function to send an error
def error_sender(args):
    #checking the correct number of args were sent, if not returning None
    if args and len(args) >= 3:
        #moving the args to their respective variables
        error_code = int(args[0])
        error_message = " ".join(args[2:])
        error_severity = int(args[1])
        error_length = len(error_message)

        print(f"[ERROR] {error_code}: {error_message}")
        print(f"[ERROR] {error_severity}: {error_length}")

        #creating the error package
        chat_header = qgp_header(
            version=1,
            msg_type=QGP_MSG_SERVER_ERROR,
            msg_len=0,
            priority=1
        )
        error_pdu = qgp_errors(chat_header, error_code, error_length, error_severity, error_message)
        error_pdu_packed = error_pdu.pack()

        #returning the error package
        return error_pdu_packed

    else:
        return None

#defining function to send chats to the client
def client_chat(args):
    #checking the correct number of args are present
    if args and len(args) >= 1:
        #moving the args to the correct varaibles
        text_message = " ".join(args[0:])
        text_length = len(text_message)

        print(f"[INFO] {text_message}")

        #creating the headers for the package
        chat_header = qgp_header(
            version=1,
            msg_type=QGP_MSG_TEXT_CHAT,
            msg_len=0,
            priority=1
        )

        #packing the content and returning
        chat_pdu = qgp_text_chat(chat_header, text_length, text_message)
        chat_pdu_packed = chat_pdu.pack()
        return chat_pdu_packed
    else:
        return None

#defining function to start the game
def start_game(args):
    #checking the correct number of args are present
    if args and len(args) >= 8:
        #assigning each parameter to its variable
        match_id = int(args[0])
        match_type = int(args[1])
        match_duration = int(args[2])
        match_map = int(args[3])
        match_mode = int(args[4])
        match_team = int(args[5])
        match_player = int(args[6])
        match_player_ids = " ".join(args[7:])
        match_player_ids = match_player_ids.split(" ")

        #converting each player id to an interger
        for i in range(len(match_player_ids)):
            match_player_ids[i] = int(match_player_ids[i])

        #debug prints
        print(f"[INFO] {match_id}: {match_type}")
        print(f"[INFO] {match_type}: {match_duration}")
        print(f"[INFO] {match_type}: {match_map}")
        print(f"[INFO] {match_type}: {match_mode}")
        print(f"[INFO] {match_type}: {match_team}")
        print(f"[INFO] {match_type}: {match_player}")
        print(f"[INFO] {match_type}: {match_player_ids}")

        #creating the headers
        start_game_header = qgp_header(
            version=1,
            msg_type=QGP_MSG_GAME_START,
            msg_len=0,
            priority=0
        )

        #creating the payload and packaging
        start_game_pdu = qgp_game_start(header=start_game_header, match_id=match_id, match_type=match_type,
                                        match_duration=match_duration, match_players=match_player, match_mode=match_mode,
                                        match_team=match_team, match_player_ids=match_player_ids, match_map=match_map)
        start_game_pdu_packed = start_game_pdu.pack()

        return start_game_pdu_packed
    else:
        return None

#defining the function to end a match
#TODO: FINISH ME
# def end_game(args):
#    if args and len(args) >= 1:

#defining the function to move the player
def move_player(args):
    #making sure the correct num of args are present
    if args and len(args) >= 7:
        #assigning each arg to its varaible
        player_id = int(args[0])
        movement_type = int(args[1])
        direction = int(args[2])
        x_position = int(args[3])
        y_position = int(args[4])
        z_position = int(args[5])
        speed = int(args[6])

        #creating the headers
        move_header = qgp_header(
            version=1,
            msg_type=QGP_MSG_PLAYER_MOVEMENT,
            msg_len=0,
            priority=0
        )

        #creating the package and returning
        move_pdu = qgp_player_movement(
            header=move_header,
            player_id=player_id,
            movement_type=movement_type,
            direction=direction,
            x_position=x_position,
            y_position=y_position,
            z_position=z_position,
            speed=speed
        )
        move_pdu_packed = move_pdu.pack()

        return move_pdu_packed
    else:
        return None

#defining the function to send the player status of health and damage taken
def player_status(args):
    #checking the correct number of args were sent
    if args and len(args) >= 3:
        #assigning each arg to a variable
        player_id = int(args[0])
        player_health = int(args[1])
        player_dmg_taken = int(args[2])

        #defining the header
        status_header = qgp_header(
            version=1,
            msg_type=QGP_MSG_PLAYER_STATUS,
            msg_len=0,
            priority=0
        )

        #packing and returning the packed struct
        status_pdu = qgp_player_status(header=status_header, player_id=player_id, player_health=player_health, player_dmg_taken=player_dmg_taken)
        status_pdu_packed = status_pdu.pack()

        return status_pdu_packed
    else:
        return None

#defining the function for players joining
def player_join(args):
    #making sure the correct number of args are present
    if args and len(args) >= 3:
        #saving each arg to its variable
        player_id = int(args[0])
        match_id = int(args[1])
        player_team = int(args[2])

        #creating the headers
        join_header = qgp_header(
            version=1,
            msg_type=QGP_MSG_PLAYER_JOIN,
            msg_len=0,
            priority=0
        )

        #packing and returning the package
        join_pdu = qgp_player_join(
            header=join_header,
            player_id=player_id,
            match_id=match_id,
            player_team=player_team
        )
        join_pdu_packed = join_pdu.pack()

        return join_pdu_packed
    else:
        return None

#defining the function for player leaving
def player_leave(args):
    if args and len(args) >= 3:
        # saving each arg to its variable
        player_id = int(args[0])
        match_id = int(args[1])
        player_team = int(args[2])

        # creating the headers
        leave_header = qgp_header(
            version=1,
            msg_type=QGP_MSG_PLAYER_JOIN,
            msg_len=0,
            priority=0
        )

        # packing and returning the package
        leave_pdu = qgp_player_leave(
            header=leave_header,
            player_id=player_id,
            match_id=match_id,
            player_team=player_team
        )
        leave_pdu_packed = leave_pdu.pack()

        return leave_pdu_packed
    else:
        return None