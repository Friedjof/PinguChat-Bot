from utilities.message import Message


class User:
    def __init__(self, ID: int, name: str, messages: list[Message]):
        self.ID = ID
        self.name = name
        self.messages = messages

    def __str__(self):
        return f'User: {self.name}'

    def __repr__(self):
        return f'User: {self.name}'

    def __eq__(self, other):
        return self.ID == other.ID
