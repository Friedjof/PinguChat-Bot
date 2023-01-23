from datetime import datetime


class Message:
    def __init__(self, ID: int, content: str, date: datetime):
        self.ID = ID
        self.content = content
        self.date = date

    def __str__(self):
        return f'Message: {self.content}'

    def __repr__(self):
        return f'Message: {self.content}'

    def __eq__(self, other: 'Message'):
        return self.ID == other.ID
