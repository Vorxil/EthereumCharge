from user import User, NotEnoughFundsError, NoConnectionError, NoStationError
from eth_utils import from_wei, to_wei
from filter_utils import getTxEvent, getDeepEvent
from decimal import Decimal
from threading import Thread
from time import sleep
import atexit
from re import match
from factory import getWeb
from string import split
from traceback import print_exc
from station import Station



class UserCLI:

    #CONSTS
    STATES = Station.states

    #Variables
    user = None
    charge_filter = None
    stop_filter = None
    commands = {}
    command_desc = {}

    #Constructor
    def __init__(self, web3):
        self.user = User(web3)
        self.commands = {
            "help": self.command_help,
            "ls": self.command_ls,
            "balance": self.command_balance,
            "station": self.command_station,
            "deposit": self.command_deposit,
            "withdraw": self.command_withdraw,
            "charge": self.command_charge,
            "stop": self.command_stop,
            "logout": self.command_logout
            }

        self.command_desc = {
            "help": "Get help on commands. Identical to ls.",
            "ls": "List all commands",
            "balance": "Fetch account balance",
            "station": "Set the contract address of the charging station, takes address as single argument",
            "deposit": "Deposit ether, takes deposit amount as single argument",
            "withdraw": "Withdraw all your ether",
            "charge": "Begin charging",
            "stop": "Stop charging",
            "logout": "Logout"
            }
        atexit.register(self.clean_up)
        
    #Helpers
    def parse_input(self, tokens):
        if len(tokens) == 0:
            return self.do_nothing
        else:
            if tokens[0] in self.commands:
                return self.commands[tokens[0]]
            else:
                return self.invalid_command

    def web3(self):
        return self.user.contract.web3

    def eth(self):
        return self.user.contract.web3.eth

    #Event handlers
    def powerUpdate(self, event):
        args = event['args']
        charge = Decimal(args['consume'])
        charge = charge/Decimal(1000*3600)
        exp = Decimal('0.000000001')
        print "Charged " + str(charge.quantize(exp)) + " kWh"

    def stop_filter(self, event):
        args = event['args']
        if args['charger'] == self.eth().defaultAccount:
            self.charge_fltr.stop_watching()
            self.stop_fltr.running = False
            self.stop_fltr.web3.eth.uninstallFilter(self.stop_fltr.filter_id)

            exp = Decimal('0.0000001')
            charge = Decimal(args['totalCharge'])
            charge = charge/Decimal(1000*3600)
            cost = from_wei(args['cost'], 'ether')
            print "Charging stopped."
            print "Charged: " + str(charge.quantize(exp)) + " kWh"
            print "Total cost: " + str(cost.quantize(exp)) + " Ether"

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

    def command_ls(self, tokens):
        if len(tokens) == 1:
            for command in self.command_desc:
                print command + "\t" + self.command_desc[command]
            return
        else:
            print "Command 'ls' takes no arguments"

    def command_balance(self, tokens):
        if len(tokens) == 1:
            try:
                print "Balance: " + str(from_wei(self.user.balance(),'ether')) + " Ether"
            except NoConnectionError:
                print "No web connection!"
        else:
            print "Command 'balance' takes no arguments"

    def command_station(self, tokens):
        if len(tokens) == 2:
            address = tokens[1]
            if self.user.registerStation(address) == True:
                print "New station: " + str(address)
            else:
                print "Not a valid address"
        else:
            print "Command 'station' takes one argument"

    def command_deposit(self, tokens):
        if len(tokens) == 2:
            try:
                fltr = self.user.contract.on("chargeDeposited", None)
                txHash = self.user.deposit(tokens[1])
                event = getTxEvent(fltr, txHash, 20, 1)
                if len(event) == 0:
                    print "Deposit timed out"
                    return
                args = event['args']
                print "Deposited " + str(from_wei(args['value'],'ether')) + " Ether"
                return
            except NoConnectionError:
                print "No web connection!"
                return
            except NoStationError:
                print "No registered station!"
            except ValueError:
                print "Not a valid number!"
                return
            except NotEnoughFundsError:
                print "Not enough funds!"
                return
            finally:
                fltr.running = False
                fltr.stopped = True
                self.eth().uninstallFilter(fltr.filter_id)
        else:
            print "Command 'deposit' takes one argument"

    def command_withdraw(self, tokens):
        if len(tokens) == 1:
            try:
                self.user.withdraw()
            except NoConnectionError:
                print "No web connection!"
            except NoStationError:
                print "No registered station!"
        else:
            print "Command 'station' takes one argument"

    def command_charge(self, tokens):
        if len(tokens) == 1:
            try:
                fltr = self.user.contract.on("priceUpdated", None)
                hashed = self.user.getHash()
                txHash = self.user.notify()
                event = getDeepEvent(fltr, hashed, 20, 1)

                if len(event) == 0:
                    print "Notification timed out"
                    return

                print "Price: " + str(from_wei(
                    event['args']['price'], 'ether')*1000*3600) + " Ether/kWh"
            except NoConnectionError:
                print "No web connection!"
                return
            except NoStationError:
                print "No registered station!"
                return
            finally:
                fltr.running = False
                fltr.stopped = True
                self.eth().uninstallFilter(fltr.filter_id)

            response = raw_input("Charge at current price (y/n)? ")
            if response != 'y':
                    try:
                        self.user.cancel()
                        return
                    except NoConnectionError:
                        print "No web connection!"
                        return
                    except NoStationError:
                        print "No registered station!"
                        return

            try:
                fltr = self.user.contract.on("charging", None)
                txHash = self.user.start()
                event = getTxEvent(fltr, txHash, 20, 1)
                
                if len(event) == 0:
                    print "Charging timed out"
                    return
                print "Charging..."

                self.charge_fltr = self.user.contract.on("consume", None, self.powerUpdate)
                self.stop_fltr = self.user.contract.on("chargingStopped", None, self.stop_filter)
                return
            except NoConnectionError:
                print "No web connection!"
                return
            except NoStationError:
                print "No registered station!"
                return
            finally:
                fltr.running = False
                fltr.stopped = True
                self.eth().uninstallFilter(fltr.filter_id)
        else:
            print "Command 'charge' takes no argument"

    def command_stop(self, tokens):
        if len(tokens) == 1:
            if self.charge_filter == None and self.stop_filter == None:
                print "Not charging"
                return
            try:
                fltr = self.user.contract.on("chargingStopped", None)
                txHash = self.user.stop()
                event = getTxEvent(fltr,txHash,20,1)

                if len(event) == 0:
                    print "Stopping timed out"
            except NoConnectionError:
                print "No web connection!"
                return
            except NoStationError:
                print "No registered station!"
                return
            finally:
                fltr.running = False
                fltr.stopped = True
                self.eth().uninstallFilter(fltr.filter_id)               
        else:
            print "Command 'stop' takes no argument"

    def command_logout(self, tokens):
        if len(tokens) == 1:
            self.clean_up()
            quit(0)
        else:
            print "Command 'logout' takes no argument"


    #Exit clean up
    def clean_up(self):
        if self.charge_filter != None or self.stop_filter != None:
            try:
                self.user.stop()
                if self.charge_filter != None:
                    self.charge_filter.join(5)
                    self.charge_filter = None
                if self.stop_filter != None:
                    self.stop_filter.join(5)
                    self.stop_filter = None
                return
            except NoConnectionError:
                print "No web connection!"
                return
            except NoStationError:
                print "No registered station!"
                return
        else:
            try:
                self.user.cancel()
                return
            except NoConnectionError:
                print "No web connection!"
                return
            except NoStationError:
                print "No registered station!"
                return


if __name__ == "__main__":
    cli = None
    input_string = raw_input(">Enter account number: ")
    regex = r"^([0-9])$"
    resp = match(regex, input_string)
    if resp == None:
        print "Not a valid account number!"
        quit(0)
    web = getWeb()
    if web.isConnected() == False:
        print "No web connection!"
        quit(0)
    print "Connected!"
    print "Type 'help' for more information."
    cli = UserCLI(web)
    cli.user.setAccount(cli.eth().accounts[int(input_string)])
    try:
        while True:
            input_string = raw_input(">")
            tokens = split(input_string)
            cli.parse_input(tokens)(tokens)
    except Exception as e:
        print_exc()
        cli.clean_up()
