#importing the custom libraires
from aioquic.quic import events

from qgp.pdu_constants import QGP_MSG_CLIENT_ERROR, QGP_MSG_CLIENT_HELLO, QGP_MSG_SERVER_HELLO
from qgp.qgp_hello import qgp_client_hello, qgp_server_hello
from qgp.qgp_header import qgp_header


#importing non-custom libraries
import asyncio, logging
from typing import Dict, Optional

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, HandshakeCompleted, ConnectionTerminated

#defining a temporary DFA
class server_client_dfa:
    AWAITING_CLIENT_HELLO = 1
    AWAITING_FURTHER_CLIENT_ACTION = 2

#defining the server protocol class
class qgp_server(QuicConnectionProtocol):
    #defining the class varaibles
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_state = Dict[int, server_client_dfa] = {}

        #this is initialized to wait for the hello as no connections available when server first boots
        self.current_dfa_state = server_client_dfa.AWAITING_CLIENT_HELLO

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

                #getting the client information
                print("Client id", headers.client_id)
                print("Client version", headers.client_version)
                print("Client capabilities", headers.client_capabilities)

                #packing the server hello message
                server_hello_header = qgp_header(version=1, msg_type=QGP_MSG_SERVER_HELLO, msg_len=0, priority=0)
                server_hello_payload = qgp_server_hello(header= server_hello_header, server_id=1, server_software_version=1, capabilities_str=headers.client_capabilities)
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

#defining the main function
async def main():
    config = QuicConfiguration(
        alpn_protocols=['qgp/1.0'],
        is_client=False,
    )

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
