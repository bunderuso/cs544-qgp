#importing the custom libraires
from aioquic.quic import events

from qgp.pdu_constants import QGP_MSG_CLIENT_ERROR, QGP_MSG_CLIENT_HELLO, QGP_MSG_SERVER_HELLO
from qgp.qgp_hello import qgp_client_hello, qgp_server_hello
from qgp.qgp_header import qgp_header
from qgp.qgp_communication import qgp_text_chat


#importing non-custom libraries
import asyncio, logging
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
        print(f"[Server] New connection from: {self.peer_address}")
        ACTIVE_CLIENTS.add(self)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        print(f"[Server] Connection lost from: {self.peer_address}")
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
                self._quic.send_stream_data(stream_id, server_hello_packed, end_stream=False)
                print("Sent response")

                #updating the DFA
                self.current_dfa_state = server_client_dfa.AWAITING_FURTHER_CLIENT_ACTION
                print("Updated current dfa_state")

        elif isinstance(event, ConnectionTerminated):
            print("ConnectionTerminated")
            self.current_dfa_state = server_client_dfa.AWAITING_CLIENT_HELLO


# --- CLI Handling ---
async def process_commands(command_queue: asyncio.Queue):
    """Coroutine to process commands from the CLI queue."""
    print("[Server CLI Processor] Ready for commands.")
    while True:
        command_parts = await command_queue.get()  # Wait for a command
        cmd = command_parts[0].lower()
        args = command_parts[1:]

        print(f"[Server CLI Processor] Processing command: {cmd} with args {args}")

        if cmd == "broadcast_chat":
            if args:
                message_text = " ".join(args)
                print(f"[Server CLI] Broadcasting chat: '{message_text}'")
                header = qgp_header(
                    version=1,
                    msg_type=0,  # Will be set by PDU pack
                    msg_len=0,  # Will be set by PDU pack
                    priority=1  # Example priority
                )
                chat_pdu = qgp_text_chat(header, text=message_text, text_length=len(message_text))

                clients_to_send = list(ACTIVE_CLIENTS)  # Iterate over a copy
                if not clients_to_send:
                    print("[Server CLI] No active clients to broadcast to.")
                for client_protocol in clients_to_send:
                    # Server initiates messages on new streams typically, or use a known broadcast stream
                    # For simplicity, let each client_protocol handle sending on a new stream it picks
                    if hasattr(client_protocol, 'send_qgp_pdu'):
                        # We need to ensure this call is thread-safe if process_commands runs
                        # in the main loop and send_qgp_pdu is called from it.
                        # If cli_loop is in a separate thread, we'd need run_coroutine_threadsafe
                        # For now, assuming cli_loop is an asyncio task.
                        asyncio.create_task(
                            client_protocol.send_qgp_pdu(chat_pdu, stream_id_to_use=None))  # Send on a new stream
            else:
                print("[Server CLI] Usage: broadcast_chat <message>")

        elif cmd == "list_clients":
            if not ACTIVE_CLIENTS:
                print("[Server CLI] No clients currently connected.")
            else:
                print("[Server CLI] Active clients:")
                for i, client in enumerate(ACTIVE_CLIENTS):
                    client_id_str = f"QGP_ID={client.client_qgp_id}" if hasattr(client,
                                                                                'client_qgp_id') and client.client_qgp_id else "ID_Pending"
                    print(f"  {i + 1}. {client.peer_address} ({client_id_str})")

        elif cmd == "exit" or cmd == "quit":
            print("[Server CLI] Exit command received. Server shutting down (manual stop needed for now)...")
            # In a real app, you'd signal the main server loop to stop.
            # For this example, it just stops processing CLI commands.
            # To stop the server, you'd typically cancel the main 'serve' task.
            # loop = asyncio.get_event_loop()
            # loop.stop() # This might be too abrupt for aioquic server
            break
        else:
            print(f"[Server CLI] Unknown command: {cmd}")

        command_queue.task_done()  # Notify queue that item processing is complete


def cli_loop(loop: asyncio.AbstractEventLoop, command_queue: asyncio.Queue):
    """Blocking CLI input loop to run in a separate thread."""
    print("[Server CLI] Type 'broadcast_chat <message>', 'list_clients', or 'exit'.")
    while True:
        try:
            command_line = input("QGP Server> ")
            if command_line:
                # Pass command to asyncio loop safely
                asyncio.run_coroutine_threadsafe(command_queue.put(command_line.split()), loop)
                if command_line.lower() in ["exit", "quit"]:
                    break
        except EOFError:  # Handle Ctrl+D
            asyncio.run_coroutine_threadsafe(command_queue.put(["exit"]), loop)
            break
        except KeyboardInterrupt:  # Handle Ctrl+C
            print("[Server CLI] Interrupted. Sending exit command.")
            asyncio.run_coroutine_threadsafe(command_queue.put(["exit"]), loop)
            break
        except Exception as e:
            print(f"[Server CLI] Error in input loop: {e}")
            break
    print("[Server CLI] Input loop ended.")

#defining the main function
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

#defining the debug function
if __name__ == "__main__":
    try:
        asyncio.run(main())

    #catching keyboard interrupts to terminate the server
    except KeyboardInterrupt:
        print("Server stopping")
