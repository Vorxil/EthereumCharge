import solc, web3

def build(contractName, source, contractPath, web):
    compiled = solc.compile_files([source])
    abi = compiled[contractPath]['abi']
    bin_compiled = compiled[contractPath]['bin']
    bin_runtime = compiled[contractPath]['bin-runtime']

    contract = web3.contract.Contract.factory(web,
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
    return web3.Web3(web3.providers.rpc.HTTPProvider(url))

w = getWeb()
c = buildAndDeploy("Owned", ".\\owned.sol", ".\\owned.sol:Owned", w)
