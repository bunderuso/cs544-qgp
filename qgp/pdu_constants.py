#defining the message types
QGP_MSG_SERVER_HELLO = 0x0001
QGP_MSG_CLIENT_HELLO = 0x0002
QGP_MSG_AUTH_REQ = 0x0003
QGP_MSG_AUTH_RES = 0x0004
QGP_MSG_Q_REQ = 0x0010 
QGP_MSG_Q_RES = 0x0011 
QGP_MSG_MATCH = 0x0012 
QGP_MSG_LD_MATCH_START = 0x0013 
QGP_MSG_LD_MATCH_END = 0x0014 
QGP_MSG_GAME_START = 0x0015 
QGP_MSG_GAME_END = 0x0016 
QGP_MSG_PLAYER_JOIN = 0x0017 
QGP_MSG_PLAYER_LEAVE =0x0018 
QGP_MSG_OWN_PLAYER_LEAVE =0x0019
QGP_MSG_PLAYER_STATUS = 0x001A
QGP_MSG_TEXT_CHAT = 0x0020 
QGP_MSG_VOICE_CHAT = 0x0021 
QGP_MSG_PLAYER_MOVEMENT = 0x0100 
QGP_MSG_PLAYER_ACTION = 0x0101 
QGP_MSG_SERVER_ERROR = 0x0200 
QGP_MSG_CLIENT_ERROR = 0x0201 
QGP_MSG_LATENCY_WARN = 0x0202 
QGP_MSG_PACKETDRP_WARN = 0x0203 
QGP_MSG_NAT_WARN = 0x0204 
QGP_MSG_ANTICHEAT_WARN = 0x0205 
QGP_MSG_UNKNOWN_ERROR = 0x0206

#Control constants
QGP_VERSION = 1
QGP_ALPN = ['qgp/1.0']

#defining the connection constants
QGP_HOST = "localhost"
QGP_PORT = 5544

# --- DFA State Enumerations ---
class ClientDFAState:
    INITIAL = 0
    QUIC_CONNECTING = 1
    AWAITING_SERVER_HELLO = 2
    AWAITING_AUTH_RESULT = 3 # If server drives auth after hello
    # Or: SENDING_AUTH_SUBMIT = 3 # If client drives auth after hello
    IDLE_CONNECTED = 4 # Handshake & Auth complete
    IN_QUEUE = 5
    MATCH_FOUND_AWAIT_LOAD = 6
    LOADING_MAP = 7
    IN_GAME = 8
    GAME_OVER = 9
    TERMINATING = 10

class ServerClientDFAState: # Server's perspective for each connected client
    AWAITING_CLIENT_HELLO = 1
    AWAITING_CLIENT_AUTH = 2 # If server sent ServerHello indicating auth needed
    # Or: PROCESSING_CLIENT_AUTH = 2 # If client sent auth data with/after hello
    CLIENT_CONNECTED_IDLE = 3 # Handshake & Auth complete
    CLIENT_IN_QUEUE = 4
    CLIENT_LOADING_MAP = 5 # Match formed, client is loading
    CLIENT_IN_GAME = 6
    CLIENT_GAME_ENDING = 7 # Game over for this client's match
    CLIENT_TERMINATING = 8