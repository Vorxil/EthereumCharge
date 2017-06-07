from factory import getWeb
from station import Station
from string import split
import atexit

class StationCLI:

    #Variables
    station = None
    commands = {}
    command_desc = {}

    #Constructor
    def __init__(self, station):
        self.station = station
        self.commands = {
            "help": self.command_help,
            "quit": self.command_quit
            }
        self.command_desc = {
            "help": "List all commands available",
            "quit": "Shutdown station"
            }
        atexit.register(self.clean_up)

    def parse_input(self, tokens):
        if len(tokens) == 0:
            return self.do_nothing
        else:
            if tokens[0] in self.commands:
                return self.commands[tokens[0]]
            else:
                return self.invalid_command

    def address(self):
        if self.station == None or self.station.contract == None or self.station.contract.address == None:
            return "No address"
        return self.station.contract.address

    #Commands
    def do_nothing(self, tokens):
        return

    def invalid_command(self, tokens):
        print str(tokens[0]) + " is not a valid command. Use 'help' for help."
        return

    def command_help(self, tokens):
        if len(tokens) == 1:
            for command in self.command_desc:
                print command + "\t" + self.command_desc[command]
            return
        else:
            print "Command 'help' takes no arguments"

    def command_quit(self, tokens):
        if len(tokens) == 1:
            self.clean_up()
            quit(0)
        else:
            print "Command 'quit' takes no argument"
        

    #Clean up
    def clean_up(self):
        if self.station != None:
            self.station.tearDownFilters
            self.station = None
        return

    

    

if __name__ == '__main__':
    web = getWeb()
    station_account = web.eth.accounts[0]
    owner_account = web.eth.accounts[1]
    web.eth.defaultAccount = station_account
    cli = StationCLI(Station.factoryDeploy(station_account, owner_account, 30, web))
    def stateChange(event):
        args = event['args']
        print "State Changed:\t" + str(args['from']) + ' ==> ' + str(args['to'])
    cli.station.addFilter('state', 'stateChanged', stateChange)
    print "Station address:\t" + cli.address()
    while True:
        input_string = raw_input()
        tokens = split(input_string)
        cli.parse_input(tokens)(tokens)
