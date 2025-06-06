import asyncio
import logging
from typing import Optional, Dict, Tuple, sys

from aioquic.asyncio import QuicConnectionProtocol, connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, HandshakeCompleted, ConnectionTerminated
import argparse  # For command-line arguments

# QGP Package imports based on your provided client.py structure
# Assuming pdu_constants.py contains all QGP_MSG_ codes and DFA state enums
from qgp.pdu_constants import *  # Imports all constants like QGP_MSG_CLIENT_HELLO, ClientDFAState, QGP_VERSION, QGP_ALPN etc.
from qgp.qgp_header import qgp_header
from qgp.qgp_hello import qgp_client_hello, qgp_server_hello
from qgp.qgp_communication import qgp_text_chat
from qgp.qgp_player import qgp_player_movement  # Assuming this is where player movement is
# Assuming your session_pdus are in qgp_session_mgmt.py for game start/end
from qgp.qgp_session_mgmt import qgp_game_start, qgp_game_end #, qgp_player_join_notify, qgp_player_leave_notify
from qgp.qgp_errors import qgp_errors  # Assuming your error PDU class is named qgp_errors


class QGPClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_dfa_state = ClientDFAState.INITIAL  # Using ClientDFAState directly
        self._first_bidirectional_stream_id: Optional[int] = None
        self.stream_buffers: Dict[int, bytes] = {}
        self.resolved_peer_address: Optional[Tuple[str, int]] = None
        self.qgp_server_id: Optional[int] = None
        self.my_qgp_client_id: int = 1234
        self.current_match_id: Optional[int] = None

    def connection_made(self, transport):
        super().connection_made(transport)
        peername = transport.get_extra_info('peername')
        self.resolved_peer_address = peername if peername else ("UnknownServer", 0)
        print(f"[Client] Connection made to: {self.resolved_peer_address}")
        self.current_dfa_state = ClientDFAState.QUIC_CONNECTING
        print(f"[Client] State: QUIC_CONNECTING (waiting for QUIC HandshakeCompleted)")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        super().connection_lost(exc)
        print(f"[Client] Connection lost to {self.resolved_peer_address}: {exc if exc else 'Closed normally'}")
        self.current_dfa_state = ClientDFAState.TERMINATING

    def process_stream_buffer(self, stream_id: int):
        buffer = self.stream_buffers.get(stream_id, b'')
        peer_display = self.resolved_peer_address

        processing_possible = True
        while processing_possible and len(buffer) >= qgp_header.SIZE:
            try:
                temp_header_for_len, _ = qgp_header.unpack(buffer)
                # Ensure your qgp_header class uses 'message_length'
                expected_total_pdu_len = temp_header_for_len.message_length

                if len(buffer) >= expected_total_pdu_len:
                    full_pdu_bytes = buffer[:expected_total_pdu_len]
                    buffer = buffer[expected_total_pdu_len:]
                    self.stream_buffers[stream_id] = buffer

                    header_obj, payload_bytes = qgp_header.unpack(full_pdu_bytes)
                    print(
                        f"[Client] Processing PDU from {peer_display} on stream {stream_id}: Type={header_obj.msg_type}, Len={header_obj.message_length}")
                    self.handle_qgp_pdu(header_obj, payload_bytes, stream_id)
                else:
                    processing_possible = False
            except ValueError as e:
                print(f"[Client] PDU unpack error for stream {stream_id} from {peer_display}: {e}. Clearing buffer.")
                self.stream_buffers[stream_id] = b''
                processing_possible = False
            except Exception as e:
                print(f"[Client] Unexpected error processing buffer for {peer_display}: {e}")
                self.stream_buffers[stream_id] = b''
                processing_possible = False

    def handle_qgp_pdu(self, header_obj: qgp_header, payload_bytes: bytes, stream_id: int):
        """Main QGP PDU handling logic based on DFA state for the client."""
        peer_display = self.resolved_peer_address

        if self.current_dfa_state == ClientDFAState.AWAITING_SERVER_HELLO:
            if header_obj.msg_type == QGP_MSG_SERVER_HELLO:
                server_hello = qgp_server_hello.unpack(header_obj, payload_bytes)
                self.qgp_server_id = server_hello.server_id
                print(f"[Client] Received ServerHello from {peer_display} (ServerID: {self.qgp_server_id}):")
                # Assuming your qgp_server_hello unpacks to these attribute names
                print(
                    f"  SWVer: {server_hello.server_software_version}, Status: {server_hello.status_code}, Caps: '{server_hello.capabilities_str}'")

                if server_hello.status_code == qgp_server_hello.STATUS_OK_HANDSHAKE_COMPLETE:
                    self.current_dfa_state = ClientDFAState.IDLE_CONNECTED
                    print(f"[Client] State: IDLE_CONNECTED. QGP Handshake successful!")
                elif server_hello.status_code == qgp_server_hello.STATUS_OK_PROCEED_TO_AUTH:
                    print(f"[Client] Server requires authentication. State: AWAITING_AUTH_RESULT (Not Implemented)")
                    # self.current_dfa_state = ClientDFAState.AWAITING_AUTH_RESULT # Assuming this state exists
                    # TODO: Implement sending QGP_MSG_CLIENT_AUTH_SUBMIT
                    self.current_dfa_state = ClientDFAState.IDLE_CONNECTED  # Placeholder bypass for now
                else:
                    print(f"[Client] ServerHello indicated error: {server_hello.status_code}. Terminating.")
                    self.send_error_and_close(QGP_ERROR_SERVER_HANDSHAKE_FAILED,  # Use defined error codes
                                              f"ServerHello error status: {server_hello.status_code}")
            else:
                print(f"[Client] Error: Expected ServerHello, got type {header_obj.msg_type} from {peer_display}")
                self.send_error_and_close(QGP_ERROR_UNEXPECTED_PDU, f"Expected ServerHello, got {header_obj.msg_type}")


        elif self.current_dfa_state == ClientDFAState.IDLE_CONNECTED or \
                self.current_dfa_state == ClientDFAState.IN_GAME:

            if header_obj.msg_type == QGP_MSG_TEXT_CHAT:
                chat_pdu = qgp_text_chat.unpack(header_obj, payload_bytes)
                # Assuming your qgp_text_chat unpacks to 'text_string'
                print(f"\n>>> [CHAT from Server/Broadcast]: {chat_pdu.text_string}\nQGP Client> ",
                      end="")

            elif header_obj.msg_type == QGP_MSG_PLAYER_MOVEMENT and self.current_dfa_state == ClientDFAState.IN_GAME:
                move_pdu = qgp_player_movement.unpack(header_obj, payload_bytes)
                if move_pdu.player_id != self.my_qgp_client_id:
                    print(
                        f"\n>>> [Player {move_pdu.player_id} Moved]: Pos=({move_pdu.x_pos:.1f},{move_pdu.y_pos:.1f},{move_pdu.z_pos:.1f})\nQGP Client> ",
                        end="")

            elif header_obj.msg_type == QGP_MSG_GAME_START:  # Using your constant name
                # Assuming your qgp_session_mgmt.qgp_game_start unpacks to these attributes
                game_start_pdu = qgp_game_start.unpack(header_obj, payload_bytes)
                self.current_match_id = game_start_pdu.match_id
                self.current_dfa_state = ClientDFAState.IN_GAME
                print(
                    f"\n>>> [GAME START] Match ID: {self.current_match_id}, Type: {game_start_pdu.match_type}, Map: {game_start_pdu.match_map}, Mode: {game_start_pdu.match_mode}")
                print(f"   Players in match: {game_start_pdu.match_player_ids}\nQGP Client> ", end="")

            elif header_obj.msg_type == QGP_MSG_GAME_END and self.current_dfa_state == ClientDFAState.IN_GAME:
                # Assuming your qgp_session_mgmt.qgp_game_end unpacks to these attributes
                game_end_pdu = qgp_game_end.unpack(header_obj, payload_bytes)
                print(
                    f"\n>>> [GAME END] Match ID: {game_end_pdu.match_id} ended. Duration: {game_end_pdu.match_duration}s")
                print(f"   Players: {game_end_pdu.match_player_ids}")
                print(f"   Kills:   {game_end_pdu.match_player_kills}")  # Ensure this field exists in your qgp_game_end
                self.current_dfa_state = ClientDFAState.IDLE_CONNECTED
                self.current_match_id = None
                print("QGP Client> ", end="")


            #TODO: FIX ME
            # elif header_obj.msg_type == QGP_MSG_PLAYER_JOIN_NOTIFY and self.current_dfa_state == ClientDFAState.IN_GAME:
            #     join_pdu = qgp_player_join_notify.unpack(header_obj, payload_bytes)
            #     # Ensure qgp_player_join_notify unpacks to player_id and player_name
            #     print(
            #         f"\n>>> [Player Joined Match {self.current_match_id}]: ID={join_pdu.player_id}, Name='{join_pdu.player_name}'\nQGP Client> ",
            #         end="")

            # TODO: FIX ME
            # elif header_obj.msg_type == QGP_MSG_PLAYER_LEAVE_NOTIFY and self.current_dfa_state == ClientDFAState.IN_GAME:
            #     leave_pdu = qgp_player_leave_notify.unpack(header_obj, payload_bytes)
            #     # Ensure qgp_player_leave_notify unpacks to player_id and reason_code
            #     print(
            #         f"\n>>> [Player Left Match {self.current_match_id}]: ID={leave_pdu.player_id}, Reason={leave_pdu.reason_code}\nQGP Client> ",
            #         end="")

            elif header_obj.msg_type == QGP_MSG_UNKNOWN_ERROR or header_obj.msg_type == QGP_MSG_SERVER_ERROR or header_obj.msg_type == QGP_MSG_CLIENT_ERROR:  # Catching your error types
                # Assuming your qgp_errors PDU class and its unpack method handle these
                # And it unpacks to attributes like error_code and message or error_message
                err_pdu = qgp_errors.unpack(header_obj, payload_bytes)
                err_code_attr = getattr(err_pdu, 'error_code', getattr(err_pdu, 'error_specific_code', 'N/A'))
                err_msg_attr = getattr(err_pdu, 'message', getattr(err_pdu, 'error_message', 'No details'))
                print(
                    f"\n>>> [ERROR RECEIVED]: Type={header_obj.msg_type}, Code={err_code_attr}, Msg='{err_msg_attr}'\nQGP Client> ",
                    end="")
            else:
                print(
                    f"[Client] Warning: Unhandled PDU type {header_obj.msg_type} in state {self.current_dfa_state} from {peer_display}")

        # Add elif for ClientDFAState.AWAITING_AUTH_RESULT if you implement full auth flow

    def quic_event_received(self, event: QuicEvent):
        if isinstance(event, HandshakeCompleted):
            # self.current_dfa_state = ClientDFAState.QUIC_CONNECTING # Is already set in connection_made
            print(f"[Client] QUIC HandshakeCompleted with {self.resolved_peer_address}. ALPN: {self.alpn_protocol}")
            if self.current_dfa_state == ClientDFAState.QUIC_CONNECTING:
                self.send_qgp_client_hello()
            else:
                print(
                    f"[Client] Warning: QUIC HandshakeCompleted received in unexpected state: {self.current_dfa_state}")

        elif isinstance(event, StreamDataReceived):
            if event.stream_id not in self.stream_buffers: self.stream_buffers[event.stream_id] = b''
            self.stream_buffers[event.stream_id] += event.data
            self.process_stream_buffer(event.stream_id)
        elif isinstance(event, ConnectionTerminated):
            peer_display = self.resolved_peer_address if self.resolved_peer_address else event.peer_address if hasattr(
                event, 'peer_address') else "Server"
            print(
                f"[Client] QUIC ConnectionTerminated by {peer_display}. Reason: {event.reason_phrase}, Err: {event.error_code}")
            self.current_dfa_state = ClientDFAState.TERMINATING

    def send_qgp_pdu(self, pdu_instance, end_stream=False):
        """Helper to pack and send a QGP PDU on the primary client stream."""
        if self._quic is None or self._quic.is_closed:  # Check if connection is usable
            print("[Client] Cannot send PDU: QUIC connection is not active or is closed.")
            self.current_dfa_state = ClientDFAState.TERMINATING  # Reflect connection issue
            return

        if self._first_bidirectional_stream_id is None:
            # Client initiates on stream 0 (first bi-di)
            self._first_bidirectional_stream_id = 0

        stream_id_to_use = self._first_bidirectional_stream_id

        try:
            packed_pdu_bytes = pdu_instance.pack()
            pdu_type_to_log = pdu_instance.header.msg_type if hasattr(pdu_instance, 'header') else 'UnknownType'
            print(
                f"[Client] Sending PDU type {pdu_type_to_log} ({len(packed_pdu_bytes)} bytes) on stream {stream_id_to_use}")
            self._quic.send_stream_data(stream_id_to_use, packed_pdu_bytes, end_stream=end_stream)
        except Exception as e:
            print(f"[Client] Error sending PDU: {e}")
            if self._quic and not self._quic.is_closed:
                self.close()
            self.current_dfa_state = ClientDFAState.TERMINATING

    def send_qgp_client_hello(self):
        # Ensure QGP_VERSION is imported or defined
        header = qgp_header(QGP_VERSION, 0, 0, 1)  # Type and length set by qgp_client_hello.pack()
        # Ensure qgp_client_hello __init__ matches: header, client_id, client_version, capabilities
        client_hello_pdu = qgp_client_hello(
            header=header, client_id=self.my_qgp_client_id,
            client_version=0x0100,
            capabilities="PythonClient;BasicTest"  # This should match the field name in your class
        )
        self.send_qgp_pdu(client_hello_pdu, end_stream=False)
        self.current_dfa_state = ClientDFAState.AWAITING_SERVER_HELLO
        print(f"[Client] State: AWAITING_SERVER_HELLO")

    def send_error_and_close(self, error_code: int, error_message: str):
        print(f"[Client] Sending error and closing: {error_code} - {error_message}")
        if self._quic and not self._quic.is_closed:
            # Ensure QGP_MSG_CLIENT_ERROR is defined and qgp_errors class exists
            err_header = qgp_header(QGP_VERSION, QGP_MSG_CLIENT_ERROR, 0, 10)
            # Ensure qgp_errors __init__ matches: header, error_code, error_message, [severity, etc.]
            # And its pack() method sets the correct message_type in the header.
            # Assuming qgp_errors takes (header, error_code, severity, error_message_str)
            err_pdu = qgp_errors(err_header, error_code=error_code, severity=2, error_message_str=error_message)
            self.send_qgp_pdu(err_pdu, end_stream=True)

        if self._quic and not self._quic.is_closed:
            self.close()
        self.current_dfa_state = ClientDFAState.TERMINATING


async def cli_input_handler(protocol_instance: QGPClientProtocol, loop: asyncio.AbstractEventLoop):
    print("\n[Client CLI] Type 'chat <message>', 'move <x_float> <y_float>', or 'exit'.")
    while protocol_instance.current_dfa_state != ClientDFAState.TERMINATING:
        try:
            if loop.is_closed(): break
            command_line = await loop.run_in_executor(None, input, "QGP Client> ")
            if not command_line: continue
            if protocol_instance.current_dfa_state == ClientDFAState.TERMINATING: break

            parts = command_line.lower().split()
            cmd = parts[0] if parts else ""
            args = parts[1:]

            if cmd == "chat":
                if protocol_instance.current_dfa_state >= ClientDFAState.IDLE_CONNECTED:
                    if args:
                        message = " ".join(args)
                        # Ensure qgp_header uses 'message_length'
                        header = qgp_header(QGP_VERSION, 0, 0, 1)
                        # Ensure qgp_text_chat __init__ takes (header, text_string)
                        # and its pack() method sets the correct QGP_MSG_TEXT_CHAT type
                        chat_pdu = qgp_text_chat(header, text_string=message)
                        protocol_instance.send_qgp_pdu(chat_pdu)
                    else:
                        print("Usage: chat <your message>")
                else:
                    print("Not connected enough to chat yet.")
            elif cmd == "move":
                if protocol_instance.current_dfa_state == ClientDFAState.IN_GAME:
                    if len(args) == 2:
                        try:
                            x, y = float(args[0]), float(args[1])
                            header = qgp_header(QGP_VERSION, 0, 0, 2)
                            # Ensure qgp_player_movement __init__ fields match
                            move_pdu = qgp_player_movement(header, protocol_instance.my_qgp_client_id,
                                                           0, 0, x, y, 0.0, 5)  # movement_type, direction, x,y,z, speed
                            protocol_instance.send_qgp_pdu(move_pdu)
                        except ValueError:
                            print("Usage: move <x_float> <y_float>")
                    else:
                        print("Usage: move <x_float> <y_float>")
                else:
                    print("Cannot send movement, not in game.")
            elif cmd == "exit" or cmd == "quit":
                print("[Client CLI] Exiting...")
                if protocol_instance._quic and not protocol_instance._quic.is_closed:
                    protocol_instance.close(error_code=0, reason_phrase="Client exiting via CLI")
                protocol_instance.current_dfa_state = ClientDFAState.TERMINATING
                break
            else:
                print(f"Unknown command: {cmd}")
        except EOFError:
            print("[Client CLI] EOF, exiting.")
            if protocol_instance.current_dfa_state != ClientDFAState.TERMINATING:
                if protocol_instance._quic and not protocol_instance._quic.is_closed:
                    protocol_instance.close(error_code=0, reason_phrase="Client exiting via EOF")
                protocol_instance.current_dfa_state = ClientDFAState.TERMINATING
            break
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            print("[Client CLI] CLI task cancelled.")
            break
        except Exception as e:
            print(f"[Client CLI] Error: {e}")


async def main(host: str, port: int):
    configuration = QuicConfiguration(
        alpn_protocols=[QGP_ALPN] if isinstance(QGP_ALPN, bytes) else QGP_ALPN,  # Ensure QGP_ALPN is a list of bytes
        is_client=True,
    )
    try:
        # Ensure 'your_public_cert.pem' matches the server's generated cert for self-signed setup
        configuration.load_verify_locations(cafile="your_public_cert.pem")
    except FileNotFoundError:
        print("[Client] WARNING: Certificate file 'your_public_cert.pem' not found.")

    print(f"Attempting to connect to QGP Server at {host}:{port}...")
    client_protocol_instance: Optional[QGPClientProtocol] = None
    cli_task: Optional[asyncio.Task] = None

    try:
        async with connect(
                host=host, port=port, configuration=configuration,
                create_protocol=QGPClientProtocol,
        ) as client_protocol_instance:
            print("[Client] QUIC Connection attempt initiated.")
            loop = asyncio.get_running_loop()
            cli_task = loop.create_task(cli_input_handler(client_protocol_instance, loop))

            while client_protocol_instance.current_dfa_state != ClientDFAState.TERMINATING:
                if not client_protocol_instance._quic or client_protocol_instance._quic.is_closed:
                    print("[Client] Connection detected closed in main loop.")
                    if client_protocol_instance.current_dfa_state != ClientDFAState.TERMINATING:
                        client_protocol_instance.current_dfa_state = ClientDFAState.TERMINATING
                    break
                await asyncio.sleep(0.1)

            print("[Client] Main loop condition met (TERMINATING state or closed connection).")

    except ConnectionRefusedError:
        print(f"[Client] Connection refused. Is the server running at {host}:{port}?")
    except FileNotFoundError as e:  # More specific for cert
        print(f"[Client] Certificate file error: {e}. Ensure 'test_cert.pem' is correct.")
    except asyncio.CancelledError:
        print("[Client] Main client task was cancelled.")
    except Exception as e:
        print(f"[Client] Connection error or other exception in main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[Client] Main client function finishing...")
        if cli_task and not cli_task.done():
            print("[Client] Cancelling CLI task.")
            cli_task.cancel()
            try:
                await cli_task
            except asyncio.CancelledError:
                print("[Client] CLI task successfully cancelled.")
            except Exception as e_cli:
                print(f"[Client] Exception while awaiting cancelled CLI task: {e_cli}")
        print("[Client] Main client function finished.")


if __name__ == "__main__":
    # Ensure QGP_SERVER_HOST and QGP_DEFAULT_PORT are defined (e.g., from qgp.pdu_constants)
    # Defaulting here if not found from wildcard import, but explicit import is better.
    DEFAULT_HOST = getattr(sys.modules.get('qgp.pdu_constants'), 'QGP_SERVER_HOST', 'localhost')
    DEFAULT_PORT = getattr(sys.modules.get('qgp.pdu_constants'), 'QGP_DEFAULT_PORT', 5544)

    parser = argparse.ArgumentParser(description="QGP Client")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="Server hostname or IP address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Server port")
    args = parser.parse_args()

    # For Python 3.8+ you might need to add this for Windows proactor loop with aioquic if not using default loop
    # if sys.platform == "win32" and sys.version_info >= (3,8):
    #    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.INFO,  # Change to logging.DEBUG for verbose aioquic logs
    )
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        print("\n[Client] Client process shutting down via KeyboardInterrupt...")
    except Exception as e:
        print(f"[Client Main] Top-level client error: {e}")
