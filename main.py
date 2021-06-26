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
    print("New connection received:", conn, addr)
    conn.setblocking(False)
    sel.register(conn, selectors.EVENT_READ, read_packet)

    # register new item in players dictionary, but without any information about where they are yet until they send us it
    players[conn.getpeername()] = {"con": conn, "registered": False, "net_id": None, "position": None, "partial_data": b""}

def disconnect_client(conn):
    try:
        players.pop(conn.getpeername())
        print("Client disconnected:", conn)
        sel.unregister(conn)
        conn.close()
    except OSError:
        # TODO: We need to come back and fix this
        pass
    return

def read_packet(conn, mask):
    peer = conn.getpeername()
    try:
        data = conn.recv(1024)
    except (ConnectionResetError, ConnectionAbortedError, ConnectionError) as e:
        disconnect_client(conn)
        return

    # TODO: Do we need this line now that we check for exceptions?
    if not data:
        disconnect_client(conn)
        return

    # Append this message to the previous message
    players[peer]["partial_data"] += data

    if len(players[peer]["partial_data"]) > 10000:
        print("Client sent too much data at one time!")
        print(players[peer]["partial_data"])
        disconnect_client(conn)
        return

    try:
        while b"\n" in players[peer]["partial_data"]:
            end_of_first_command = players[peer]["partial_data"].find(b"\n")
            data = players[peer]["partial_data"][0:end_of_first_command]

            # Lastly, before we parse it, we need to remove this part of the string from the partial data
            players[peer]["partial_data"] = players[peer]["partial_data"][end_of_first_command+1:]

            # We may have gotten more than one message from the client. For now, lets just take the latest one
            # TODO: When we support more than just position updates, we may need to read every message, not just the latest
            data = data.decode('utf-8')
            parse_message_from_client(conn, data, peer)
    except OSError:
        print("Player disconnected while parsing messages")
        disconnect_client(conn)
        return

def parse_message_from_client(conn, data, peer):
    # Parse the information as JSON and store it so we can serve it to clients later
    try:
        client_command = json.loads(data)
    except:
        print("Could not parse JSON sent by client")
        print(data)
        disconnect_client(conn)
        return

    # Check that the command type is valid
    if client_command['$type'] == "MGChat.Commands.ServerConnectCommand, MGChat":
        # TODO: Handle authentication
        handle_registration(conn, client_command, peer)
        return

    if client_command['$type'] == "MGChat.Commands.SetPositionCommand, MGChat":
        handle_movement(conn, client_command, peer)
        return

    print("Invalid command type received from client. Disconnecting them")
    print(client_command)
    disconnect_client(conn)

def handle_registration(conn, server_connect_command, peer):
    if players[peer]["registered"]:
        print("Client attempted to register for a second time")
        disconnect_client(conn)
        return

    # Validate they have a reasonable name
    name = str(server_connect_command['NetId'])
    if len(name) > 20:
        print("Client attempted to connect with name that was too long!")
        disconnect_client(conn)
        return

    # TODO: Validate it doesn't have special characters etc

    players[peer]["registered"] = True
    players[peer]["net_id"] = name

    # Now, send the client a list of all player positions
    handle_movement(conn, server_connect_command, peer)

def handle_movement(conn, setPositionCommand, peer):
    # Check they are registered before handling their movement
    if not players[peer]["registered"]:
        print("Client attempted to set a position before registration")
        disconnect_client(conn)
        return

    # Check whether they have actually moved. If they haven't, we can bail out early!
    if setPositionCommand['Position'] == players[peer]["position"]:
        print("A client sent us a position, but they hadn't moved! Client bug?")
        return

    players[peer]["position"] = setPositionCommand['Position']

    # We now need to let every client know that this person has moved position
    # We can construct some raw JSON that pretends to be a real C# object
    server_command = {
        '$type': 'MGChat.Commands.SetRemotePositionCommand, MGChat',
        'Position': setPositionCommand['Position'],
        'NetId': players[peer]["net_id"]
    }

    notify_clients(conn, server_command)


def notify_clients(conn, server_command):
    for _, player in players.items():
        # Skip the current player (the one who sent us this command)
        if player["con"] == conn:
            continue

        # Send the command
        data = json.dumps(server_command).encode()
        player["con"].send(data + b"\n")


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(100)
    s.setblocking(False)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sel.register(s, selectors.EVENT_READ, accept)

    while True:
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)