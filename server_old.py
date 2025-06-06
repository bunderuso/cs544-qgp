#importing the custom libraires
from aioquic.quic import events

from qgp.pdu_constants import QGP_MSG_CLIENT_ERROR, QGP_MSG_CLIENT_HELLO, QGP_MSG_SERVER_HELLO
from qgp.qgp_hello import qgp_client_hello, qgp_server_hello
from qgp.qgp_header import qgp_header
from qgp.qgp_communication import qgp_text_chat

#importing the cli library
from cli_funcs.cli_cmds import *


#importing non-custom libraries
import asyncio, logging, threading
from typing import Dict, Optional, Set

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, HandshakeCompleted, ConnectionTerminated

#tracking the connected clients
ACTIVE_CLIENTS: Set[QuicConnectionProtocol] = set()

#defining a temporary DFA
class server_client_dfa:
    AWAITING_CLIENT_HELLO = 1
    AWAITING_FURTHER_CLIENT_ACTION = 2

#defining the server protocol class
class qgp_server(QuicConnectionProtocol):
    #defining the class varaibles
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_state: Dict[int, server_client_dfa] = {}

        #this is initialized to wait for the hello as no connections available when server first boots
        self.current_dfa_state = server_client_dfa.AWAITING_CLIENT_HELLO

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

    #defining function to handle the incoming QUIC requests
    def quic_event_received(self, event: QuicEvent):
        #letting quic do its normal handshake
        if isinstance(event, HandshakeCompleted):
            print("HandshakeCompleted")
        elif isinstance(event, StreamDataReceived):
            print("StreamDataReceived")

            #saving the stream_id and data
            stream_id = event.stream_id
            data = event.data

            #upacking the headers and payload from
            headers, payload = qgp_header.unpack(data)

            #checking the header message type
            if headers.msg_type == QGP_MSG_CLIENT_HELLO:
                print("Hello packet received")

                #unpacking the client hello
                client_hello = qgp_client_hello.unpack(headers, payload)
                #getting the client information
                print("Client id", client_hello.client_id)
                print("Client version", client_hello.client_version)
                print("Client capabilities", client_hello.capabilities)

                #packing the server hello message
                server_hello_header = qgp_header(version=1, msg_type=QGP_MSG_SERVER_HELLO, msg_len=0, priority=0)
                server_hello_payload = qgp_server_hello(header= server_hello_header, server_id=1, server_software_version=1, capabilities_str=client_hello.capabilities)
                server_hello_packed = server_hello_payload.pack()

                #sending the packed response to the client
                print("Hello stream id", stream_id)
                self._quic.send_stream_data(stream_id, server_hello_packed, end_stream=False)
                print("Sent response")

                #updating the DFA
                self.current_dfa_state = server_client_dfa.AWAITING_FURTHER_CLIENT_ACTION
                print("Updated current dfa_state")

        elif isinstance(event, ConnectionTerminated):
            print("ConnectionTerminated")
            self.current_dfa_state = server_client_dfa.AWAITING_CLIENT_HELLO

    async def send_qgp_pdu(self, pdu_instance, stream_id_to_use: Optional[int] = None, end_stream=False):
        """Helper method to pack and send a QGP PDU."""
        peer_display = self.resolved_peer_address if self.resolved_peer_address else "Peer"

        #packed_pdu = pdu_instance.pack()
        packed_pdu = pdu_instance

        if stream_id_to_use is None:
           stream_id = self._quic.get_next_available_stream_id(
                    is_unidirectional=False)  # Or True for one-way broadcast
        else:
            stream_id = stream_id_to_use
        print("Stream id", stream_id)

        #pdu_type_to_log = pdu_instance.header.msg_type if hasattr(pdu_instance, 'header') else 'UnknownType'

        #print(
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
                    version= 1,
                    msg_type=0,
                    msg_len=0,
                    priority=1
                )
                chat_pdu = qgp_text_chat(chat_header, text_length= len(message_text), text=message_text)

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

        #sending the error command
        elif cmd == "send_error":
            packaged_pdu = error_sender(args)

            #checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)
        #sending the chat command
        elif cmd == "chat":
            packaged_pdu = client_chat(args)

            # checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)

        # sending the start_game command
        elif cmd == "start_game":
            packaged_pdu = start_game(args)

            # checking a pdu package was returned and if so sending it
            if packaged_pdu is None:
                print("Invalid arguments provided")
            else:
                sender(packaged_pdu)

        # sending the player_move command
        elif cmd == "end_game":
            packaged_pdu = end_game(args)

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

#defining function to send the package pdu
def sender(packaged_pdu):
    #getting the active clients
    clients_to_send_snapshot = list(ACTIVE_CLIENTS)
    if not clients_to_send_snapshot:
        print("[Server CLI] No active clients to broadcast to.")

    #looping through the active clients and sending the error
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


#defining the main function that does not have the CLI
async def main():
    config = QuicConfiguration(
        alpn_protocols=['qgp/1.0'],
        is_client=False,
    )

    #defining the ssl cert and key
    config.load_cert_chain(certfile='test_cert.pem', keyfile='test_private_key.pem')

    #starting the server
    print("Server starting")
    await serve(
        host = "localhost",
        port = 5544,
        configuration = config,
        create_protocol=qgp_server
    )

    #running forever
    await asyncio.Future()


async def main_server_with_cli():
    configuration = QuicConfiguration(
        alpn_protocols=['qgp/1.0'],  # Use your ALPN from constants
        is_client=False,
    )
    # Ensure paths to cert and key are correct
    configuration.load_cert_chain(certfile='test_cert.pem', keyfile='test_private_key.pem')

    command_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    cli_thread = threading.Thread(target=cli_input_loop, args=(loop, command_queue), daemon=True)
    cli_thread.start()

    processor_task = asyncio.create_task(process_commands(command_queue, loop))

    #print(f"Starting QGP Server on {qgp_constants.QGP_SERVER_HOST}:{qgp_constants.QGP_DEFAULT_PORT} with CLI...")

    server_transport = None
    try:
        await serve(
            host="localhost",
            port=5544,
            configuration=configuration,
            create_protocol=qgp_server
        )

        await processor_task
    except asyncio.CancelledError:
        print("[Server Main] Main server task or command processor was cancelled.")
    except Exception as e:
        print(f"[Server Main] Exception in main server execution: {e}")
    finally:
        print("[Server Main] Shutting down...")
        if not processor_task.done():
            processor_task.cancel()  # Ensure processor task is stopped
            try:
                await processor_task  # Allow it to process the cancellation
            except asyncio.CancelledError:
                pass  # Expected

        if server_transport:  # aioquic's serve returns a transport which can be closed
            print("[Server Main] Closing server transport.")
            server_transport.close()
            # For newer asyncio/aioquic that might return a Server object:
            # await server_transport.wait_closed()

        # Ensure CLI thread is encouraged to exit if it hasn't
        # The cli_input_loop should exit when it puts None on the queue or on exception
        if cli_thread.is_alive():
            print("[Server Main] Waiting for CLI thread to join (max 1s)...")
            cli_thread.join(timeout=1.0)  # Give it a moment to exit
            if cli_thread.is_alive():
                print("[Server Main] CLI thread did not exit gracefully.")

        print("[Server Main] Server fully shut down.")

#defining the debug function
if __name__ == "__main__":
    try:
        #asyncio.run(main())
        asyncio.run(main_server_with_cli())
    #catching keyboard interrupts to terminate the server
    except KeyboardInterrupt:
        print("Server stopping")
