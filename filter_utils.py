import web3, time, eth_utils

def getTxEvent(fltr, txHash, numReq, sleepTime):
    for k in range(0, numReq):
        log = fltr.get()
        for event in log:
            if txHash == event['transactionHash']:
                return event
        time.sleep(sleepTime)
    return []



def getDeepEvent(fltr, addr_hash, numReq, sleepTime):
    for k in range(0,numReq):
        log = fltr.get()
        for event in log:
            args = event['args']
            if args['hash'] == addr_hash:
                return event
        time.sleep(sleepTime)
    return []

