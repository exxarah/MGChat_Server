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

    # register new item in players dictionary, but without any information about where they are yet until they send us it
    players[conn.getpeername()] = {"con": conn, "info": False}
    # send event letting people know I exist
    # register myself to find out when new people join

def disconnect_client(conn):
    players.pop(conn.getpeername())
    print("Client disconnected:", conn)
    sel.unregister(conn)
    conn.close()
    return

def read_packet(conn, mask):
    try:
        data = conn.recv(1000)
    except (ConnectionResetError, ConnectionAbortedError, ConnectionError) as e:
        disconnect_client(conn)
        return

    # TODO: Do we need this line now that we check for exceptions?
    if not data:
        disconnect_client(conn)
        return

    # We may have gotten more than one message from the client. For now, lets just take the latest one
    # TODO: When we support more than just position updates, we may need to read every message, not just the latest
    data = data.decode('utf-8')
    data = data.split("\n")[-2]

    # Parse the information as JSON and store it so we can serve it to clients later
    try:
        d = json.loads(data)
    except:
        print("Invalid data from client!")
        print(data)
        disconnect_client(conn)
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
    if d[0] == players[conn.getpeername()]["info"]:
        # A client sent us data but they haven't moved!
        return

    # Update the players position and let every client know about it :)
    players[conn.getpeername()]["info"] = d[0]
    notify_clients()


def notify_clients():
    print("updating positions")
    for _, player in players.items():
        # Send new information to the client about the position of all players (except the current player)
        data_to_send = []

        for _, value in players.items():
            # Ignore self
            if value["con"] == player["con"]:
                continue
            if value["info"]:
                data_to_send.append(value["info"])

        data = json.dumps(data_to_send).encode()
        player["con"].send(data + b"\n")

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
