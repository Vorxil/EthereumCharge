from factory import build, buildAndDeploy, getWeb
from web3.contract import Contract
from web3 import Web3
from datetime import datetime
from requests import get, Response, HTTPError, RequestException
from decimal import Decimal
from eth_utils import to_wei, from_wei
from math import sin, pi, exp, log, ceil
from threading import Thread
from time import sleep, clock
from user import NoConnectionError, connected, hasAddress
from filter_utils import getDeepEvent
import atexit

class NoJsonException(RequestException):
    """The response has no json!"""

class InvalidResponseException(RequestException):
    """Json response does not match expectations"""

class EthException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg
    
class ChargingException(EthException):
    """Something's gone wrong with the charging"""

class StateException(EthException):
    """Unexpected state"""

class PowerUpdateDaemon():
    running = False
    thread = None
    up_period = 1
    up_fun = None
    up_args = ()
    up_kwargs = {}

    def __init__(self, update_period, update_fun, *update_args, **update_kwargs):
        self.up_fun = update_fun
        self.up_args = update_args
        self.up_kwargs = update_kwargs
        self.up_period = update_period

        self.thread = Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()

    def run(self):
        self.running = True

        while self.running == True :
            self.up_fun(*self.up_args, **self.up_kwargs)
            sleep(self.up_period)

    def stop(self):
        if self.running == True:
            self.running = False
            

def enum(**enums):
    return type('Enum', (), enums)

class Station:
    #CONSTS
    CONTRACT_FILE = ".\\chargeStation.sol"
    CONTRACT_PATH = ".\\chargeStation.sol:ChargeStation"
    CONTRACT_NAME = "ChargeStation"

    ETH_PRICE_URL = "https://coinmarketcap-nexuist.rhcloud.com/api/eth"

    #State Enum
    states = enum(IDLE=0, NOTIFIED=1, CHARGING=2)
    FILTER_NAMES = enum(FETCH="fetch", START="start", STOP="stop")

    #Variables
    contract = None
    daemon = None
    filters = {}

    #Constructor
    def __init__(self, contract):    
        self.contract = contract

    #Factories
    @classmethod
    def factoryDeploy(cls, station_account, owner_account, prep_duration_seconds=60, web3=getWeb()):
        if web3 == None or not isinstance(web3, Web3):
            raise ValueError("No Web!")
        elif web3.isConnected() == False:
            raise NoConnectionError
        elif not web3.isAddress(station_account):
            raise ValueError("Invalid Station Account!")
        elif not web3.isAddress(owner_account):
            raise ValueError("Invalid Owner Account!")
        elif prep_duration_seconds == None:
            raise ValueError("No prep duration!")
        elif not isinstance(prep_duration_seconds, (int, long)):
            raise ValueError("Prep duration not an integer")
        elif prep_duration_seconds <= 0:
            raise ValueError("Prep duration must be positive and non-zero (seconds)")
                
        station = cls(buildAndDeploy(cls.CONTRACT_NAME, cls.CONTRACT_FILE, cls.CONTRACT_PATH, web3,
                                  station_account, prep_duration_seconds,
                                  **{'from':owner_account}
                                  )
                   )

        station.setupFilters()
        return station
                        
        

    @classmethod
    def factory(cls, contract_address, web3=getWeb()):
        if web3 == None or not isinstance(web3, Web3):
            raise ValueError("No Web!")
        elif not web3.isAddress(contract_address):
            raise ValueError("Invalid address!")

        station = cls(build(cls.CONTRACT_NAME, cls.CONTRACT_FILE, cls.CONTRACT_PATH, web3))
        station.contract.address = contract_address

        station.setupFilters()
        return station
                              

    #Helpers
    @connected()
    @hasAddress()
    def getState(self):
        return self.contract.call().getStateInt()

    @connected()
    @hasAddress()
    def getHash(self, from_address):
        if self.contract.web3.isAddress(from_address):
            return self.contract.call().getHash(from_address)
        else:
            raise ValueError("Not an address")
    
    def isConnected(self):
        return self.contract.web3.isConnected()

    def setupFilters(self):
        self.addFilter(self.FILTER_NAMES.FETCH, "fetchPrice", self.fetchPrice)
        self.addFilter(self.FILTER_NAMES.START, "charging", self.startCharging)
        self.addFilter(self.FILTER_NAMES.STOP, "chargingStopped", self.stopCharging)

    def tearDownFilters(self):
        for key in self.filters.keys():
            fltr = self.filters.pop(key)
            if fltr.running == True:
                fltr.stopWatching()
            fltr.running = False
            fltr.stopped = True
            fltr.web3.eth.uninstallFilter(fltr.filter_id)

    #Daemon function
    @connected()
    @hasAddress()
    def updatePower(self,t0):

        def power(time, charge_voltage, battery_voltage, voltage_low, voltage_high, battery_capacity, resistance):
            nominalPower = (charge_voltage*(charge_voltage - voltage_low)/float(resistance))
            powerFactor = exp(-((voltage_high - voltage_low)/float(3600*battery_capacity*resistance))*time)
            return nominalPower*powerFactor

        charge_voltage = 500#Charger, 50 kW DC at 500 Volts and 100-130 Amps

        #Using battery specs from www.electricvehiclewiki.com/Battery_specs

        battery_voltage = 360#Volts, nominal
        voltage_high = 403.2#Volts, fully charged
        voltage_low = 307.2#Volts, effectively dead. Assumed from 3.2V Li-Ion cutoff voltage.
        battery_capacity = 66.7#Amp-hours, calculated from 24 kWh at 360 V
        battery_resistance = 1.4 #Ohms, effective resistance, calculated from charge time using circuit model

        #~40 min charge time using 50 kW DC charger at 500 V and 100-130 Amps
        
    
        t1 = clock()
        delta = t1-t0
        p = power(t1-t0,
                  charge_voltage,
                  battery_voltage,
                  voltage_low,
                  voltage_high,
                  battery_capacity,
                  battery_resistance)
        txHash = self.contract.transact().updatePower(int(ceil(p)))
        resp = self.contract.web3.eth.getTransactionReceipt(txHash)
        gas = Decimal(resp['gasUsed'])
        gasPrice = Decimal(self.contract.web3.eth.gasPrice)
        cost = from_wei(gas*gasPrice,'ether')
        print "Charging at " + str(p) + " W | Tx Cost:\t" + str(cost) + " Ether"
        

    #Event Handlers
    @connected()
    @hasAddress()
    def fetchPrice(self, event):
        d = datetime.now()
        delta = d - datetime(d.year, 1, 1)
        resp = get(self.ETH_PRICE_URL)
        if resp.status_code != 200:
            raise HTTPError(None, {'response': resp})
        elif resp.headers['content-type'] != 'application/json':
            raise NoJsonException(None, {'response': resp})
        json = resp.json()
        if 'price' not in json.keys() or 'eur' not in json['price'].keys():
            raise InvalidResponseException(None, {'response': resp})

        eur_to_eth = 1/Decimal(json['price']['eur'])
        
        nominal = 7.69 + sin(2*Decimal(pi)*Decimal(delta.days)/Decimal(365.25))#0.01 Euro/kWh
        converted = to_wei(Decimal(nominal)*eur_to_eth/Decimal(100000*3600), 'ether') #Convert 0.01 Euro/kWh to Wei/J

        self.contract.transact().update(converted, event['args']['asker'])

    @connected()
    @hasAddress()
    def startCharging(self, event):
        if self.states.CHARGING == self.getState():
            if self.daemon != None:
                raise ChargingException("Already Charging!")
            self.daemon = PowerUpdateDaemon(6, self.updatePower,(clock()))
        else:
            raise StateException("Expected CHARGING state")

    @connected()
    @hasAddress()
    def stopCharging(self, event):
        if self.states.IDLE == self.getState():
            if self.daemon != None:
                self.daemon.stop()
                self.daemon = None
            else:
                raise ChargingException("Not Charging!")
        else:
            raise StateException("Expected IDLE state")

    def addFilter(self, fltr_name, event, handler):
        if event in self.filters.keys():
            raise KeyError("Filter " + str(fltr_name) + " already exists!")
        self.filters[fltr_name] = self.contract.on(event, None, handler)

    def removeFilter(self, fltr_name):
        if fltr_name not in self.filters.keys():
            raise KeyError("Filter " + str(fltr_name) + " doesn't exist!")
        fltr = self.filters.pop(fltr_name)
        fltr.stopWatching()

    
