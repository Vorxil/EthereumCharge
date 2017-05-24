*** Settings ***
Suite Setup		Start TestRPC Server
Suite Teardown	Close TestRPC Server

*** Test Cases ***
User can register a station
	Given a user has a valid account
	And a station has a valid contract
	And contract is deployed
	Then the user can set that station as current
	
*** Keywords ***
Start TestRPC Server
	Start Process	testrpc