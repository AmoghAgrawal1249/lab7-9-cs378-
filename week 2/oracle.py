import socket
import struct
import sys

TCP_PORT = 5000
CONNECT = 1
LINK_STATE = 2


def read_exact(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("peer closed the TCP connection")
        chunks.extend(chunk)
    return bytes(chunks)


def receive_frame(sock):
    message_type, body_size = struct.unpack("!BH", read_exact(sock, 3))
    return message_type, read_exact(sock, body_size)


def send_frame(sock, message_type, body):
    sock.sendall(struct.pack("!BH", message_type, len(body)) + body)


def read_topology(path):
    rows = []
    with open(path, encoding="utf-8") as config:
        for line_number, raw in enumerate(config, start=1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            try:
                rows.append([int(value) for value in line.split()])
            except ValueError as error:
                raise ValueError(f"line {line_number}: costs must be integers") from error

    if not rows:
        raise ValueError("configuration needs at least one upper-triangle cost row")
    node_count = len(rows) + 1
    if node_count > 26:
        raise ValueError("configuration supports at most 26 nodes")
    for row_index, row in enumerate(rows):
        expected = node_count - row_index - 1
        if len(row) != expected:
            raise ValueError(
                f"row {row_index + 1} must contain {expected} upper-triangle costs"
            )
        if any(cost == 0 or cost < -1 for cost in row):
            raise ValueError("costs must be positive integers or -1 for no link")
    return rows


def neighbourhoods(rows):
    count = len(rows) + 1
    costs = [[-1] * count for _ in range(count)]
    for i in range(count):
        costs[i][i] = 0
    for i, row in enumerate(rows):
        for offset, cost in enumerate(row, start=1):
            j = i + offset
            costs[i][j] = costs[j][i] = cost
    return [
        [(j, costs[i][j]) for j in range(count) if j == i or costs[i][j] > 0]
        for i in range(count)
    ]


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <bind-ip> <topology-file>", file=sys.stderr)
        return 2

    bind_ip, config_path = sys.argv[1:]
    rows = read_topology(config_path)
    node_count = len(rows) + 1
    peers = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((bind_ip, TCP_PORT))
            listener.listen(node_count)
            print(f"Oracle listening on {bind_ip}:{TCP_PORT}; expecting {node_count} nodes")

            for index in range(node_count):
                conn, source = listener.accept()
                conn.settimeout(30)
                try:
                    message_type, body = receive_frame(conn)
                    if message_type != CONNECT or len(body) != 6:
                        raise ValueError("expected a 6-byte CONNECT message")
                    ip_text = socket.inet_ntoa(body[:4])
                    udp_port = struct.unpack("!H", body[4:])[0]
                    if udp_port == 0:
                        raise ValueError("UDP port must be nonzero")
                    peer = {"id": chr(ord("A") + index), "ip": ip_text,
                            "port": udp_port, "socket": conn, "source": source}
                    peers.append(peer)
                    print(f"Registered {peer['id']} at {ip_text}:{udp_port} (TCP peer {source[0]})")
                except Exception:
                    conn.close()
                    raise

            links = neighbourhoods(rows)
            for index, peer in enumerate(peers):
                entries = links[index]
                body = bytearray([len(entries)])
                for node_index, cost in entries:
                    target = peers[node_index]
                    body.extend(struct.pack("!c4sHi", target["id"].encode("ascii"),
                                            socket.inet_aton(target["ip"]),
                                            target["port"], cost))
                send_frame(peer["socket"], LINK_STATE, bytes(body))
                rendered = ", ".join(f"{chr(ord('A') + node)}={cost}" for node, cost in entries)
                print(f"Sent LINK-STATE to {peer['id']}: {rendered}")

            print("All initial neighbourhoods sent. Keep this terminal open during the demo.")
            input("Press Enter to close the oracle... ")
    except (OSError, ValueError, ConnectionError, TimeoutError) as error:
        print(f"Oracle error: {error}", file=sys.stderr)
        return 1
    finally:
        for peer in peers:
            try:
                peer["socket"].close()
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
