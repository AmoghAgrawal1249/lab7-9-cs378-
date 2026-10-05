import socket

with socket.create_server(('10.53.4.191', 12456)) as server:
    conn, _ = server.accept()
    print(conn.recv(1024).decode())
    