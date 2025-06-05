import asyncio
import logging
from typing import Optional

from aioquic.asyncio import QuicConnectionProtocol, connect
from aioquic.quic import events
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aioquic.quic.events import QuicEvent, StreamDataReceived, HandshakeCompleted, ConnectionTerminated

from qgp.pdu_constants import QGP_MSG_CLIENT_ERROR, QGP_MSG_CLIENT_HELLO, QGP_MSG_SERVER_HELLO
from qgp.qgp_hello import qgp_client_hello, qgp_server_hello
from qgp.qgp_header import qgp_header

#defining the DFA class
class client_dfa_state:
    INITIAL = 0
    QUIC_CONNECTING = 1
    AWAITING_SERVER_HELLO = 2
    HANDSHAKE_COMPLETED = 3

#defining the client class for QUIC
class qgp_client_protocol(QuicConnectionProtocol):
    #defining the class variables
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_dfa_state = client_dfa_state.INITIAL
        self._client_hello_sent_on_stream: Optional[int] = None

    #defining the function to handle quic connections
    def quic_event_received(self, event: events.QuicEvent):
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
            headers, payload = qgp_header.unpack(data)

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



    #defining function to send the client hello
    def send_qgp_client_hello(self):
        stream_id = 0
        self.client_hello_sent_on_stream = stream_id

        #creating the header
        header = qgp_header(
            version=1,
            msg_type=QGP_MSG_CLIENT_HELLO,
            msg_len=0,
            priority=0
        )

        #creating the payload
        client_hello_payload = qgp_client_hello(
            header=header,
            client_id=1,
            client_version=1,
            capabilities="test_env"
        )

        #packing the payload and sending
        client_hello_packed = client_hello_payload.pack()
        self._quic.send_stream_data(stream_id, client_hello_packed, end_stream=False)

        #updating the dfa status
        self.current_dfa_state = client_dfa_state.AWAITING_SERVER_HELLO
        print("client hello sent")

#defining the main function
async def main():
    config = QuicConfiguration(
        alpn_protocols=['qgp/1.0'],
        is_client=True,
    )

    #loading the ssl cert
    config.load_verify_locations(cafile="test_cert.pem")

    async with connect(configuration = config,
                              port = 5544,
                              host = "localhost",
                              create_protocol=qgp_client_protocol) as connection:
        connection.client_dfa_state = client_dfa_state.QUIC_CONNECTING

        await asyncio.sleep(10)
        print("Client connected")

#defining the debug function
if __name__ == '__main__':
    asyncio.run(main())