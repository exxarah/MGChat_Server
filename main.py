#!/usr/bin/env python3

import socket
import selectors
import json

# TODO: Load these values from a configuration file
HOST = '0.0.0.0'  # Standard loopback interface address (localhost)
PORT = 1272  # Port to listen on (non-privileged ports are > 1023)

sel = selectors.DefaultSelector()

players = {}


def accept(sock, mask):
    conn, addr = sock.accept()
    print("New connection recieved:", conn, addr)
    conn.setblocking(False)
    sel.register(conn, selectors.EVENT_READ, read_packet)


def read_packet(conn, mask):
    try:
        data = conn.recv(1000)
    except (ConnectionResetError, ConnectionAbortedError, ConnectionError) as e:
        try:
            players.pop(conn.getpeername())
        except:
            pass
        print("Client disconnected:", conn)
        sel.unregister(conn)
        conn.close()
        return

    # TODO: Do we need this line now that we check for exceptions?
    if not data:
        try:
            players.pop(conn.getpeername())
        except:
            pass
        print("Client disconnected:", conn)
        print(conn.getpeername())
        sel.unregister(conn)
        conn.close()
        return

    # Parse the information as JSON and store it so we can serve it to clients later
    try:
        d = json.loads(data.decode('utf-8'))
    except:
        try:
            players.pop(conn.getpeername())
        except:
            pass
        print("Invalid data from client!")
        print(data)
        sel.unregister(conn)
        conn.close()
        return

    if len(d) != 1:
        try:
            players.pop(conn.getpeername())
        except:
            pass
        print("Invalid data from client!")
        print(d)
        sel.unregister(conn)
        conn.close()
        return

    # TODO: Check if the player name is already in use -- no duplicates!!!!
    players[conn.getpeername()] = d[0]

    # Send new information to the client about the position of all players (except the current player)
    data_to_send = []

    for _, value in players.items():
        # Ignore self
        if value == d[0]:
            continue

        data_to_send.append(value)

    data = json.dumps(data_to_send).encode()
    print(data)
    conn.send(data)


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(100)
    s.setblocking(False)
    sel.register(s, selectors.EVENT_READ, accept)

    while True:
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)

'''

    conn, addr = s.accept()

    with conn:
        print('Connected by', addr)
        while True:
            data = conn.recv(1024)

            if not data:
                break
            if random.random() < 0.001:
                print(data)
            # dummy data!!!
            i += 0.001
            data = '[{"NetId":"ss23","Position":"' + str(int(i)) + ', 100"}]'
            conn.sendall(data.encode('utf-8'))
'''
