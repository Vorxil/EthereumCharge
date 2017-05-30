import solc, web3, time, atexit, string, sys, math, datetime, decimal, threading, eth_utils, filter_utils

class station:

    contract = None
    web = None
    charging = False
    charger = None
    thread = None
    filters = {}

    def __init__(self, url, owner_account, station_account):
        
        filePath = ".\\chargeStation.sol"
        contractName = "ChargeStation"

        compiled = solc.compile_files([filePath])

        contract_abi = compiled[filePath + ":" + contractName]['abi']
        contract_bin = compiled[filePath + ":" + contractName]['bin']
        contract_bin_runtime = compiled[filePath + ":" + contractName]['bin-runtime']

        web = web3.Web3(web3.providers.rpc.HTTPProvider(url))

        connected = web.isConnected()

        print "Is connected to TestRPC: " + str(connected)
        if not connected:
            raise ValueError

        web.eth.defaultAccount = station_account

        contract = web3.contract.Contract.factory(web,
                                                  contract_name = contractName,
                                                  abi = contract_abi,
                                                  bytecode = contract_bin,
                                                  bytecode_runtime = contract_bin_runtime)

        contract.address = contract.web3.eth.getTransactionReceipt(
                                contract.deploy(
                                    transaction = {'from': owner_account},
                                    args = (station_account, 120)
                                )
                            )['contractAddress']

        print "Contract deployed at " + contract.address

        #Charging details
        self.thread = None
        self.charger = None
        self.chargeState = False

        self.contract = contract
        self.web = web

        self.setup_filters()

    #Event handlers
    def updatePrice(self, event):
        d = datetime.datetime.now()
        delta = d - datetime.datetime(d.year, 1, 1)
        nominal = 7.69 + math.sin(2*math.pi*float(delta.days)/365.25)#0.01 Euro/kWh
        eurToEther = 1/82.5470 #Ether/Euro
        converted = 0.01*nominal*eurToEther/(1000*3600)#Ether/J
        self.contract.transact().update(eth_utils.to_wei(converted,'ether'),
                                        event['args']['asker'])

    def chargeDeposited(self, event):
        args = event['args']
        print str(args['from']) + " deposit:\t" + str(args['value']) + " Wei"

    def priceUpdated(self, event):
        args = event['args']
        print "New price:\t" + str(eth_utils.from_wei(args['price'],'ether')*1000*3600) + " Ether/kWh"

    def stateChanged(self, event):
        args = event['args']
        print "State change:\t" + str(args['from']) + "\t==>\t" + str(args['to'])

    def updatePower(self,charger,t0,sleepTime):
        global charging
        print charger + " charging..."
        while (charging):
            t1 = time.clock()
            delta = t1-t0
            p = self.power(t1-t0,130,400,300)
            self.contract.transact().updatePower(int(math.ceil(p)))
            print "Consuming at " + str(p) + " W"
            time.sleep(sleepTime)

    def charging(self, event):
        global charger
        global charging
        global thread
        args = event['args']
        charger = args['charger']
        charging = True
        thread = threading.Thread(target=self.updatePower, args=(str(charger),time.clock(),6))
        thread.start()

    def stop_charging(self, event):
        global charging
        global thread
        charging = False
        thread.join()
        print "Charging stopped"
        charger = None

    def power(self, time, RC, Vs, i0):
        voltage = Vs*(1 - math.exp(-time/float(RC)))
        current = i0*math.exp(-time/float(RC))
        return voltage*current

    #Exit clean up
    def clean_up():
        for fltr in self.filters:
            fltr.stopWatching()

    #Filters
    def setup_filters(self):    
        self.filters = {
            "chargeDeposited": self.contract.on("chargeDeposited", None, self.chargeDeposited),
            "fetchPrice": self.contract.on("fetchPrice", None, self.updatePrice),
            "stateChanged": self.contract.on("stateChanged", None, self.stateChanged),
            "priceUpdated": self.contract.on("priceUpdated", None, self.priceUpdated),
            "charging": self.contract.on("charging", None, self.charging),
            "stopCharging": self.contract.on("chargingStopped", None, self.stop_charging),
            "killed": self.contract.on("killed", None, self.clean_up)
            }


web = web3.Web3(web3.providers.rpc.HTTPProvider("http://localhost:8545"))
s = station("http://localhost:8545", web.eth.accounts[1], web.eth.accounts[0])

while (True):
    inp = raw_input()
    if inp == 'q':
        s.clean_up()
    quit(0)
