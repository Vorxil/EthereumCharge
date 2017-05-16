import solc, web3, time, atexit, string, sys, math, datetime, decimal, threading, eth_utils

#Setup

filePath = ".\\chargeStation.sol"
contractName = "ChargeStation"

compiled = solc.compile_files([filePath])

contract_abi = compiled[filePath + ":" + contractName]['abi']
contract_bin = compiled[filePath + ":" + contractName]['bin']
contract_bin_runtime = compiled[filePath + ":" + contractName]['bin-runtime']

web = web3.Web3(web3.providers.rpc.HTTPProvider("http://localhost:8545"))

connected = web.isConnected()

print "Is connected to TestRPC: " + str(connected)
if not connected:
    exit(0)

numAccounts = len(web.eth.accounts)
accountChoice = raw_input("Select account (2-" + str(numAccounts) + "): ")

if accountChoice.isdigit() and len(accountChoice) > 0:
    if len(accountChoice) > 1 and accountChoice[0] == '0':
        print "Invalid number"
        exit(0)
    else:
        accountChoice = int(accountChoice)
else:
    print "Not a number"

if accountChoice >= numAccounts:
    print "Account number too large"
    exit(0)

web.eth.defaultAccount = web.eth.accounts[accountChoice]

print "User address: " + str(web.eth.defaultAccount)

# Global
contract_address = ""
contract = web3.contract.Contract.factory(web,
                                          contract_name = contractName,
                                          abi = contract_abi,
                                          bytecode = contract_bin,
                                          bytecode_runtime = contract_bin_runtime)
filters = {}
updated = False
charging = False


def setupFilters():
    global filters
    filters = {
        "chargeDeposited": contract.on("chargeDeposited", None, chargeDeposited),
        "priceUpdated": contract.on("priceUpdated", None, priceUpdated),
        "charging": contract.on("charging", None, charging),
        "consume": contract.on("consume", None, consume),
        "stopCharging": contract.on("chargingStopped", None, stop_charging)
        }
#Commands

def parse_input(tokens):
    if len(tokens) == 0:
        return do_nothing
    else:
        if tokens[0] in commands:
            return commands[tokens[0]]
        else:
            return invalid_command

def do_nothing(tokens):
    return

def invalid_command(tokens):
    print str(tokens[0]) + " is not a valid command. Use 'help' for help."
    return

def command_help(tokens):
    if len(tokens) == 1:
        for command in command_desc:
            print command + "\t" + command_desc[command]
        return
    else:
        print "Command 'help' takes no arguments"

def command_ls(tokens):
    if len(tokens) == 1:
        for command in command_desc:
            print command + "\t" + command_desc[command]
        return
    else:
        print "Command 'ls' takes no arguments"

def command_balance(tokens):
    if len(tokens) == 1:
        print "Balance: " + str(eth_utils.from_wei(
            web.eth.getBalance(web.eth.defaultAccount),'ether')) + " Ether"
    else:
        print "Command 'balance' takes no arguments"

def command_station(tokens):
    global filters
    global contract
    if len(tokens) == 2:
        address = tokens[1]
        if web3.eth.is_address(address):
            if contract.address != None:
                for fltr in filters:
                    fltr.stopWatching() 
            contract.address = address
            filters = setupFilters()
            print "New station: " + str(address)
        else:
            print "Not a valid address"
    else:
        print "Command 'station' takes one argument"

def command_deposit(tokens):
    if len(tokens) == 2:
        try:
            amount = decimal.Decimal(tokens[1])
        except:
            print "Not a valid number"
            return
        if contract.address != None:
            if amount > 0:
                contract.transact({'value' : eth_utils.to_wei(amount,'ether')}).depositCharge()
            else:
                print "Amount must be positive, non-zero"
        else:
            print "No station given! Use 'station' to set the address."
    else:
        print "Command 'station' takes one argument"

def command_withdraw(tokens):
    if len(tokens) == 1:
        if contract.address != None:
            contract.transact().withdraw()
        else:
            print "No station given! Use 'station' to set the address."
    else:
        print "Command 'station' takes one argument"

def command_charge(tokens):
    global updated
    if len(tokens) == 1:
        if contract.address != None:
            updated = False
            contract.transact().notifyCharge()
        else:
            print "No station given! Use 'station' to set the address."
    else:
        print "Command 'charge' takes no argument"

def command_stop(tokens):
    global charging
    if len(tokens) == 1:
        if contract.address != None:
            contract.transact().stopCharge()
            charging = False
        else:
            print "No station given! Use 'station' to set the address."
    else:
        print "Command 'stop' takes no argument"

def command_logout(tokens):
    global filters
    if len(tokens) == 1:
        if charging == True:
            contract.transact().stopCharge()
        for fltr in filters:
            fltr.stopWatching
        filters = {}
        exit(0)
    else:
        print "Command 'logout' takes no argument"

commands = {
    "help": command_help,
    "ls": command_ls,
    "balance": command_balance,
    "station": command_station,
    "deposit": command_deposit,
    "withdraw": command_withdraw,
    "charge": command_charge,
    "stop": command_stop,
    "logout": command_logout
    }

command_desc = {
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

#Event handlers
def chargeDeposited(event):
    args = event['args']
    print "Deposited " + str(eth_utils.from_wei(args['value'], 'ether')) + " Ether"

def priceUpdated(event):
    args = event['args']
    print "New price: " + str(eth_utils.from_wei(args['price'],'ether')*1000*3600) + " Ether/kWh"

def consume(event):
    args = event['args']
    print "Consuming at " + str(args['consume']) + " W"

def charging(event):
    global charging
    chargine = True
    print "Charging..."

def stop_charging(event):
    global charging
    chargine = True
    print "Finished charging"

#Exit clean up
def clean_up():
    global filters
    if charging == True:
        contract.transact.stopCharge()
    for fltr in filters:
        fltr.stopWatching
    filters = {}

atexit.register(clean_up)

#Main loop

while True:
    tokens = raw_input(">").split()
    parse_input(tokens)(tokens)
