# cs544-qgp
This is the repo for the Quic Gaming Protocol (QGP)

# Description
This is the first version of the QGP built in Python 3. Currently it is a small tech-demo with a single client and server   
to exchange messages in a controlled fashion. The goal of it is to show how QUIC could be used to send efficient  
messages in a multiplayer gaming context.  
  
All of the messages were intended to use integers whereever possible as they are more efficient to send and allow for easier  
process than strings. Strings are currently only used for actual messages for errors or text chats.

# How to run
## Language version
Python 3

## Required libraries
1. threading
2. logging
3. struct
4. aioquic
5. asyncio
6. typing

## Running the files
1. Execute the command `python3 server.py` before starting the client. The server must be running first
2. Execute the command `python3 client.py` after starting the server. The server must be running first

# Server CLI Commands
## send_error
Command: `send_error`  
Arguments in order:  `error_code severity message`  
Example: `send_error 34 1 client has disconnected`  
Data types:
- error_code = integer
- severity = integer
- message = string

## chat
Command: `chat`  
Arguments in order: `message`  
Example: `chat i love pizza`   
Data types:  
- message = string

## start_game  
Command: `start_game`  
Arguments in order: `match_id match_type match_duration match_map match_mode match_team match_player match_player_ids`
Example: `start_game 1 34 1500 151 0 2 10 1 2 3 4 5 6 7 8 9 10`  
Data types:  
- match_id = integer
- match_type = integer
- match_duration = integer
- match_map = integer
- match_mode = integer
- match_team = integer
- match_players = integer
- match_player_ids = list of integers
  
## end_game  FINISH ME
Command: `end_game`

# Client CLI Commands
## send_error
Command: `send_error`  
Arguments in order:  `error_code severity message`  
Example: `send_error 34 1 client has disconnected`  
Data types:
- error_code = integer
- severity = integer
- message = string

## chat
Command: `chat`  
Arguments in order: `message`  
Example: `chat i love pizza`   
Data types:  
- message = string

## player_move
Command: `player_move`  
Arguments in order: `player_id move_type direction x_position y_position z_position speed`  
Example: `player_move 1 90 4 50 34 8 2`  
Data types:
- player_id = integer
- move_type = integer
- direction = integer
- x_position = integer
- y_position = integer
- z_position = integer
- speed = integer

## player_status
Command: `player_status`  
Arguments in order: `player_id player_health player_damage_received`  
Example: `player_statue 1 51 49`  
Data types:
- player_id = integer
- player_health = integer
- player_damage_received = integer

## player_join
Command: `player_join`  
Arguments in order: `player_id match_id match_team`  
Example: `player_join 1 56 2`  
Data types:
- player_id = integer
- match_id = integer
- match_team = integer

## player_leave
Command: `player_leave`  
Arguments in order: `player_id match_id match_team`  
Example: `player_leave 1 56 2`  
Data types:
- player_id = integer
- match_id = integer
- match_team = integer