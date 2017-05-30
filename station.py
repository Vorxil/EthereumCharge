from factory import buildAndDeploy, getWeb
from web3.contract import Contract
from datetime import datetime
from requests import get, Response, HTTPError, RequestException
from decimal import Decimal
from eth_utils import to_wei
from math import sin, pi, exp, log
from threading import Thread
from time import sleep, clock

class NoJsonException(RequestException):
    """The response has no json!"""

class InvalidResponseException(RequestException):
    """Json response does not match expectations"""

class PowerUpdateDaemon():
    running = False
    thread = None
    up_period = 1
    up_fun = None
    up_args = ()
    up_kwargs = {}

    def __init__(self, update_period, update_fun, *update_args, **update_kwargs):
        up_fun = update_fun
        up_args = update_args
        up_kwargs = update_kwargs
        up_period = update_period

        thread = Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def run(self):
        self.running = True

        while self.running == True :
            up_fun(up_args, up_kwargs)
            sleep(up_period)

    def stop(self):
        if self.running == True:
            self.running = False
            
    

class Station:
    #CONSTS
    CONTRACT_FILE = ".\\chargeStation.sol"
    CONTRACT_PATH = ".\\chargeStation.sol:ChargeStation"
    CONTRACT_NAME = "ChargeStation"

    ETH_PRICE_URL = "https://coinmarketcap-nexuist.rhcloud.com/api/eth"

    #Variables
    contract = None
    daemon = None

    #Constructor
    def __init__(self, owner_account, prep_duration_seconds=60, web3=getWeb()):
        if web3 == None:
            raise ValueError("No Web!")
        elif not web3.isAddress(owner_account):
            raise ValueError("No Account!")
        elif prep_duration_seconds == None:
            raise ValueError("No prep duration!")
        elif not isinstance(prep_duration_seconds, (int, long)):
            raise ValueError("Prep duration not an integer")
        elif prep_duration_seconds <= 0:
            raise ValueError("Prep duration must be positive and non-zero (seconds)")

        self.contract = buildAndDeploy(self.CONTRACT_NAME, self.CONTRACT_FILE, self.CONTRACT_PATH, web3,
                                       owner_account, prep_duration_seconds)


    #Daemon function
    def updatePower(self,t0,sleepTime):

        def power(time, charge_voltage, battery_voltage, rel_voltage_bound, battery_capacity, resistance):
            nominalPower = (charge_voltage*(charge_voltage - (1-rel_voltage_bound)*battery_voltage))/float(resistance)
            powerFactor = exp(-((1+rel_voltage_bound)*battery_voltage/(float(resistance*capacity*3600)))*time)
        return nominalPower*powerFactor

        charge_voltage = 500#Volts
        battery_voltage = 300#Volts
        rel_voltage_bound = 0.2# 20% operating voltage max deviation from nominal
        battery_capacity = 200#Amp-hours
        battery_resistance = 1.696#Ohm, internal resistance only
        #35 min charge time at 500 volts and 300 A
    
        t1 = clock()
        delta = t1-t0
        p = power(t1-t0,
                  charge_voltage,
                  battery_voltage,
                  rel_voltage_bound,
                  battery_capacity,
                  battery_resistance)
        self.contract.transact().updatePower(int(math.ceil(p)))

    #Event Handlers
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

        self.contract.transaction().updatePrice(converted, event['args']['asker'])

    
