from factory import build, getWeb
from web3.eth import is_address
from decimal import Decimal
from re import match
from eth_utils import from_wei, to_wei
from functools import wraps

def connected():
    def connected_wrapper(f):
        @wraps(f)
        def connected_decorator(self, *f_args, **f_kwargs):
            if self.isConnected() == False:
                raise NoConnectionError
        
            if self.contract.address == None:
                raise NoStationError

            f(self, *f_args, **f_kwargs)

        return connected_decorator
    return connected_wrapper

class User:
    #Variables
    CONTRACT_FILE = ".\\chargeStation.sol"
    CONTRACT_PATH = ".\\chargeStation.sol:ChargeStation"
    CONTRACT_NAME = "ChargeStation"

    NUMBER_REGEX = r"^((0|([1-9][0-9]*))|((0|([1-9][0-9]*))\.[0-9]+))$"

    contract = None

    #Functions
    def __init__(self, web3=getWeb()):
        if web3 == None:
            raise ValueError("No Web!")
        self.contract = build(self.CONTRACT_NAME, self.CONTRACT_FILE, self.CONTRACT_PATH, web3)

    def setAccount(self, account_address):
        if is_address(account_address):
            self.contract.web3.eth.defaultAccount = account_address
            return True
        return False

    def registerStation(self,station_address):
        if is_address(station_address):
            self.contract.address = station_address
            return True
        return False

    def balance(self):

        if self.isConnected() == False:
            raise NoConnectionError
        
        return Decimal(self.contract.web3.eth.getBalance(self.contract.web3.eth.defaultAccount))

    @connected()
    def deposit(self, amount):

        if match(self.NUMBER_REGEX, amount) == None:
            raise ValueError(format("%s is not a number", amount))

        d = to_wei(Decimal(amount), 'ether')

        price = Decimal(self.contract.web3.eth.gasPrice)
        gas = Decimal(self.contract.estimateGas({'value' : to_wei(d,'ether')}).deposit())        
        balance = self.balance()

        if d + gas*price > balance:
            raise NotEnoughFundsError

        return self.contract.transact({'value' : d}).deposit()

    @connected()
    def withdraw(self):
        return self.contract.transact().withdraw()
        

    @connected()
    def notify(self):
        return self.contract.transact().notify()


    @connected()
    def start(self):
        return self.contract.transact().start()

    @connected()
    def stop(self):
        return self.contract.transact().stop()

    @connected()
    def cancel(self):
        return self.contract.transact().cancel()

    @connected()
    def getHash(self):
        return self.contract.call().getHash(self.web3.eth.defaultAccount)

    def isConnected(self):
        return self.contract.web3.isConnected()

        

class NoStationError(Exception):
    def __str__(self):
        return "No Station is registered!"

class NoConnectionError(Exception):
    def __str__(self):
        return "No Station is registered!"

class NotEnoughFundsError(Exception):
    def __str__(self):
        return "Account doesn't have enough funds!"
