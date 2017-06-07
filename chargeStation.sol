pragma solidity ^0.4.11;

import "owned.sol";

contract ChargeStation is Owned {
	
	mapping(address => uint) balances;
	address charger;
	address station;
	enum State { Idle, Notified, Charging }
	State state;
	uint chargeStart;
	uint chargeIntervalStart;
	uint chargeIntervalEnd;
	uint chargeEnd;
	uint prepStart;
	uint prepDuration;
	uint totalCharge;
	uint price;
	uint oldPower;
	bool priceLocked;
	
	function ChargeStation(address _station, uint _prepDuration) {
		state = State.Idle;
		charger = address(0);
		chargeStart = 0;
		chargeEnd = 0;
		totalCharge = 0;
		price = 0;
		prepStart = 0;
		prepDuration = _prepDuration*(1 seconds);
		station = _station;
		priceLocked = false;
	}
	
	modifier onlyStation() {
		if (msg.sender == station) {
			_;
		}
	}
	
	modifier onlyCharger() {
		if (msg.sender == charger) {
			_;
		}
	}
	
	event priceUpdated(uint price, bytes32 hash);
	event chargeDeposited(address from, uint value);
	event fetchPrice(bytes32 asker);
	event stateChanged(State from, State to);
	event charging(address charger, uint time);
	event notified(address notifier, uint time);
	event consume(address charger, uint consume);
	event chargingStopped(address charger, uint time, uint totalCharge, uint cost);
	event killed();

	function getHash(address from) returns (bytes32) {
		return keccak256(keccak256(from), station);
	}
	
	function getStateInt() returns (uint8) {
		return uint8(state);
	}
	
	function getCharger() returns (address) {
		return charger;
	}
	
	function update(uint _price, bytes32 asker) onlyStation returns (bool){
		uint time = now;
		if (state == State.Idle) {
			price = _price;
			priceLocked = false;
			charger = address(0);
			priceUpdated(price, keccak256(asker,msg.sender));
			return true;
		}
		else if (state == State.Notified) {
			if (time <= prepStart + prepDuration) {
				price = _price;
				prepStart = now;
				priceLocked = true;
				priceUpdated(price, keccak256(asker, msg.sender));
				return true;
			}
			else if (time > prepStart + prepDuration) {
				price = _price;
				state = State.Idle;
				priceLocked = false;
				charger = address(0);
				priceUpdated(price, keccak256(asker, msg.sender));
				stateChanged(State.Notified, State.Idle);
				return true;
			}
		}
		return false;
	}
	
	function notify() returns (bool){
		if (state == State.Idle) {
			prepStart = now;
			state = State.Notified;
			charger = msg.sender;
			stateChanged(State.Idle, State.Notified);			
			fetchPrice(keccak256(msg.sender));
			notified(charger,prepStart);
			return true;
		} else if (state == State.Notified && now > prepStart + prepDuration) {
			prepStart = now;
			charger = msg.sender;
			fetchPrice(keccak256(msg.sender));
			notified(charger,prepStart);
			return true;
		}
		return false;
	}
	
	function cancel() onlyCharger returns (bool) {
		require(state == State.Notified);
		state = State.Idle;
		charger = address(0);
		stateChanged(State.Notified, State.Idle);
		return true;
	}
	
	function start() onlyCharger returns (bool) {
		uint time = now;
		if (state == State.Notified) {
			if (time < prepStart + prepDuration) {
				totalCharge = 0;
				chargeStart = now;
				oldPower = 0;
				chargeIntervalStart = now;
				state = State.Charging;
				stateChanged(State.Notified, State.Charging);
				charging(charger, chargeStart);
				return true;
			} else {
				charger = address(0);
				state = State.Idle;
				stateChanged(State.Notified, State.Idle);
				return false;
			}
		} else {
			return false;
		}
	}
	
	function updatePower(uint power) onlyStation returns (bool) {
		if (state == State.Charging) {
			chargeIntervalEnd = now;
			totalCharge += ((chargeIntervalEnd - chargeIntervalStart)*(oldPower + power))/2;
			oldPower = power;
			chargeIntervalStart = chargeIntervalEnd;
			consume(charger, totalCharge);
			if (totalCharge*price >= balances[charger]) {
				chargeEnd = now;
				balances[owner] += balances[charger];
				balances[charger] = 0;
				chargingStopped(charger, chargeEnd, totalCharge, totalCharge*price);
				charger = address(0);
				state = State.Idle;
				stateChanged(State.Charging, State.Idle);
			}				
			return true;
		}
		else {
			return false;
		}
	}
	
	function stop() onlyCharger returns (bool){
		if (state == State.Charging) {
			chargeEnd = now;
			uint cost = totalCharge*price;
			uint amount = balances[charger];
			if (cost > amount) {
				balances[owner] = amount;
				balances[charger] = 0;
			}
			else {
				balances[owner] = cost;
				balances[charger] = amount - cost;
			}
			state = State.Idle;
			charger = address(0);
			stateChanged(State.Charging, State.Idle);
			chargingStopped(charger, chargeEnd, totalCharge, cost);
			return true;
		}
		return false;
	}
	
	function getBalance() returns (uint) {
		return balances[msg.sender];
	}
		
	
	function deposit() payable {
		require(msg.sender != address(this));
		require(msg.sender != address(0));
		require(!(msg.sender == charger && state == State.Charging));
		
		balances[msg.sender] += msg.value;
		
		chargeDeposited(msg.sender, msg.value);
	}
	
	function withdraw() returns (bool) {
		require(!(charger == msg.sender && state == State.Charging));
		uint amount = balances[msg.sender];
		if (amount > 0) {

			balances[msg.sender] = 0;
			if (!msg.sender.send(amount)) {
				balances[msg.sender] = amount;
				return false;
			}
		}
		return true;
	}
}