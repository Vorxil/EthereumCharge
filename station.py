import solc, web3, time, atexit, string, sys, math, datetime, decimal, threading, eth_utils

comm_args = sys.argv
if len(comm_args) != 2:
    print "Not enough arguments"
    exit(0)

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
accountChoice = int(comm_args[1])
print numAccounts
print accountChoice
if accountChoice >= numAccounts:
    print "Account number too large"
    exit(0)

station_address = web.eth.accounts[accountChoice]
owner_address = web.eth.accounts[0];
web.eth.defaultAccount = station_address

contract = web3.contract.Contract.factory(web,
                                          contract_name = contractName,
                                          abi = contract_abi,
                                          bytecode = contract_bin,
                                          bytecode_runtime = contract_bin_runtime)

contract.address = contract.web3.eth.getTransactionReceipt(
                        contract.deploy(
                            transaction = {'from': owner_address},
                            args = (station_address, 120)
                        )
                    )['contractAddress']

print "Contract deployed at " + contract.address

#Charging details
thread = threading.Thread()
charger = None
charging = False

#Event handlers
def updatePrice(event):
    d = datetime.datetime.now()
    delta = d - datetime.datetime(d.year, 1, 1)
    nominal = 7.69 + math.sin(2*math.pi*float(delta.days)/365.25)#0.01 Euro/kWh
    eurToEther = 1/82.5470 #Ether/Euro
    converted = 0.01*nominal*eurToEther/(1000*3600)#Ether/J
    contract.transact().update(eth_utils.to_wei(converted,'ether'))

def chargeDeposited(event):
    args = event['args']
    print str(args['from']) + " deposit:\t" + str(args['value']) + " Wei"

def priceUpdated(event):
    args = event['args']
    print "New price:\t" + str(eth_utils.from_wei(args['price'],'ether')*1000*3600) + " Ether/kWh"

def stateChanged(event):
    args = event['args']
    print "State change:\t" + str(args['from']) + "\t==>\t" + str(args['to'])

def updatePower(charger,t0,sleepTime):
    global charging
    print charger + " charging..."
    while (charging):
        t1 = time.clock()
        delta = t1-t0
        p = power(t1-t0,130,400,300)
        contract.transact().updatePower(int(math.ceil(p)))
        print "Consuming at " + str(p) + " W"
        time.sleep(sleepTime)

def charging(event):
    global charger
    global charging
    global thread
    args = event['args']
    charger = args['charger']
    charging = True
    thread = threading.Thread(target=updatePower, args=(str(charger),time.clock(),6))
    thread.start()

def stop_charging(event):
    global charging
    global thread
    charging = False
    thread.join()
    print "Charging stopped"
    charger = None

def power(time, RC, Vs, i0):
    voltage = Vs*(1 - math.exp(-time/RC))
    current = i0*math.exp(-time/float(RC))
    return voltage*current

#Filters
filters = {
    "chargeDeposited": contract.on("chargeDeposited", None, chargeDeposited),
    "fetchPrice": contract.on("fetchPrice", None, updatePrice),
    "stateChanged": contract.on("stateChanged", None, stateChanged),
    "priceUpdated": contract.on("priceUpdated", None, priceUpdated),
    "charging": contract.on("charging", None, charging),
    "stopCharging": contract.on("chargingStopped", None, stop_charging)
    }

#Exit clean up
def clean_up():
    for fltr in filters:
        fltr.stopWatching()

#Testing
user = web.eth.accounts[1]
contract.transact({'from': user, 'value': eth_utils.to_wei(1,'ether')}).depositCharge()
time.sleep(10)
contract.transact({'from': user}).notifyCharge()
time.sleep(10)
contract.transact({'from': user}).startCharging()
time.sleep(120)
contract.transact({'from': user}).stopCharging()
time.sleep(10)
contract.transact({'from': user}).withdraw()
time.sleep(10)

