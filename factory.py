from solc import compile_files
from web3.contract import Contract
from web3 import Web3
from web3.providers.rpc import HTTPProvider

def build(contractName, source, contractPath, web):
    compiled = compile_files([source])
    abi = compiled[contractPath]['abi']
    bin_compiled = compiled[contractPath]['bin']
    bin_runtime = compiled[contractPath]['bin-runtime']

    contract = Contract.factory(web,
                                contract_name = contractName,
                                abi = abi,
                                bytecode = bin_compiled,
                                bytecode_runtime = bin_runtime)
    return contract

def buildAndDeploy(contractName, source, contractPath, web, *args, **kwargs):
    contract = build(contractName, source, contractPath, web)
    contract.address = contract.web3.eth.getTransactionReceipt(
        contract.deploy(kwargs, args)
        )['contractAddress']
    return contract

def getWeb(url="http://localhost:8545"):
    return Web3(HTTPProvider(url))

def getAccounts(web3):
    return web3.eth.accounts
