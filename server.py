import asyncio
import logging
import threading
from typing import Dict, Optional, Set, Tuple

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, HandshakeCompleted, ConnectionTerminated

# QGP Package imports
from qgp.pdu_constants import *
from qgp.qgp_header import qgp_header
from qgp.qgp_hello import qgp_client_hello, qgp_server_hello
from qgp.qgp_communication import qgp_text_chat
from qgp.qgp_player import qgp_player_movement  # Add qgp_player_action if used
from qgp.qgp_session_mgmt import qgp_game_start, qgp_game_end  # Add others as needed
from qgp.qgp_errors import qgp_errors

ACTIVE_CLIENTS: Set[QuicConnectionProtocol] = set()
NEXT_CLIENT_QGP_ID = 1001  # Simple way to assign unique QGP IDs to clients


class QGPServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_dfa_state = ServerClientDFAState.AWAITING_CLIENT_HELLO
        self.resolved_peer_address: Optional[Tuple[str, int]] = None
        self.client_qgp_id: Optional[int] = None  # QGP-level identifier for the client
        self.client_sw_version: Optional[int] = None
        self.client_capabilities: Optional[str] = None
        self.current_match_id: Optional[int] = None  # If the client is in a match
        self.stream_buffers: Dict[int, bytes] = {}

    def connection_made(self, transport):
        super().connection_made(transport)
        peername = transport.get_extra_info('peername')
        self.resolved_peer_address = peername if peername else ("Unknown", 0)
        print(f"[Server] New connection from: {self.resolved_peer_address}")
        ACTIVE_CLIENTS.add(self)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        print(f"[Server] Connection lost from: {self.resolved_peer_address} (QGP ID: {self.client_qgp_id})")
        ACTIVE_CLIENTS.discard(self)
        # If in a match, notify other players
        if self.current_match_id and self.client_qgp_id:
            # This requires a way to find other clients in the same match_id
            # For simplicity here, broadcast to all, game logic would filter
            print(f"[Server] Broadcasting player {self.client_qgp_id} left match {self.current_match_id}")

            #TODO: FIX THIS
            # leave_header = qgp_header(QGP_VERSION, QGP_MSG_PLAYER_LEAVE_NOTIFY, 0, 1)
            # leave_pdu = qgp_player_leave_notify(leave_header, self.client_qgp_id, 0)  # Reason 0 = generic disconnect
            # broadcast_pdu_to_active_clients(leave_pdu, exclude_self=self)

    def process_stream_buffer(self, stream_id: int):
        buffer = self.stream_buffers.get(stream_id, b'')
        peer_display = self.resolved_peer_address

        processing_possible = True
        while processing_possible and len(buffer) >= qgp_header.SIZE:
            try:
                temp_header_for_len, _ = qgp_header.unpack(buffer)
                expected_total_pdu_len = temp_header_for_len.message_length

                if len(buffer) >= expected_total_pdu_len:
                    full_pdu_bytes = buffer[:expected_total_pdu_len]
                    buffer = buffer[expected_total_pdu_len:]
                    self.stream_buffers[stream_id] = buffer

                    header_obj, payload_bytes = qgp_header.unpack(full_pdu_bytes)
                    print(
                        f"[Server] Processing PDU from {peer_display} (QGP ID: {self.client_qgp_id}): Type={header_obj.msg_type}, Len={header_obj.message_length}")
                    self.handle_qgp_pdu(header_obj, payload_bytes, stream_id)
                else:
                    processing_possible = False  # Wait for more data
            except ValueError as e:
                print(
                    f"[Server] PDU unpack error from {peer_display} (QGP ID: {self.client_qgp_id}): {e}. Clearing stream buffer.")
                self.stream_buffers[stream_id] = b''
                processing_possible = False
            except Exception as e:
                print(
                    f"[Server] Unexpected error processing buffer for {peer_display} (QGP ID: {self.client_qgp_id}): {e}")
                self.stream_buffers[stream_id] = b''
                processing_possible = False

    def handle_qgp_pdu(self, header_obj: qgp_header, payload_bytes: bytes, stream_id: int):
        """Main QGP PDU handling logic based on DFA state."""
        peer_display = self.resolved_peer_address
        global NEXT_CLIENT_QGP_ID

        if self.current_dfa_state == ServerClientDFAState.AWAITING_CLIENT_HELLO:
            if header_obj.msg_type == QGP_MSG_CLIENT_HELLO:
                client_hello = qgp_client_hello.unpack(header_obj, payload_bytes)
                self.client_qgp_id = client_hello.client_id  # Or assign a new one: NEXT_CLIENT_QGP_ID; NEXT_CLIENT_QGP_ID += 1
                self.client_sw_version = client_hello.client_version
                self.client_capabilities = client_hello.capabilities
                print(
                    f"[Server] ClientHello from {peer_display}: QGP_ID={self.client_qgp_id}, SWVer={self.client_sw_version}, Caps='{self.client_capabilities}'")

                # Respond with ServerHello
                resp_header = qgp_header(QGP_VERSION, 0, 0, header_obj.priority)
                server_hello_resp = qgp_server_hello(resp_header, server_id=9001, server_software_version=0x0100,
                                                     status_code=qgp_server_hello.STATUS_OK_HANDSHAKE_COMPLETE,
                                                     # Or proceed to auth
                                                     capabilities_str="ServerReady;EchoCaps:" + self.client_capabilities)
                self.send_qgp_pdu(server_hello_resp, stream_id_to_use=stream_id)
                self.current_dfa_state = ServerClientDFAState.CLIENT_CONNECTED_IDLE  # Or AWAITING_CLIENT_AUTH
                print(f"[Server] State for QGP_ID {self.client_qgp_id}: {self.current_dfa_state}")
            else:
                print(f"[Server] Error for {peer_display}: Expected ClientHello, got {header_obj.msg_type}")
                self.send_error_and_close(stream_id, 1, "Expected ClientHello")  # Error code 1

        elif self.current_dfa_state == ServerClientDFAState.CLIENT_CONNECTED_IDLE:
            if header_obj.msg_type == QGP_MSG_TEXT_CHAT:
                chat_pdu = qgp_text_chat.unpack(header_obj, payload_bytes)
                print(f"[Server] Chat from QGP_ID {self.client_qgp_id}: '{chat_pdu.text_string}'")
                # Broadcast to others (excluding sender)
                broadcast_header = qgp_header(QGP_VERSION, 0, 0, 1)
                broadcast_chat_pdu = qgp_text_chat(broadcast_header,
                                                   text_string=f"Client {self.client_qgp_id}: {chat_pdu.text_string}")
                broadcast_pdu_to_active_clients(broadcast_chat_pdu, exclude_self=self)
            elif header_obj.msg_type == QGP_MSG_PLAYER_MOVEMENT:
                move_pdu = qgp_player_movement.unpack(header_obj, payload_bytes)
                print(
                    f"[Server] Movement from QGP_ID {move_pdu.player_id}: Pos=({move_pdu.x_pos},{move_pdu.y_pos},{move_pdu.z_pos})")
                # Echo movement to other clients (simplified game logic)
                # In a real game, you'd update server state and send GameStateUpdate
                broadcast_pdu_to_active_clients(move_pdu, exclude_self=self)
            # Add handling for Q_REQ, CLIENT_LEAVE_REQUEST etc.
            else:
                print(
                    f"[Server] Unhandled msg_type {header_obj.msg_type} in state CLIENT_CONNECTED_IDLE from QGP_ID {self.client_qgp_id}")
                self.send_error_and_close(stream_id, 2, "Unexpected PDU in Idle state")

        # Add elif for other states: IN_QUEUE, IN_GAME, etc.

    def quic_event_received(self, event: QuicEvent):
        if isinstance(event, HandshakeCompleted):
            self.current_dfa_state = ServerClientDFAState.AWAITING_CLIENT_HELLO  # Ready for QGP Hello
            print(f"[Server] QUIC HandshakeCompleted with {self.resolved_peer_address}.")
        elif isinstance(event, StreamDataReceived):
            if event.stream_id not in self.stream_buffers: self.stream_buffers[event.stream_id] = b''
            self.stream_buffers[event.stream_id] += event.data
            if event.end_stream:  # Optional: process immediately if stream ended
                self.process_stream_buffer(event.stream_id)
            else:  # Or always process after appending
                self.process_stream_buffer(event.stream_id)
        elif isinstance(event, ConnectionTerminated):
            print(
                f"[Server] QUIC ConnectionTerminated with {self.resolved_peer_address}. Reason: {event.reason_phrase}, Err: {event.error_code}")
            # connection_lost will also be called to clean up from ACTIVE_CLIENTS.

    def send_qgp_pdu(self, pdu_instance, stream_id_to_use: Optional[int] = None, end_stream=False):
        peer_display = self.resolved_peer_address
        try:
            packed_pdu_bytes = pdu_instance.pack()
            if stream_id_to_use is None:
                stream_id = self._quic.get_next_available_stream_id(is_unidirectional=False)
            else:
                stream_id = stream_id_to_use

            pdu_type_to_log = pdu_instance.header.msg_type if hasattr(pdu_instance, 'header') else 'UnknownType'
            print(
                f"[Server] Sending PDU type {pdu_type_to_log} ({len(packed_pdu_bytes)} bytes) to {peer_display} (QGP ID: {self.client_qgp_id}) on stream {stream_id}")
            self._quic.send_stream_data(stream_id, packed_pdu_bytes, end_stream=end_stream)
        except Exception as e:
            print(f"[Server] Error sending PDU to {peer_display} (QGP ID: {self.client_qgp_id}): {e}")

    def send_error_and_close(self, stream_id: int, error_code: int, error_message: str):
        err_header = qgp_header(QGP_VERSION, QGP_MSG_UNKNOWN_ERROR, 0, 10)  # High priority
        err_pdu = qgp_errors(err_header, error_code, error_message)
        self.send_qgp_pdu(err_pdu, stream_id_to_use=stream_id, end_stream=True)
        self.close()  # Close the QUIC connection


def broadcast_pdu_to_active_clients(pdu_instance, exclude_self: Optional[QGPServerProtocol] = None):
    """Helper to broadcast a PDU to all active clients, optionally excluding one."""
    clients_to_send_snapshot = list(ACTIVE_CLIENTS)
    if not clients_to_send_snapshot:
        # print("[Server Broadcast] No active clients to broadcast to.")
        return

    for client_protocol in clients_to_send_snapshot:
        if client_protocol == exclude_self:
            continue
        if hasattr(client_protocol, 'send_qgp_pdu') and client_protocol._quic is not None and \
                client_protocol.current_dfa_state not in [ServerClientDFAState.AWAITING_CLIENT_HELLO,
                                                          ServerClientDFAState.CLIENT_TERMINATING]:  # Basic check
            # Server initiates messages on new streams typically.
            # Making a copy of the PDU is safer if its header gets modified by pack()
            # For simple PDUs without complex internal state, direct send is often okay.
            # Here, we assume PDU's pack method correctly sets header.
            # A more robust way would be to re-create the PDU or header for each send if pack modifies it.
            client_protocol.send_qgp_pdu(pdu_instance, stream_id_to_use=None)


async def process_commands(command_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    print(
        "[Server CLI Processor] Ready. Type 'broadcast_chat <msg>', 'list_clients', 'start_game', 'end_game <match_id>', or 'exit'.")
    current_match_sim_id = 1  # Simple match ID simulation

    while True:
        try:
            command_line_input = await command_queue.get()
            if command_line_input is None: break  # Shutdown signal

            command_parts = command_line_input.split()
            if not command_parts: command_queue.task_done(); continue

            cmd = command_parts[0].lower()
            args = command_parts[1:]
            print(f"[Server CLI] Processing: '{cmd}' with args {args}")

            if cmd == "broadcast_chat":
                if args:
                    message_text = " ".join(args)
                    header = qgp_header(QGP_VERSION, 0, 0, 1)
                    chat_pdu = qgp_text_chat(header, text_string=f"[SERVER_BROADCAST]: {message_text}")
                    broadcast_pdu_to_active_clients(chat_pdu)
                else:
                    print("[Server CLI] Usage: broadcast_chat <message>")

            elif cmd == "list_clients":
                # ... (same as your code) ...
                if not ACTIVE_CLIENTS:
                    print("[Server CLI] No clients.")
                else:
                    print("[Server CLI] Active clients:")
                    for i, cp in enumerate(ACTIVE_CLIENTS):
                        pid = cp.resolved_peer_address
                        qid = cp.client_qgp_id
                        print(f"  {i + 1}. {pid} (QGP_ID: {qid}, State: {cp.current_dfa_state})")

            elif cmd == "start_game":  # Simplified game start
                if len(ACTIVE_CLIENTS) < 1:  # Need at least 1 for this demo
                    print("[Server CLI] Not enough players to start a game.")
                else:
                    player_qgp_ids = [c.client_qgp_id for c in ACTIVE_CLIENTS if c.client_qgp_id is not None]
                    if not player_qgp_ids:
                        print("[Server CLI] No clients with assigned QGP IDs to start game.")
                        command_queue.task_done();
                        continue

                    print(
                        f"[Server CLI] Starting simulated game (Match ID: {current_match_sim_id}) for players: {player_qgp_ids}")
                    start_header = qgp_header(QGP_VERSION, 0, 0, 5)
                    game_start_pdu = qgp_game_start(start_header, match_id=current_match_sim_id,
                                                           match_type=0, match_map_id=1, match_mode_id=1,
                                                           player_ids=player_qgp_ids)
                    broadcast_pdu_to_active_clients(game_start_pdu)
                    for client_p in ACTIVE_CLIENTS:  # Update server-side state for clients
                        client_p.current_match_id = current_match_sim_id
                        client_p.current_dfa_state = ServerClientDFAState.CLIENT_IN_GAME  # Example state
                    current_match_sim_id += 1

            elif cmd == "end_game":  # Simplified game end
                if not args or not args[0].isdigit():
                    print("[Server CLI] Usage: end_game <match_id_to_end>")
                else:
                    match_id_to_end = int(args[0])
                    print(f"[Server CLI] Ending simulated game for Match ID: {match_id_to_end}")

                    clients_in_match = [c for c in ACTIVE_CLIENTS if hasattr(c,
                                                                             'current_match_id') and c.current_match_id == match_id_to_end and c.client_qgp_id is not None]
                    if not clients_in_match:
                        print(f"[Server CLI] No active clients found for Match ID: {match_id_to_end}")
                        command_queue.task_done();
                        continue

                    p_ids = [c.client_qgp_id for c in clients_in_match]
                    # Dummy stats
                    p_kills = [len(p_ids) - i - 1 for i in range(len(p_ids))]
                    p_deaths = [i for i in range(len(p_ids))]
                    p_assists = [1] * len(p_ids)

                    end_header = qgp_header(QGP_VERSION, 0, 0, 5)
                    game_end_pdu = qgp_game_end(end_header, match_id=match_id_to_end, match_type=0,
                                                       match_duration=300, match_map_id=1, match_mode_id=1,
                                                       player_ids=p_ids, player_kills=p_kills, player_deaths=p_deaths,
                                                       player_assists=p_assists, player_teamkills=[0] * len(p_ids),
                                                       player_teamdeaths=[0] * len(p_ids),
                                                       player_teamassists=[0] * len(p_ids))
                    for client_p in clients_in_match:
                        client_p.send_qgp_pdu(game_end_pdu)  # Send specifically to clients in this match
                        client_p.current_dfa_state = ServerClientDFAState.CLIENT_CONNECTED_IDLE  # Reset state
                        client_p.current_match_id = None

            elif cmd == "exit" or cmd == "quit":
                print("[Server CLI] Exit command. Signalling server and tasks to shutdown...")
                await command_queue.put(None)  # Signal self to exit loop
                # Cancel other tasks, including potentially the server listener
                current_task = asyncio.current_task()
                tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not current_task]
                for task in tasks:
                    print(f"[Server CLI] Cancelling task: {task.get_name()}")
                    task.cancel()
                break
            else:
                print(f"[Server CLI] Unknown command: {cmd}")

            command_queue.task_done()
        except Exception as e:
            print(f"[Server CLI Processor] Error: {e}")
            # Ensure task_done is called if an item was taken but an error occurred
            if 'command_queue' in locals() and hasattr(command_queue,
                                                       'task_done') and command_queue.unfinished_tasks > 0:
                command_queue.task_done()


def cli_input_loop(loop: asyncio.AbstractEventLoop, command_queue: asyncio.Queue):
    # ... (same as your version, ensure it puts None on EOF/KeyboardInterrupt) ...
    print("\n[Server CLI] Type 'broadcast_chat <msg>', 'list_clients', 'start_game', 'end_game <match_id>', or 'exit'.")
    try:
        while True:
            command_line = input("QGP Server> ")
            if not command_line: continue
            if loop.is_closed(): print("[Server CLI] Event loop closed."); break
            if command_line.lower() in ["exit", "quit"]:
                asyncio.run_coroutine_threadsafe(command_queue.put(None), loop);
                break
            asyncio.run_coroutine_threadsafe(command_queue.put(command_line), loop)
    except EOFError:
        print("[Server CLI] EOF, signalling exit.")
        if not loop.is_closed(): asyncio.run_coroutine_threadsafe(command_queue.put(None), loop)
    except KeyboardInterrupt:
        print("[Server CLI] Ctrl+C in CLI, signalling exit.")
        if not loop.is_closed(): asyncio.run_coroutine_threadsafe(command_queue.put(None), loop)
    except Exception as e:
        print(f"[Server CLI] Input loop error: {e}")
        if not loop.is_closed(): asyncio.run_coroutine_threadsafe(command_queue.put(None), loop)
    finally:
        print("[Server CLI] Input loop ended.")


async def main_server_with_cli():
    configuration = QuicConfiguration(
        alpn_protocols=QGP_ALPN,  # Use constants
        is_client=False,
    )
    configuration.load_cert_chain(certfile='test_cert.pem', keyfile='test_private_key.pem')  # Ensure these exist

    command_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    cli_thread = threading.Thread(target=cli_input_loop, args=(loop, command_queue), daemon=True)
    cli_thread.start()

    processor_task = asyncio.create_task(process_commands(command_queue, loop))

    print(f"Starting QGP Server on localhost:5544 with CLI...")

    server_transport_protocol = None
    try:
        server_transport_protocol = await serve(
            host="localhost",
            port=5544,
            configuration=configuration,
            create_protocol=QGPServerProtocol,  # Use your renamed class
        )
        # Keep the server running until the command processor task is done (e.g., by 'exit' command)
        await processor_task
    except asyncio.CancelledError:
        print("[Server Main] Main server task or command processor was cancelled.")
    except OSError as e:  # E.g. Address already in use
        print(f"[Server Main] OS Error: {e}. Is the port already in use?")
    except Exception as e:
        print(f"[Server Main] Exception in main server execution: {e}")
    finally:
        print("[Server Main] Shutting down...")
        if processor_task and not processor_task.done():
            processor_task.cancel()
            try:
                await processor_task
            except asyncio.CancelledError:
                pass  # Expected cancellation

        if server_transport_protocol:  # This is the transport object returned by aioquic.serve
            print("[Server Main] Closing server listener.")
            server_transport_protocol.close()
            # For servers, wait_closed might not be directly on the transport from serve()
            # but rather you'd manage the lifecycle of the server task itself.
            # For now, closing the transport is the primary step.

        # Wait for CLI thread
        if cli_thread.is_alive():
            print("[Server Main] Waiting for CLI thread to join...")
            cli_thread.join(timeout=2.0)  # Give it a couple of seconds
            if cli_thread.is_alive():
                print("[Server Main] CLI thread did not exit gracefully.")
        print("[Server Main] Server fully shut down.")


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.INFO,
    )
    try:
        asyncio.run(main_server_with_cli())
    except KeyboardInterrupt:
        print("\n[Main] Server process interrupted. Shutting down...")
    except Exception as e:
        print(f"[Main] Top-level server error: {e}")
