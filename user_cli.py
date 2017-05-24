import solc, web3, atexit, string, sys, datetime, decimal, filter_utils, eth_utils

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
updated = False
charging = False
charge_fltr = None
stop_fltr = None

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
    global contract
    if len(tokens) == 2:
        address = tokens[1]
        if web3.eth.is_address(address): 
            contract.address = address
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
                fltr = contract.on("chargeDeposited", None)
                txHash = contract.transact({'value' : eth_utils.to_wei(amount,'ether')}).deposit()
                event = filter_utils.getTxEvent(fltr, txHash, 60, 1)
                if len(event) == 0:
                    print "Deposit timed out"
                    return
                args = event['args']
                print "Deposited " + str(eth_utils.from_wei(args['value'],'ether')) + " Ether" 
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
    global charge_fltr
    global stop_fltr
    if len(tokens) == 1:
        if contract.address != None:
            fltr = contract.on("priceUpdated", None)
            hashed = contract.call().getHash(web.eth.defaultAccount)
            txHash = contract.transact().notify()
            event = filter_utils.getDeepEvent(fltr, hashed, 20, 1)

            if len(event) == 0:
                print "Notification timed out"
                return

            print "Price: " + str(eth_utils.from_wei(
                event['args']['price'], 'ether')*1000*3600) + " Ether/kWh"

            response = raw_input("Charge at current price (y/n)? ")
            if response != 'y':
                contract.transact().cancel()
                return

            fltr = contract.on("charging", None)
            txHash = contract.transact().start()
            event = filter_utils.getTxEvent(fltr, txHash, 20, 1)
            if len(event) == 0:
                print "Charging timed out"
                return
            print "Charging..."

            def powerUpdate(event):
                args = event['args']
                charge = decimal.Decimal(args['consume'])
                charge = charge/(decimal.Decimal(1000*3600))
                exp = decimal.Decimal('0.000000001')
                print "Charged " + str(charge.quantize(exp)) + " kWh"

            def stop_filter(event):
                global charge_fltr
                global stop_fltr
                args = event['args']
                if args['charger'] == web.eth.defaultAccount:
                    charge_fltr.stop_watching()
                    stop_fltr.running = False
                    stop_fltr.web3.eth.uninstallFilter(stop_fltr.filter_id)

                    exp = decimal.Decimal('0.0000001')
                    charge = decimal.Decimal(args['totalCharge'])
                    charge = charge/(decimal.Decimal(1000*3600))
                    cost = eth_utils.from_wei(args['cost'], 'ether')
                    print "Charging stopped."
                    print "Charged: " + str(charge.quantize(exp)) + " kWh"
                    print "Total cost: " + str(cost.quantize(exp)) + " Ether"

            charge_fltr = contract.on("consume", None, powerUpdate)
            stop_fltr = contract.on("chargingStopped", None, stop_filter)
            return            
        else:
            print "No station given! Use 'station' to set the address."
    else:
        print "Command 'charge' takes no argument"

def command_stop(tokens):
    global charge_fltr
    global stop_fltr
    if len(tokens) == 1:
        if contract.address != None:
            if charge_fltr != None:
                charge_fltr.stopWatching()
                charge_fltr = None
            if stop_fltr != None:
                stop_fltr.stopWatching()
                stop_fltr = None    
            try:
                fltr = contract.on("chargingStopped", None)
                txHash = contract.transact().stop()
                event = filter_utils.getTxEvent(fltr,txHash,20,1)
                if len(event) != 0:
                    args = event['args']
                    exp = decimal.Decimal('0.0000001')
                    charge = decimal.Decimal(args['totalCharge'])
                    charge = charge/(decimal.Decimal(1000*3600))
                    cost = eth_utils.from_wei(args['cost'], 'ether')
                    print "Charging stopped."
                    print "Charged: " + str(charge.quantize(exp)) + " kWh"
                    print "Total cost: " + str(cost.quantize(exp)) + " Ether"
                else:
                    print "Stopping timed out"
            except:
                print "Not charging"
            
        else:
            print "No station given! Use 'station' to set the address."
    else:
        print "Command 'stop' takes no argument"

def command_logout(tokens):
    global charge_fltr 
    if len(tokens) == 1:
        try:
            contract.transact().stop()
        except:
            print "Not charging"
        if charge_fltr != None:
            charge_fltr.stop_watching()
            charge_fltr = None
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

#Exit clean up
def clean_up():
    global charge_fltr
    try:
        contract.transact().stop()
    except:
        print "Not charging"
    if charge_fltr != None:
        charge_fltr.stopWatching()
        charge_fltr = None
            
atexit.register(clean_up)

#Main loop

while True:
    tokens = raw_input(">").split()
    parse_input(tokens)(tokens)
