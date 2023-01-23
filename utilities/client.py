import time
from socket import socket, AF_INET, SOCK_STREAM
from typing import Callable

import requests

from utilities.user import User


class Client:
    username: str = None
    identifier: str = None
    password: str = None
    token: str = None
    ID: int = None
    contact_list: dict[int, User] = None

    _timeout: int = 1
    _socket: socket = None
    _connected: bool = False
    _logged_in: bool = False
    _current_chat: User = None
    
    _logging: Callable = print
    _response_handler: Callable = None
    _get_text: Callable = None

    def __init__(self, server: str, port: int):
        self.server = server
        self.port = port

    def login(self, username: str, identifier: str, password: str) -> bool:
        self.username = username
        self.identifier = identifier
        self.password = password

        self.token: str = self.get_token()

        if self.token is None:
            self._logging("Fehler beim Login")
            return False

        response: requests.Response = requests.get(
            f'http://{self.server}/api/user/me/',
            headers={"accept": "application/json", "Authorization": f"Bearer {self.token}"},
            timeout=self._timeout
        )

        if response.status_code != 200 or 'id' not in response.json():
            self._logging("Fehler beim Login")
            return False

        self.ID = response.json()['id']

        self._logging(f"Logged in as {self.username} ({self.ID})")
        self._logging("Login was successful")

        self._logged_in = True
        return True

    def connect(self):
        if self._connected:
            return
        if not self._logged_in:
            self.login(self.username, self.identifier, self.password)

        s: socket = socket(AF_INET, SOCK_STREAM)
        s.connect((self.server, self.port))

        if not self._handshake(s):
            return

        # Identifizierung
        request: bytes = bytes([0x00, 0x02, 0x04])
        request += bytes(self.ID.to_bytes(4, 'big'))

        s.send(request)

        # Authentifizierung
        request: bytes = bytes([0x00, 0x03])
        request += bytes([(len(self.token) >> 8) & 0xFF, len(self.token) & 0xFF])

        for char in self.token:
            request += bytes([ord(char)])

        s.send(request)

        self._socket = s
        self._connected = True

    def get_token(self) -> str | None:
        response: requests.Response = requests.post(
            f'http://{self.server}/token',
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": self.username, "password": self.password}, timeout=self._timeout
        )

        if response.status_code != 200 or 'access_token' not in response.json():
            self._logging("Fehler beim Login")
            return None

        self._logging("Token request was successful")

        self.token = response.json()['access_token']
        return self.token

    def get_contacts(self):
        if not self._logged_in:
            return None

        response: requests.Response = requests.get(
            f'http://{self.server}/api/users',
            headers={"Authorization": f"Bearer {self.token}"}, timeout=self._timeout
        )

        if response.status_code != 200:
            self._logging("Fehler beim Abrufen der Kontakte")
            return

        self.contact_list = {}

        for contact in response.json():
            if 'username' not in contact or 'id' not in contact:
                continue

            self.contact_list[contact['id']] = User(contact['id'], contact['username'], [])

        self.sort_contacts()

    def sort_contacts(self):
        self.contact_list = dict(sorted(self.contact_list.items(), key=lambda item: item[1].name))

    def get_messages(self, user: User, limit: int = 10, pagination: int = 1):
        if not self._logged_in:
            return None

        response: requests.Response = requests.get(
            f'http://{self.server}/api/messages/with/{user.ID}?limit={limit}&pagination={pagination}',
            headers={"Authorization": f"Bearer {self.token}"}, timeout=self._timeout,
        )

        self._logging(response.json())

        if response.status_code != 200:
            self._logging("Fehler beim Abrufen der Nachrichten")
            return

    def switch_chat(self, user: User):
        if not self._connected:
            self.connect()

        request: bytes = bytes([0x00, 0x04, 0x04])

        request += bytes(user.ID.to_bytes(4, 'big'))

        self._socket.send(request)

        # Acknowledgement
        response: bytes = self._socket.recv(2)
        if response[0] != 0x00 or response[1] != 0x05:
            self._logging("Fehler beim Wechseln des Chats")
            return

        self._current_chat = user

    def send_message(self, message: str):
        if not self._logged_in or not self._connected or message is None:
            return None

        buffer: bytes = message.encode('utf-8')
        length: int = min(len(buffer), 0xFFFF)

        request: bytes = bytes([0x01])
        request += bytes([(length >> 8) & 0xFF, length & 0xFF])

        for i in range(length):
            request += bytes([buffer[i]])

        self._socket.send(request)

        self._logging(f"Nachricht an '{self._current_chat.name}' gesendet")
        self._logging(message, save=True)

    def handel_input(self):
        self._input_loop()
        
    def set_logging(self, logging: Callable):
        self._logging = logging

    def get_current_chat(self) -> User:
        return self._current_chat

    def set_response_handler(self, handler: Callable):
        self._response_handler = handler

    def _input_loop(self):
        self._logging("Input loop started…")

        while True:
            request: bytes = self._socket.recv(1)

            if len(request) == 0:
                self._logging("Connection lost")
                self._connected = False

                self._logging("Trying to reconnect…")
                self.connect()
                continue

            if request[0] == 0x00:
                hsType: bytes = self._socket.recv(1)
                self._logging(f"Handshake Type: {', '.join(hex(b) for b in hsType)}")
                if hsType[0] == 0x05:
                    self._logging("Handshake erfolgreich")
                    continue
            elif request[0] == 0x01:
                length: int = (self._socket.recv(1)[0] << 8) + self._socket.recv(1)[0]
                message: str = self._socket.recv(length).decode('utf-8')

                self._logging(f"'{self._current_chat.name}' -> '{message}'")

                response: str = self._response_handler(message)

                if response is not None:
                    self.send_message(response)

                time.sleep(2)

    def disconnect(self) -> bool:
        if not self._connected:
            return False

        self._socket.close()
        self._connected = False
        return True

    def __del__(self):
        if self._socket is not None:
            self._socket.close()

    @staticmethod
    def _handshake(s: socket) -> bool:
        response: bytes = s.recv(3)

        if response[0] != 0x00 or response[1] != 0x00 or response[2] != 0x2a:
            print(">> Fehler beim Verbinden zum Server")
            return False

        print(">> Verbindung zum Server hergestellt")

        # send {0x00, 0x01} to server
        s.send(bytes([0x00, 0x01]))

        return True
