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

## Required SSL Certs
QUIC by nature requires TLS 1.3 encryption which requires a certificate and a private key. These are available in the repo as  
- `test_cert.pem` for the certificate
- `test_private_key.pem` for the private key
  
A user can generate their own key and certificate pair by following the below steps:
1. Create a config file named **san.cnf**
2. Paste the below contents into that file
```
[ req ]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[ req_distinguished_name ]
CN = localhost

[ v3_req ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = localhost
IP.1 = 127.0.0.1
```
3. With that file created, the SSL certs can be generated with the below command:  
`openssl req -x509 -newkey rsa:2048 -keyout your_private_key.pem -out your_public_cert.pem -days 365 -nodes -config san.cnf -extensions v3_req`

## Running the files/testing
Each file in this project was designed with a `if __name__ == "__main__:` debug function at the bottom of it. These allow the individual PDUs to be tested to ensure they are packing and unpacking correctly without worrying about network corruption or other outside factors. 

## Running the server and client
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
Arguments in order: `match_id match_type match_duration match_map match_mode match_team match_players match_player_ids, match_player_kills, match_player_deaths, match_player_assists, match_player_teamkills, match_player_teamdeaths, match_player_teamassists`
Data types:
- match_id = integer
- match_type = integer
- match_duration = integer
- match_map = integer
- match_mode = integer
- match_team = integer
- match_players = integer
- match_player_ids = list of integers
- match_player_kills = list of integers
- match_player_deaths = list of integers
- match_player_assists = list of integers
- match_player_teamkills = list of integers
- match_player_teamdeaths = list of integers
- match_player_teamassists = list of integers

**Special Note:** The commas between the lists are needed as a delimiter between the lists. No other parameter should have commas between them
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

# Reflection Summary
While working on this project I vastly underestimated how easy it would be to complete. The libraries of async and aioquic definitely  
helped in rapidly deploying this project, there were still plenty of challenges faces. Of course even with challenges I saw this project  
as a huge success. Not only did I start building my own network protocol, it taught me value lessons along the way

## Challenges
1. When packing the data into a byte serialization, the contents would be mis-aligned if the correct data type wasn't picked. This was my first time using the **struct** library so it was definitely a learning curve on that front
2. Creating the packed payloads and headers in isolation was easy however putting the two together was difficult at first. This again was partly due to not working with struct objects before but another being forgetting the endianess of the data
3. The ports selected we're blocked on my localhost firewall which was initally mis-diagnosed as a python configuration error. However after more debugging, it was actually the system firewall blocking those ports. Once they were changed to go in the 5000 range the issue was not longer present

## Postitives and Lessons learned
1. Instead of hitting the ground running with a massive task, its best to start small. Initially I tried to deploy the full DFA since I was overconfident in my abilities. However this was a mistake as there were errors upon errors. Instead doing it one small step at a time allowed the errors to be hunted down one by one and allowing the program to expand
2. Getting hands on with the **aioquic** library. This library makes working with QUIC a lot easier and has inspired me to further explore it to see if I can make a custom web-messenger for my friends
3. Working with async routines. I've worked with async and threaded programs in the past but they did not have an interactable command line. This was my first experience having a CLI in an async environment which was fun to deploy and see how powerful it is

## Final words on the project
Overall this project was a great experience. It taught me how to think differently from the software I usually write and to accommodate for more edge cases. My normal software is non-interactable in the sense of a user talks to it via an API and it does stuff. With this, the CLI is the API which needed to be built in order for the user to use the software and not have to wait for the server/client to not be busy processing something else. I do plan to continue working on this protocol as it shows promise where high speed communication is critical or for games that do not need a lot of clunky overhead if its a simple mobile game. Of course the biggest challenge of continuing this protocol is making sure its adopted widely and the middlewear boxes don't block it on the internet :D 