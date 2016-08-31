"""
Default Twisted IRC bot with steam API in-game status check by KwithH.
Steam profiles are checked by ID number, which are registered via
private message to the bot.

Twisted legacy method names require camelCase.
"""

import sys
import time
import requests
from requests.exceptions import ConnectionError

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol, threads, ssl
from twisted.python import log

STEAM_API_URL = 'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=REDACTED&steamids={}'
IRC_URL = "your irc server url"
IRC_PORT = 6667
CHANNEL = "channel name"
NICKNAME = "Steam Bot"
LOG_FILE = "steam_bot_logfile.txt"
STEAM_ID_LIST_FILE = "id_list"

class MessageLogger:
    def __init__(self, file):
        self.file = file

    def log(self, message):
        timestamp = time.strftime("[%H:%M:%S]", time.localtime(time.time()))
        self.file.write('\n%s %s' % (timestamp, message))
        self.file.flush()

    def close(self):
        self.file.close()


class Bot(irc.IRCClient):

    def connectionMade(self):
        """Runs on successful connection."""
        irc.IRCClient.connectionMade(self)
        self.logger = MessageLogger(open(self.factory.filename, "a"))
        self.logger.log("[connected at %s]" %
                        time.asctime(time.localtime(time.time())))

    def connectionLost(self, reason):
        """Runs on connection loss."""
        if irc.IRCClient.connectionLost(self, reason):
            i = 0
            while i < 60:
                time.sleep(10)
                print("Disconnected, attempting reconnect...")
                try:
                    reactor.connectSSL(IRC_URL, IRC_PORT, bot_instance, ssl.ClientContextFactory())
                    i = 60
                except:
                    import traceback
                    print("Failed!")
                    traceback.print_exc()
                    i += 1
        self.logger.log("[disconnected at %s]" %
                        time.asctime(time.localtime(time.time())))
        print("Giving up.")
        self.logger.close()

    def steam_request(self):
        """Get new steam status."""
        new_steam_query = "".join(reversed(self.steaming_stack))[:-1]
        return requests.get(STEAM_API_URL.format(new_steam_query)).json()

    def update_steam_status(self, channel, current_status):
        """Compare live status with cached status."""
        new_status = ""

        try:
            current_status = current_status['response']['players']
        except BaseException as base_exception:
            self.msg(channel, 'No JSON in original. Error: ' + base_exception)

        while True:
            if reactor.running:
                time.sleep(5)
                steaming_stack = []
                id_file = open(STEAM_ID_LIST_FILE, "r")
                for line in id_file:
                    steaming_stack.append(line.split(":")[2] + ",")
                id_file.close()
                try:
                    new_data = self.steam_request(steaming_stack)
                except ConnectionError as connection_error:
                    self.msg(channel, "Error: " + connection_error)

                try:
                    new_data = new_data['response']['players']
                except ValueError as value_error:
                    self.logger.log("Error: " + value_error)

                for old in current_status:
                    for new_person in new_data:
                        if old['steamid'] == new_person['steamid']:
                            name = new_person['personaname'].encode("UTF-8")

                            if 'gameextrainfo' in old:
                                current = old['gameextrainfo']
                            else:
                                current = ""

                            if 'gameextrainfo' in new_person:
                                new_status = new_person['gameextrainfo']
                            else:
                                new_status = ""

                            if current != new_status and current == "":
                                old['gameextrainfo'] = new_status
                                new_status.encode("UTF-8")
                                self.msg(channel, "{} now playing: {}".format(name, new_status))
                                print(new_status)
                            elif current != new_status and new_status == "":
                                old['gameextrainfo'] = new_status
                                self.msg(channel, "{} is no longer in-game.".format(name))
                                print(new_status)
            else:
                break

    # callbacks for events

    def signedOn(self):
        """Called when bot has succesfully signed on to server."""
        self.join(self.factory.channel)

    def joined(self, channel):
        """This will get called when the bot joins the channel."""
        self.logger.log("\n[I have joined %s]" % channel)

    def privMsg(self, user, channel, msg):
        """Called when someone PM's Bot"""

        user = user.split('!', 1)[0]
        self.logger.log("<%s> %s" % (user, msg))

        # Check to see if they're sending me a private message
        if channel == self.NICKNAME:
            if msg.startswith('!register'):
                try:
                    steam_id = msg.split(" ")[1].strip()
                except Exception as exception:
                    self.msg(channel, "usage: !register <steam ID #>")
                    print("Error registering: " + exception)

                if not steam_id.isdigit():
                    self.msg(user, "Please, numbers only.")
                    return

                try:
                    steam_id = steam_id.encode('UTF-8')
                    data = requests.get(STEAM_API_URL.format(steam_id)).json()
                    steam_name = data['response']['players'][0]['personaname'].encode('UTF-8')
                    steam_name = steam_name.replace(":", "~")
                except ConnectionError as connection_error:
                    self.msg(user,
                             "Summin happened M8, couldn't pull your info from Volvo. Double check your steam ID.")
                    print(user + "Error: " + connection_error)

                try:
                    game_title = data['response']['players'][0]['gameextrainfo'].encode('UTF-8')
                except TypeError as type_error:
                    print("Type mismatch: " + type_error)
                    game_title = '_'

                try:
                    id_list = open(STEAM_ID_LIST_FILE, 'r')
                    for line in id_list:
                        if line.split(":")[2] == steam_id:
                            self.msg(user, "You're already registered, douchebag.")
                            return
                    self.msg(user, "Adding {} to the list of cool people...".format(steam_name))
                    id_list.close()
                    id_list = open(STEAM_ID_LIST_FILE, 'a+')
                    id_list.write("\n" + user + ":" + steam_name + ":" + steam_id + ":" + game_title)
                except IOError as io_error:
                    self.msg(user,
                             "Something's up with the id file, let Kris know that Timmy is stuck in the well again. "
                             + io_error)

                return

        elif msg.startswith('!'):
            req = msg[1:]
            print(req)
            if req == 'check':
                self.msg(channel, 'Check yourself before you riggity wreck yourself.')
            elif req == 'help':
                self.msg(channel, ("Steam Bot ! commands are:\n"
                                   "   help    - Display this.\n"
                                   "   check   - Test to make sure I'm here.\n"
                                   "\n\nTo register your steam ID to have your in-game status tracked, /msg {0}"
                                   " !register <steam_ID_number>").format(NICKNAME))

    def action(self, user, channel, msg):
        """This will get called when the bot sees someone do an action."""
        user = user.split('!', 1)[0]
        self.logger.log("* %s %s %s" % (channel, user, msg))

    # irc callbacks

    def ircNick(self, prefix, params):
        """Called when an IRC user changes their nickname."""
        old_nick = prefix.split('!')[0]
        new_nick = params[0]
        self.logger.log("%s is now known as %s" % (old_nick, new_nick))

    def alterCollidedNick(self, nickname):
        """Appends ~ if nick is taken."""
        return nickname + '~'

    def start_steam_check(self):
        """Divert steam checking function to thread."""
        id_file = open(STEAM_ID_LIST_FILE, "r")
        steam_id_stack = []
        for line in id_file:
            steam_id_stack.append(line.split(":")[2] + ",")

        id_file.close()
        steam_query = "".join(reversed(steam_id_stack))[:-1]
        current_status = requests.get(STEAM_API_URL.format(steam_query)).json()
        steam_func = self.update_steam_status(self, self.channel, self.current_status)
        threads.deferToThread(steam_func)


class BotFactory(protocol.ClientFactory):
    """A factory for Bots.

    A new protocol instance will be created each time we connect to the server.
    """

    def __init__(self, channel, filename):
        self.channel = channel
        self.filename = filename

    def buildProtocol(self, addr):
        """Build self as a protocol"""
        bot_proto = Bot()
        bot_proto.factory = self
        print "build_protocol addr: ", addr
        return bot_proto

    def clientConnectionLost(self, connector, reason):
        """If we get disconnected, reconnect to server."""
        print "connection lost: ", reason
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        """If we get an error response, stop trying to connect."""
        print "connection failed: ", reason
        reactor.stop()
        connector.delete()


if __name__ == '__main__':
    # initialize logging
    log.startLogging(sys.stdout)

    # create factory protocol and application
    bot_instance = BotFactory(CHANNEL, LOG_FILE)

    # connect factory to this host and port
    # reactor.connectTCP(IRC_URL, IRC_PORT, f)
    reactor.connectSSL(IRC_URL, IRC_PORT, bot_instance, ssl.ClientContextFactory())

    # run bot
    reactor.run()

    # start checking steam status
    bot_instance.start_steam_check()
