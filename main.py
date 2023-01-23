from utilities.bot import Bot
from utilities.user import User


if __name__ == '__main__':
    general: User = User(1, 'chat', [])

    bot = Bot(
        'Username', 'TUM-ID', 'Password',
        general, connect=True
    )
