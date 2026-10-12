import socket
import struct
import sys


def read_exact(connection, size):
    data = b""
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ConnectionError("VN disconnected")
        data += chunk
    return data


def main():
    with open(sys.argv[2]) as config:
        rows = []
        for line in config:
            line = line.split("#", 1)[0].strip()
            if line:
                rows.append([int(value) for value in line.split()])

    count = len(rows) + 1
    costs = [[0] * count for _ in range(count)]
    for i, row in enumerate(rows):
        for j, cost in enumerate(row, start=i + 1):
            costs[i][j] = costs[j][i] = cost

    connections = []
    peers = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((sys.argv[1], 5000))
            server.listen(count)
            print(f"Oracle waiting for {count} nodes", flush=True)

            for i in range(count):
                connection, _ = server.accept()
                connections.append(connection)
                message_type, size = struct.unpack("!BH", read_exact(connection, 3))
                if message_type != 1:
                    raise ValueError("expected CONNECT")
                ip, port = struct.unpack("!4sH", read_exact(connection, size))
                peers.append((ip, port))
                print(f"Registered {chr(65 + i)}: {socket.inet_ntoa(ip)}:{port}", flush=True)

            for i, connection in enumerate(connections):
                neighbours = []
                for j in range(count):
                    if i == j or costs[i][j] > 0:
                        neighbours.append(j)

                body = bytes([len(neighbours)])
                for j in neighbours:
                    ip, port = peers[j]
                    body += struct.pack("!c4sHi", chr(65 + j).encode(), ip, port, costs[i][j])
                connection.sendall(struct.pack("!BH", 2, len(body)) + body)
                print(f"Sent LINK-STATE to {chr(65 + i)}")
    finally:
        for connection in connections:
            connection.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 oracle.py <own-ip> <topology-file>")
    try:
        main()
    except (OSError, ValueError, struct.error) as error:
        sys.exit(f"Oracle error: {error}")
