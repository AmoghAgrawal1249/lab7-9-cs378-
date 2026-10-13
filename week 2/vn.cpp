#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>
#include <csignal>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

void read_exact(int fd, void* buffer, size_t size) {
    char* data = static_cast<char*>(buffer);
    size_t received = 0;
    while (received < size) {
        ssize_t amount = recv(fd, data + received, size - received, 0);
        if (amount < 0 && errno == EINTR) continue;
        if (amount <= 0) throw std::runtime_error("TCP receive failed");
        received += amount;
    }
}

void send_all(int fd, const void* buffer, size_t size) {
    const char* data = static_cast<const char*>(buffer);
    size_t sent = 0;
    while (sent < size) {
        ssize_t amount = send(fd, data + sent, size - sent, 0);
        if (amount < 0 && errno == EINTR) continue;
        if (amount <= 0) throw std::runtime_error("TCP send failed");
        sent += amount;
    }
}

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "Usage: ./vn <oracle-ip> <own-ip> <udp-port>\n";
        return 1;
    }

    int udp = -1, tcp = -1;
    int result = 0;
    std::signal(SIGPIPE, SIG_IGN);
    try {
        sockaddr_in own{};
        own.sin_family = AF_INET;
        int port = std::stoi(argv[3]);
        if (port < 1 || port > 65535) throw std::runtime_error("invalid UDP port");
        own.sin_port = htons(port);
        if (inet_pton(AF_INET, argv[2], &own.sin_addr) != 1)
            throw std::runtime_error("invalid own IP");

        udp = socket(AF_INET, SOCK_DGRAM, 0);
        if (udp < 0 || bind(udp, reinterpret_cast<sockaddr*>(&own), sizeof(own)) < 0)
            throw std::runtime_error("UDP bind failed");
        std::cout << "UDP bound to " << argv[2] << ':' << port << '\n';

        sockaddr_in oracle{};
        oracle.sin_family = AF_INET;
        oracle.sin_port = htons(5000);
        if (inet_pton(AF_INET, argv[1], &oracle.sin_addr) != 1)
            throw std::runtime_error("invalid Oracle IP");
        tcp = socket(AF_INET, SOCK_STREAM, 0);
        if (tcp < 0 || connect(tcp, reinterpret_cast<sockaddr*>(&oracle), sizeof(oracle)) < 0)
            throw std::runtime_error("TCP connect failed");

        uint8_t type = 1;
        uint16_t size = htons(6);
        send_all(tcp, &type, 1);
        send_all(tcp, &size, 2);
        send_all(tcp, &own.sin_addr, 4);
        send_all(tcp, &own.sin_port, 2);
        std::cout << "Sent CONNECT\n";

        uint8_t count;
        read_exact(tcp, &type, 1);
        read_exact(tcp, &size, 2);
        read_exact(tcp, &count, 1);
        if (type != 2 || ntohs(size) != 1 + count * 11)
            throw std::runtime_error("invalid LINK-STATE message");

        std::cout << "Neighbourhood (id, IP, UDP port, cost):\n";
        for (int i = 0; i < count; ++i) {
            char id;
            in_addr ip;
            uint16_t udp_port;
            uint32_t cost;
            read_exact(tcp, &id, 1);
            read_exact(tcp, &ip, 4);
            read_exact(tcp, &udp_port, 2);
            read_exact(tcp, &cost, 4);
            std::cout << "  " << id << "  " << inet_ntoa(ip) << ':'
                      << ntohs(udp_port) << "  cost=" << ntohl(cost) << '\n';
        }
    } catch (const std::exception& error) {
        std::cerr << "VN error: " << error.what() << '\n';
        result = 1;
    }
    if (tcp >= 0) close(tcp);
    if (udp >= 0) close(udp);
    return result;
}
