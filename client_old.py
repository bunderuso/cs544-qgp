import asyncio, threading
import logging
from typing import Optional, Set

from aioquic.asyncio import QuicConnectionProtocol, connect
from aioquic.quic import events
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import QuicEvent, StreamDataReceived, HandshakeCompleted, ConnectionTerminated

from cli_funcs.cli_cmds import *

from qgp.pdu_constants import *
from qgp.qgp_communication import qgp_text_chat
from qgp.qgp_hello import qgp_client_hello, qgp_server_hello
from qgp.qgp_header import qgp_header
from qgp.qgp_errors import qgp_errors

#tracking the connected clients
ACTIVE_CLIENTS: Set[QuicConnectionProtocol] = set()

#defining the DFA class
class client_dfa_state:
    INITIAL = 0
    QUIC_CONNECTING = 1
    AWAITING_SERVER_HELLO = 2
    HANDSHAKE_COMPLETED = 3
    TERMINATING = 4
    IN_GAME = 5
    GAME_OVER = 6
    IDLE = 7

#defining the client class for QUIC
class qgp_client_protocol(QuicConnectionProtocol):
    #defining the class variables
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_dfa_state = client_dfa_state.INITIAL
        self._client_hello_sent_on_stream: Optional[int] = None

    def connection_made(self, transport):
        super().connection_made(transport)

        peername = transport.get_extra_info('peername')
        if peername:
            self.resolved_peer_address = peername
            print(f"[Server] New connection from: {self.resolved_peer_address}")
        else:
            self.resolved_peer_address = None  # Should ideally not happen
            print("[Server] New connection, but peer address not available from transport.")

        ACTIVE_CLIENTS.add(self)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        # Use the stored resolved_peer_address for logging if available
        peer_display = self.resolved_peer_address if self.resolved_peer_address else "Unknown Peer"
        print(f"[Server] Connection lost from: {peer_display}")
        ACTIVE_CLIENTS.discard(self)

    #defining the function to handle quic connections
    def quic_event_received(self, event: events.QuicEvent):
        print("received event", event)
        if isinstance(event, HandshakeCompleted):
            print("handshake completed")
            #checking the DFA status only if its the initial state
            if self.current_dfa_state == client_dfa_state.INITIAL:
                self.current_dfa_state = client_dfa_state.QUIC_CONNECTING

            if self.current_dfa_state == client_dfa_state.QUIC_CONNECTING:
                self.send_qgp_client_hello()

        elif isinstance(event, StreamDataReceived):
            #getting the stream id and the data
            stream_id = event.stream_id
            data = event.data

            #unpacking the headers
            headers = None
            payload = None
            headers, payload = qgp_header.unpack(data)

            #errors can happen in any state so error check is located outside of DFA checks
            if headers.msg_type == QGP_MSG_SERVER_ERROR:
                print("Error received")
                error = qgp_errors.unpack(headers, payload)

                print("Error code:", error.error_code)
                print("Error length:", error.error_length)
                print("Error message:", error.error_message)
                print("Error severity:", error.severity)
            else:

                #checking the DFA status
                if self.current_dfa_state == client_dfa_state.AWAITING_SERVER_HELLO:
                    #checking the message type
                    if headers.msg_type == QGP_MSG_SERVER_HELLO:
                        print("message len", headers.msg_len)
                        server_hello = qgp_server_hello.unpack(headers, payload)

                        print("Received server hello")
                        print("server id:", server_hello.server_id)
                        print("server version", server_hello.server_software_version)
                        print("server capabilities:", server_hello.capabilities_str)

                        #updating the DFA
                        self.current_dfa_state = client_dfa_state.HANDSHAKE_COMPLETED

                    else:
                        print("Invalid message, closing connection")
                        self.close()

                #this can happen after the initial connection or the client is out of the game
                elif self.current_dfa_state == client_dfa_state.HANDSHAKE_COMPLETED or self.current_dfa_state == client_dfa_state.GAME_OVER:
                    #checking the message type
                    if headers.msg_type == QGP_MSG_GAME_START:
                        print("Game start message received")
                        game_start = qgp_game_start.unpack(headers, payload)

                        #printing the details of the payload
                        print(f"[INFO] Match ID: {game_start.match_id}")
                        print(f"[INFO] Match Type: {game_start.match_type}")
                        print(f"[INFO] Match Duration: {game_start.match_duration}")
                        print(f"[INFO] Match Map: {game_start.match_map}")
                        print(f"[INFO] Match Mode: {game_start.match_mode}")
                        print(f"[INFO] Match Team: {game_start.match_team}")
                        print(f"[INFO] Match Players: {game_start.match_players}")
                        print(f"[INFO] Match Player IDs: {game_start.match_player_ids}")

                        #updating the client dfa
                        self.current_dfa_state = client_dfa_state.IN_GAME

                    else:
                        print("Server sent a packet outside of valid headers")
                        print("Sending a client error")
                        args = ["6", "0", "Client sent a packet outside of valid headers"]
                        packaged_pdu = server_error_sender(args)
                        # checking a pdu package was returned and if so sending it
                        if packaged_pdu is None:
                            print("Invalid arguments provided")
                        else:
                            sender(packaged_pdu)



                elif self.current_dfa_state == client_dfa_state.IN_GAME:
                    #checking the message type
                    if headers.msg_type == QGP_MSG_TEXT_CHAT:
                        print("Chat message received")
                        server_chat = qgp_text_chat.unpack(headers, payload)

                        print("Received server chat message:", server_chat.text)
                    elif headers.msg_type == QGP_MSG_GAME_END:
                        print("Game end message received")
                        game_end = qgp_game_end.unpack(headers, payload)

                        # printing the details of the payload
                        print(f"[INFO] Match ID: {game_end.match_id}")
                        print(f"[INFO] Match Type: {game_end.match_type}")
                        print(f"[INFO] Match Duration: {game_end.match_duration}")
                        print(f"[INFO] Match Map: {game_end.match_map}")
                        print(f"[INFO] Match Mode: {game_end.match_mode}")
                        print(f"[INFO] Match Team: {game_end.match_team}")
                        print(f"[INFO] Match Players: {game_end.match_players}")
                        print(f"[INFO] Match Player IDs: {game_end.match_player_ids}")
                        print(f"[INFO] Match Player Kills: {game_end.match_player_kills}")
                        print(f"[INFO] Match Player Deaths: {game_end.match_player_deaths}")
                        print(f"[INFO] Match Player Assists: {game_end.match_player_assists}")
                        print(f"[INFO] Match Player TeamKills: {game_end.match_player_teamkills}")
                        print(f"[INFO] Match Player TeamDeaths: {game_end.match_player_teamdeaths}")
                        print(f"[INFO] Match Player TeamAssists: {game_end.match_player_teamassists}")

                        #changing the dfa status
                        self.current_dfa_state = client_dfa_state.GAME_OVER
                    else:
                        print("Server sent a packet outside of valid headers")
                        print("Sending a client error")
                        args = ["6", "0", "Client sent a packet outside of valid headers"]
                        packaged_pdu = server_error_sender(args)
                        # checking a pdu package was returned and if so sending it
                        if packaged_pdu is None:
                            print("Invalid arguments provided")
                        else:
                            sender(packaged_pdu)

                else:
                    print("Server sent a packet outside of next expected state")
                    print("Sending a client error")
                    args = ["7", "0", "Received packet outside of next expected state"]
                    packaged_pdu = client_error_sender(args)
                    # checking a pdu package was returned and if so sending it
                    if packaged_pdu is None:
                        print("Invalid arguments provided")
                    else:
                        sender(packaged_pdu)

    def send_qgp_client_hello(self):
        stream_id = 0
        self._client_hello_sent_on_stream = stream_id

        header = qgp_header(version=1, msg_type=QGP_MSG_CLIENT_HELLO, msg_len=0, priority=0)
        client_hello_payload = qgp_client_hello(header=header, client_id=1, client_version=1, capabilities="test_env")
        packed = client_hello_payload.pack()
        self._quic.send_stream_data(stream_id, packed, end_stream=False)
        self.current_dfa_state = client_dfa_state.AWAITING_SERVER_HELLO
        print("client hello sent")

    async def send_qgp_pdu(self, pdu_instance, stream_id_to_use: Optional[int] = None, end_stream=False):
        """Helper method to pack and send a QGP PDU."""
        peer_display = self.resolved_peer_address if self.resolved_peer_address else "Peer"

        # packed_pdu = pdu_instance.pack()
        packed_pdu = pdu_instance

        if stream_id_to_use is None:
            stream_id = self._quic.get_next_available_stream_id(
                is_unidirectional=False)  # Or True for one-way broadcast
        else:
            stream_id = stream_id_to_use
        print("Stream id", stream_id)

        # pdu_type_to_log = pdu_instance.header.msg_type if hasattr(pdu_instance, 'header') else 'UnknownType'

        # print(
        #    f"[Server] Sending PDU type {pdu_type_to_log} ({len(packed_pdu)} bytes) to {peer_display} on stream {stream_id}")
        self._quic.send_stream_data(stream_id, packed_pdu, end_stream=True)
        self.transmit()
        print("Sent response")

# --- CLI Handling ---
async def process_commands(command_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    print("[Server CLI Processor] Ready for commands.")
    while True:

        command_line_input = await command_queue.get()
        if command_line_input is None:  # Sentinel for shutdown
            print("[Server CLI Processor] Shutdown signal received.")
            break

        command_parts = command_line_input.split()
        if not command_parts:
            command_queue.task_done()
            continue

        cmd = command_parts[0].lower()
        args = command_parts[1:]

        print(f"[Server CLI Processor] Processing command: '{cmd}' with args {args}")

        if cmd == "broadcast_chat":
            if args:
                message_text = " ".join(args)
                print(f"[Server CLI] Broadcasting chat: '{message_text}'")
                chat_header = qgp_header(
                    version=1,
                    msg_type=0,
                    msg_len=0,
                    priority=1
                )
                chat_pdu = qgp_text_chat(chat_header, text_length=len(message_text), text=message_text)

                clients_to_send_snapshot = list(ACTIVE_CLIENTS)
                if not clients_to_send_snapshot:
                    print("[Server CLI] No active clients to broadcast to.")
                for client_protocol in clients_to_send_snapshot:
                    if hasattr(client_protocol, 'send_qgp_pdu') and client_protocol._quic is not None:
                        # Use asyncio.create_task for safety from within another coroutine
                        asyncio.create_task(client_protocol.send_qgp_pdu(chat_pdu, stream_id_to_use=None))
                    else:
                        peer_addr_display = client_protocol.resolved_peer_address if hasattr(client_protocol,
                                                                                             'resolved_peer_address') and client_protocol.resolved_peer_address else "Unknown Client"
                        print(
                            f"[Server CLI] Cannot send to client {peer_addr_display}: missing send_qgp_pdu or not fully connected.")
            else:
                print("[Server CLI] Usage: broadcast_chat <message>")

        # sending the error command
        elif cmd == "send_error":
            packaged_pdu = client_error_sender(args)

            # checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)
        # sending the chat command
        elif cmd == "chat":
            packaged_pdu = client_chat(args)

            # checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)

        # sending the player_move command
        elif cmd == "player_move":
            packaged_pdu = move_player(args)

            # checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)

        # sending the player_join command
        elif cmd == "player_join":
            packaged_pdu = player_join(args)

            # checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)

        # sending the player_leave command
        elif cmd == "player_leave":
            packaged_pdu = player_leave(args)

            # checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)

        # sending the player_leave command
        elif cmd == "player_status":
            packaged_pdu = player_status(args)

            # checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)


        elif cmd == "list_clients":
            if not ACTIVE_CLIENTS:
                print("[Server CLI] No clients currently connected.")
            else:
                print("[Server CLI] Active clients:")
                for i, client_proto_instance in enumerate(ACTIVE_CLIENTS):
                    peer_addr_display = client_proto_instance.resolved_peer_address if hasattr(
                        client_proto_instance,
                        'resolved_peer_address') and client_proto_instance.resolved_peer_address else "Address N/A"
                    client_qgp_id_display = client_proto_instance.client_qgp_id if hasattr(client_proto_instance,
                                                                                           'client_qgp_id') and client_proto_instance.client_qgp_id else "QGP_ID N/A"
                    print(f"  {i + 1}. {peer_addr_display} (QGP ID: {client_qgp_id_display})")

        elif cmd == "exit" or cmd == "quit":
            print("[Server CLI] Exit command received from CLI. Signalling server shutdown...")
            # Signal all tasks to cancel, including the server listener if possible
            current_task = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not current_task]
            for task in tasks:
                task.cancel()
            await command_queue.put(None)  # Ensure this processor exits its loop
            break
        else:
            print(f"[Server CLI] Unknown command: {cmd}")

        command_queue.task_done()

def cli_input_loop(loop: asyncio.AbstractEventLoop, command_queue: asyncio.Queue):
    print("\n[Server CLI] Type 'broadcast_chat <message>', 'list_clients', or 'exit'.")
    try:
        while True:
            command_line = input("QGP Server> ")  # This is blocking
            if not command_line:  # Handle empty input
                continue
            if loop.is_closed():
                print("[Server CLI] Event loop closed, exiting CLI input.")
                break

            if command_line.lower() in ["exit", "quit"]:
                # Signal the processor to stop, and then this thread will exit
                asyncio.run_coroutine_threadsafe(command_queue.put(None), loop)
                break
            asyncio.run_coroutine_threadsafe(command_queue.put(command_line), loop)
    except EOFError:
        print("[Server CLI] EOF received, signalling exit.")
        if not loop.is_closed():
            asyncio.run_coroutine_threadsafe(command_queue.put(None), loop)
    except KeyboardInterrupt:
        print("[Server CLI] KeyboardInterrupt in CLI, signalling exit.")
        if not loop.is_closed():
            asyncio.run_coroutine_threadsafe(command_queue.put(None), loop)
    except Exception as e:
        print(f"[Server CLI] Error in input loop: {e}")
        if not loop.is_closed():
            asyncio.run_coroutine_threadsafe(command_queue.put(None), loop)  # Try to signal exit
    finally:
        print("[Server CLI] Input loop ended.")

# defining function to send the package pdu
def sender(packaged_pdu):
    # getting the active clients
    clients_to_send_snapshot = list(ACTIVE_CLIENTS)
    if not clients_to_send_snapshot:
        print("[Server CLI] No active clients to broadcast to.")

    # looping through the active clients and sending the error
    print(clients_to_send_snapshot)
    for client_protocol in clients_to_send_snapshot:
        if hasattr(client_protocol, 'send_qgp_pdu') and client_protocol._quic is not None:
            # Use asyncio.create_task for safety from within another coroutine
            asyncio.create_task(client_protocol.send_qgp_pdu(packaged_pdu, stream_id_to_use=None))
        else:
            peer_addr_display = client_protocol.resolved_peer_address if hasattr(client_protocol,
                                                                                 'resolved_peer_address') and client_protocol.resolved_peer_address else "Unknown Client"
            print(
                f"[Server CLI] Cannot send to client {peer_addr_display}: missing send_qgp_pdu or not fully connected.")

#defining the main function
async def main():
    config = QuicConfiguration(
        alpn_protocols=QGP_ALPN,
        is_client=True,
    )

    #loading the ssl cert
    config.load_verify_locations(cafile="test_cert.pem")

    async with connect(configuration = config,
                              port = QGP_PORT,
                              host = QGP_HOST,
                              create_protocol=qgp_client_protocol) as connection:
        connection.client_dfa_state = client_dfa_state.QUIC_CONNECTING

        while connection.current_dfa_state != client_dfa_state.TERMINATING:
            if not connection._quic:
                print("[Client] Connection appears closed in main loop. Exiting.")
                connection.current_dfa_state = client_dfa_state.TERMINATING
                break
            await asyncio.sleep(1)

        #await asyncio.sleep(100)
        print("Client connected")

async def main_with_cli():
    config = QuicConfiguration(
        alpn_protocols=QGP_ALPN,
        is_client=True,
    )
    config.load_verify_locations(cafile="test_cert.pem")
    config.idle_timeout = 1200

    command_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    cli_thread = threading.Thread(target=cli_input_loop, args=(loop, command_queue), daemon=True)
    cli_thread.start()

    async with connect(configuration=config,
                       port=QGP_PORT,
                       host=QGP_HOST,
                       create_protocol=qgp_client_protocol) as connection:

        connection.client_dfa_state = client_dfa_state.QUIC_CONNECTING

        command_task = asyncio.create_task(process_commands(command_queue, connection))

        while connection.current_dfa_state != client_dfa_state.TERMINATING:
            if not connection._quic:
                connection.current_dfa_state = client_dfa_state.TERMINATING
                break
            await asyncio.sleep(1)

        await command_task

#defining the debug function
if __name__ == '__main__':
    #asyncio.run(main())
    asyncio.run(main_with_cli())