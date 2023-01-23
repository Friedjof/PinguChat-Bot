import re
import requests
import yaml
from datetime import datetime

from utilities.client import Client
from utilities.user import User


class Bot:
    path: str = 'config/commands.yaml'

    commands: dict[str, dict[str, str]] = None
    text: dict[str, str] = None
    executors: dict[str, list] = None

    configs: dict = None
    client: Client = None

    def __init__(self, username: str, identifier: str, password: str, chat: User, connect: bool = True):
        self.load()

        self.client = Client(
            self.configs["config"]["server"]["host"],
            self.configs["config"]["server"]["port"]
        )

        self.client.set_logging(self.log)
        self.client.set_response_handler(self.response)

        if connect:
            self.connect(username, identifier, password, chat)

    def connect(self, username: str, identifier: str, password: str, chat: User):

        self.client.login(username, identifier, password)

        self.client.connect()

        self.client.switch_chat(chat)

        self.loop()

    def load(self):
        with open(self.path, 'r') as file:
            self.configs = yaml.safe_load(file)
            self.commands = self.configs['commands']
            self.text = self.configs['text']
            self.executors = self.configs['exec']

    def _is_command(self, msg: str) -> bool:
        for command in self.commands:
            if self._is_in_message(msg, *self.commands[command]['triggers']):
                return True
        return False

    def _is_text(self, msg: str) -> bool:
        return msg in self.text.keys()

    def _is_exec(self, msg: str) -> bool:
        for k, v in self.executors.items():
            if self._is_in_message(msg, *v):
                return True
        return False

    def get_exec(self, msg: str) -> str | None:
        for k, v in self.executors.items():
            if self._is_in_message(msg, *v):
                self.log(f"Command '{k}' triggered")
                return k
        return None

    def get_answer(self, message: str) -> str | None:
        for command, data in self.commands.items():
            if self._is_in_message(message, *data['triggers']):
                self.log(f'Command {command} triggered')
                return data['response']
        return None

    def response(self, msg: str) -> str | None:
        username, userinput = self.split_message(msg)

        self.log(f"User '{username}' sent '{userinput}' ({msg})")
        self.log(userinput, username, True)

        if self._is_command(userinput):
            return self.get_answer(userinput)
        elif self._is_exec(userinput):
            e: str = self.get_exec(userinput)

            self.log(f"Executing '{e}'")

            if e == 'joke':
                joke: str = self.get_joke()
                self.log(f"Joke: {joke}")
                return joke
            elif e == 'dm':
                return self.prepare_direct_message(username)
            elif e == 'chucknorris':
                chucknorris: str = self.get_chucknorris()
                self.log(f"Chuck Norris: {chucknorris}")
                return chucknorris
            elif e == 'reload':
                if self.is_admin(username):
                    self.load()
                    return self.get_text("reload_success")
                else:
                    self.log(f"User '{username}' tried to reload the bot")
            elif e == 'reconnect':
                if self.is_admin(username):
                    self.client.disconnect()
                    self.client.connect()
                    self.client.switch_chat(self.client.get_current_chat())
                    return self.get_text("reconnect_success")
                else:
                    self.log(f"User '{username}' tried to reconnect")
            elif e == 'mensa':
                return self.get_mensa()
            else:
                self.log(f"Unknown exec '{e}'")

    def get_text(self, key: str) -> str:
        self.log(f"Getting text for '{key}'")
        return self.text[key].replace('\\n', '\n')

    def get_mensa(self) -> str:
        year: str = datetime.now().strftime('%Y')
        week: str = datetime.now().strftime('%W')
        day: int = datetime.now().weekday()

        url: str = f'https://tum-dev.github.io/eat-api/mensa-garching/{year}/{week}.json'

        speiseplan: dict = requests.get(url).json()

        self.log(f"Got mensa plan for {year}/{week}")

        meals: list[str] = []

        if day > 4:
            return self.get_text('mensa_fail')

        for meal in speiseplan["days"][day]["dishes"]:
            meals.append(meal["name"])

        # Formatierung in spalten
        return f"Mensa {datetime.now().strftime('%d.%m.%Y')}:\n" + '\n'.join([f"- {meal}" for meal in meals])

    def loop(self):
        self.client.send_message(self.get_text('start') + "\n" + self.get_text('news'))
        self.client.handel_input()

    def prepare_direct_message(self, username: str) -> str:
        self.client.get_contacts()
        user = self.get_user_by_username(username)
        if user is None:
            return self.get_text('dm_fail')

        self.send_direct_message(user, self.get_text('dm'))
        return self.get_text('dm_success')

    def send_direct_message(self, new_chat: User, message: str):
        current_user: User = self.client.get_current_chat()
        self.client.switch_chat(new_chat)
        self.client.send_message(message)
        self.client.switch_chat(current_user)

    def get_user_by_username(self, username: str) -> User | None:
        self.client.get_contacts()
        for contact in self.client.contact_list.values():
            if contact.name == username:
                return contact
        return None

    def log(self, message: str, username: str = "Bot", save: bool = False):
        chat_section: str = f'{self.client.get_current_chat().name} - ' if self.client.get_current_chat() is not None else ""

        message: str = f'{datetime.now().strftime("%d.%m.%Y %H:%M:%S")} -> {chat_section}{username}: {message}'

        if save:
            with open(self.configs["config"]["logs"], 'a') as file:
                file.write(message + '\n')
        else:
            print(message)

    @staticmethod
    def _is_in_message(message: str, *args: str) -> bool:
        for arg in args:
            if arg in message.lower().split(' '):
                return True
        return False

    def get_joke(self) -> str:
        url = self.configs["config"]["joke_url"]
        response = requests.get(url)
        data: dict = response.json()

        if "joke" in data:
            return data["joke"]
        elif "setup" in data and "delivery" in data:
            return data["setup"] + " " + data["delivery"]
        else:
            return "Ich konnte keinen Witz finden."

    def get_chucknorris(self) -> str:
        url = self.configs["config"]["chucknorris_url"]
        response = requests.get(url)
        data: dict = response.json()
        return data["value"]

    @staticmethod
    def split_message(message: str) -> tuple[str, str]:
        match = re.search(r"([^:]+):(.*)", message)
        if match:
            username = match.group(1).strip()
            message = match.group(2).strip()
            return username, message
        else:
            return "", message

    @staticmethod
    def is_admin(username: str) -> bool:
        return username == 'chris' or username == 'mirza'
