import socket

with socket.create_connection(('10.53.4.191', 12456)) as client:
    client.sendall(b"Hello!")
