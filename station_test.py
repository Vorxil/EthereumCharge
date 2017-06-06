from station import Station
from user import User
from factory import getWeb
import unittest
from subprocess import Popen, CREATE_NEW_PROCESS_GROUP
from time import sleep
from eth_utils import to_wei, from_wei
from filter_utils import getTxEvent
from decimal import Decimal
from psutil import Process, wait_procs

proc = None

def setUpModule():
    global proc
    proc = Popen('testrpc', shell=True,
                 creationflags = CREATE_NEW_PROCESS_GROUP)
    sleep(5)

def tearDownModule():
    global proc
    sleep(5)
    parent = Process(proc.pid)
    children = parent.children(recursive=True)
    for child in children:
        child.kill()
    gone, sill_alive = wait_procs(children, timeout=5)
    parent.kill()
    parent.wait(5)

class TestStation(unittest.TestCase):

    def setUp(self):
        self.web = getWeb()
        self.accounts = self.web.eth.accounts
        self.station_account = self.accounts[0]
        self.owner_account = self.accounts[1]
        self.user_account = self.accounts[2]
        self.web.eth.defaultAccount = self.station_account
        self.assertNotEqual(self.station_account, self.owner_account)
        self.assertNotEqual(self.station_account, self.user_account)
        self.assertNotEqual(self.user_account, self.owner_account)

    def test_station_deploy(self):
        station = Station.factoryDeploy(self.station_account,
                                        self.owner_account,
                                        60,
                                        self.web)
        self.assertIsInstance(station, Station, "Should be a station")
        self.assertIsNotNone(station.contract, "Should have a contract")
        self.assertIsNotNone(station.contract.address, "Contract should have an address")
        self.assertTrue(self.web.isAddress(station.contract.address), "Address should be valid")
        station.tearDownFilters()

    def test_station_dry_factory(self):
        station = Station.factoryDeploy(self.station_account,
                                        self.owner_account,
                                        60,
                                        self.web)
        other_station = Station.factory(station.contract.address, self.web)
        self.assertIsInstance(other_station, Station, "Should be a station")
        self.assertEqual(station.contract.address, other_station.contract.address, "Addresses should be identical")
        self.assertEqual(station.contract.abi, other_station.contract.abi, "Contracts should have the same ABI")
        station.tearDownFilters()
        other_station.tearDownFilters()

class TestUser(unittest.TestCase):

    def setUp(self):
        self.web = getWeb()
        self.accounts = self.web.eth.accounts
        self.station_account = self.accounts[0]
        self.owner_account = self.accounts[1]
        self.user_account = self.accounts[2]
        self.web.eth.defaultAccount = self.station_account
        self.assertNotEqual(self.station_account, self.owner_account)
        self.assertNotEqual(self.station_account, self.user_account)
        self.assertNotEqual(self.user_account, self.owner_account)
        
    def test_init(self):
        station = Station.factoryDeploy(self.station_account,
                                        self.owner_account,
                                        60,
                                        self.web)
        user = User(self.web)
        self.assertEqual(station.contract.abi, user.contract.abi, "Contracts should have the same ABI")
        station.tearDownFilters()

    def test_set_account(self):
        user = User(self.web)
        self.assertNotEqual(user.contract.web3.eth.defaultAccount, self.user_account, "User account shouldn't be set")
        user.setAccount(self.user_account)
        self.assertEqual(user.contract.web3.eth.defaultAccount, self.user_account, "User account should have been set")

    def test_register_station(self):
        station = Station.factoryDeploy(self.station_account,
                                        self.owner_account,
                                        60,
                                        self.web)
        second_station = Station.factoryDeploy(self.station_account,
                                        self.owner_account,
                                        60,
                                        self.web)
        user = User(self.web)
        self.assertIsNone(user.contract.address, "Should have no initial address")
        user.registerStation(station.contract.address)
        self.assertEqual(user.contract.address, station.contract.address, "Registered address should match")
        user.registerStation(second_station.contract.address)
        self.assertEqual(user.contract.address, second_station.contract.address, "Should be able to change to another station if one is already registered")
        station.tearDownFilters()
        second_station.tearDownFilters()

    def test_balance(self):
        user = User(self.web)
        user.setAccount(self.user_account)
        self.assertEqual(from_wei(user.balance(),'ether'), 100, "Unused account should have 100 ethers according to documentation of testrpc")

    def test_deposit(self):
        user = User(self.web)
        user.setAccount(self.user_account)
        station = Station.factoryDeploy(self.station_account,
                                        self.owner_account,
                                        60,
                                        self.web)
        user.registerStation(station.contract.address)
        startingAmount = Decimal(user.balance())
        gasUsed = user.contract.estimateGas().deposit()
        gasCost = Decimal(gasUsed)*Decimal(self.web.eth.gasPrice)
        fltr = user.contract.on("chargeDeposited", None)
        txHash = user.deposit('1')
        event = getTxEvent(fltr, txHash, 10, 1)
        fltr.running = False
        fltr.stopped = True
        self.web.eth.uninstallFilter(fltr.filter_id)
        self.assertTrue(len(event) > 0, "Event chargeDeposited should have fired")
        print event
        balance = Decimal(user.balance())
        print startingAmount
        print gasCost
        print to_wei(1,'ether')
        print balance
        station.tearDownFilters()
        self.assertEqual(startingAmount, balance + gasCost + Decimal(to_wei(1,'ether')), "Balance should be maintained")
        
        
        
        
if __name__ == '__main__':
    unittest.main()
