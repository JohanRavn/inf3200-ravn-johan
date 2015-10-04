import sys
import getopt
import threading
import signal
import socket, errno
import httplib
import random
import string

import time
import os
import logging
import hashlib
import math
from fingertable import FingerTable
from backendserver import BackendHTTPServer, BackendHttpHandler

MAX_CONTENT_LENGHT = 1024		# Maximum length of the content of the http request (1 kilobyte)
MAX_STORAGE_SIZE = 104857600	# Maximum total storage allowed (100 megabytes)

httpdServeRequests = True

# should setup handle predeccesor
# should handle join, leave
# should handle initalizing of first node
# should have a fingerprint table
# find successor
#
mEntries = 25

# class for communcication to nodes
class NodeCommunication:
	def start_get_conn(self, code, hostName, portNumber, key):
		conn = httplib.HTTPConnection(hostName, portNumber)
		# Try to start connection, if it fails wait 500 ms and try again
		while True:
			try:
				conn.request(code, key)
				break
			# Catch erno 111, happens when nodes joins the network too fast
			# The server on the recieving node have not been able to set up its server fast enough

			except socket.error as e:
				if e.errno == errno.ECONNREFUSED:
					conn.close
					time.sleep(0.5)
					conn = httplib.HTTPConnection(hostName, portNumber)
				else:
					raise socket.error

		response = conn.getresponse()
		if response.status != 200:
			logger.error("Response from get_successor failed")
			return False
		return response.read()

	# Start a put connection instead of the get
	def start_put_conn(self, code, hostName, portNumber, key, value):
		conn = httplib.HTTPConnection(hostName, portNumber)

		while True:
			try:
				conn.request(code, key, value)
				break
			except socket.error as e:
				if e.errno == errno.ECONNREFUSED:
					conn.close
					time.sleep(0.5)
					conn = httplib.HTTPConnection(hostName, portNumber)
				else:
					raise socket.error

		response = conn.getresponse()

		if response.status != 200:
			logger.error("Response from get_successor failed")
			return False
		return True

	def update_others_finger_table(self, hostName, portNumber, identity, stopIdentity):
		self.start_put_conn("UPDATE_FINGER_TABLE", hostName, portNumber, identity, stopIdentity)

	def update_predecessor(self, hostName, portNumber, identity, newIdentity):
		self.start_put_conn("UPDATE_PREDECESSOR", hostName, portNumber, identity, newIdentity)

	def put_value(self, hostName, portNumber, key, value):
		self.start_put_conn("PUT_VALUE", hostName, portNumber, key, value)

	def get_value(self, hostName, portNumber, key):
		return self.start_get_conn("GET_VALUE", hostName, portNumber, key)

	def request_successor(self, hostName, portNumber, identifier):
		return self.start_get_conn("GET_SUCCESSOR", hostName, portNumber, identifier)

# Node operations, are operations that change the state of the node
class NodeOperations(NodeCommunication):
	# operation when recieving a get form the frontend
	def frontend_get_value(self, key):
		keyIdentifier = int("0x"+hashlib.sha1(key).hexdigest(),0) % pow(2,mEntries)

		identifier = keyIdentifier
		# if identifier is equal to my own just put it in my map
		if identifier == self.identifier:
			return self.keyValueMap.get(str(identifier))

		# if identfier is smaller than my own, add 2^5 +1
		if self.identifier > identifier:
			identifier += pow(2,mEntries)+1
		# check corner cases
		identity = self.check_corner_cases(identifier)
		# Send to scuccessor
		if identity is None:
			identity = self.request_successor(self.fingerTable.get_succ_identity(), self.portNumber, str(identifier))

		# If key is in my own map
		if identity == self.identity:
			return self.keyValueMap.get(str(keyIdentifier))
		# Send a get value to the node that has the key
		else:
			return self.get_value(identity, self.portNumber, str(keyIdentifier))
		return False



	def frontend_put_value(self, key, value, size):
		keyIdentifier = int("0x"+hashlib.sha1(key).hexdigest(),0) % pow(2,mEntries)

		identifier = keyIdentifier
		if identifier == self.identifier:
			self.keyValueMap[str(identifier)] = value
			return

		if self.identifier > identifier:
			identifier += pow(2,mEntries)+1
		identity = self.check_corner_cases(identifier)
		if identity is None:
			identity = self.request_successor(self.fingerTable.get_succ_identity(), self.portNumber, str(identifier))

		if identity == self.identity:
			self.keyValueMap[str(keyIdentifier)]= value
		else:
			self.put_value(identity, self.portNumber, str(keyIdentifier), value)

	# Put value in map
	def operation_put_value(self, key, value, size):
		self.keyValueMap[key] = value
		self.size += size

	# Get value from map
	def operation_get_value(self, key):
		return self.keyValueMap.get(key)

	# return s the successor of the identifier
	def operation_get_successor(self, identifier):
		identity = self.check_corner_cases(identifier)
		# if my identifier is bigger than the request, return my identifier
		# lots of if tests to make sure the message is not passed to the first node that sent the message
		# maybe use threading to reduce if testing
		if identity is None:
			if self.identifier >= identifier:
				return self.identity
			else:
				if self.fingerTable.get_succ_identifier() >= identifier:
					return self.fingerTable.get_succ_identity()
				else:
					return self.request_successor(self.fingerTable.get_succ_identity(), self.portNumber, str(identifier))
				return self.request_successor(self.fingerTable.get_succ_identity(), self.portNumber, str(identifier))
		else:
			return identity

	# check if the successor of the newly joind node is a finger in my table
	# request new finger if it is
	def operation_update_finger_table(self, identity, stopIdentity):

		for i in range(1, mEntries):
			if identity == self.fingerTable.get_finger_identity(i):

				identifier = self.fingerTable.table[i][0]
				if self.identifier > identifier:
						identifier += pow(2,mEntries)+1
				newIdentity = self.check_corner_cases(identifier)
				if newIdentity is None:
					newIdentity = self.request_successor(self.fingerTable.get_succ_identity(), self.portNumber, str(identifier))
				self.fingerTable.new_entry(i, self.identifier, newIdentity)

		# if the message has gone through all, stop sending

		if self.fingerTable.get_succ_identity() != stopIdentity:
			self.update_others_finger_table(self.fingerTable.get_succ_identity(), self.portNumber, identity, stopIdentity)

		# Update my successor to the newly joined node
	def	operation_update_predecessor(self,oldIdentity, newIdentity):
		if(self.fingerTable.get_succ_identity() == oldIdentity):
			self.fingerTable.new_entry(0, self.identifier, newIdentity)
		else:
			self.update_predecessor(self.fingerTable.get_succ_identity(), self.portNumber, oldIdentity, newIdentity)

		# logging
	def log_status(self):
		#logger.info("my identity = " + self.identity)
		for i in range(0,mEntries):
			#pass
			logger.info("my successor = "+ str(self.fingerTable.table[i]))
		logger.info("map = \n" + str(self.keyValueMap))
		logger.info("size is %d", self.size)


# Main node class, initalizing and joining
class Node(NodeCommunication, NodeOperations):

	def __init__(self, portNumber):
		self.portNumber = portNumber
		self.keyValueMap = dict()
		self.size = 0
		self.identity = socket.gethostname().rstrip(".local")

		self.identifier = int("0x"+hashlib.sha1(self.identity).hexdigest(),0) % pow(2,mEntries)

		# initalize fingertable
		self.fingerTable = FingerTable(mEntries)

	def join(self, predecessor):
		# Join the system. Find my place
		# corner case for first node
		if predecessor == socket.gethostname().rstrip(".local"):
			for i in range(0,mEntries):
				self.fingerTable.new_entry(i, self.identifier, self.identity)
			return

		preIdentifier = int("0x"+hashlib.sha1(predecessor).hexdigest(),0) % pow(2,mEntries)
		identifier = self.identifier
		if preIdentifier > identifier:
			identifier += pow(2, mEntries)+1

		# find my place in the system
		successor = self.request_successor(predecessor, self.portNumber, str(identifier))
		# Calculate first finger and join the system
		self.fingerTable.new_entry(0,self.identifier, successor)
		# Update the predecessor
		self.update_predecessor(self.fingerTable.get_succ_identity(), self.portNumber, self.fingerTable.get_succ_identity(), self.identity)
		# Calculate the rest of the fingers
		self.find_fingers(self.identifier, self.portNumber)
		# send message to all others nodes, that they should update their finger table
		self.update_others_finger_table(self.fingerTable.get_succ_identity(), self.portNumber, self.fingerTable.get_succ_identity(), self.identity)

	# Calculate and find the fingers for the finger table
	def find_fingers(self, identifier, portNumber):
		for i in range(2, mEntries + 1):
			value = int((identifier + pow(2,i-1)) % pow(2,mEntries))

			if value < identifier:
				value += pow(2,mEntries)+1
			successor = self.check_corner_cases(value)
			if successor is None:
				successor = self.request_successor(self.fingerTable.get_succ_identity(), portNumber, str(value))
			self.fingerTable.new_entry(i-1, identifier, successor)

	# Function to check corner cases, very important when we pass the zero identifier
	# might be easier with threaded connection
	def check_corner_cases(self, identifier):
		# only one node
		if self.fingerTable.get_succ_identifier() == self.identifier:
			identity = self.fingerTable.get_succ_identity()

					#return old finger
			return identity

		if self.identifier > self.fingerTable.get_succ_identifier():
			if identifier > pow(2,mEntries):
				# well....
				identifier -=  (pow(2,mEntries)+1)
			else:
				if self.identifier >= identifier:
					return self.identity
			if self.identifier > identifier:
				if self.fingerTable.get_succ_identifier() > identifier:
					return self.fingerTable.get_succ_identity()
				else:
					return self.request_successor(self.fingerTable.get_succ_identity(), self.portNumber, str(identifier))
			else:
				return self.fingerTable.get_succ_identity()
		return None
	# find my successor

if __name__ == '__main__':

	logger = logging.getLogger('logg')
	#idividual logs
	#hdlr = logging.FileHandler('mandatory-master/assignment1/src/precode/logs/logging'+socket.gethostname().rstrip(".local")+'.log', mode="w")
	hdlr = logging.FileHandler('logging'+socket.gethostname().rstrip(".local")+'.log', mode="w")

	#hdlr = logging.FileHandler('mandatory-master/assignment1/src/precode/logs/logging.log', mode="w")

	formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
	hdlr.setFormatter(formatter)
	logger.addHandler(hdlr)
	logger.setLevel(logging.DEBUG)
	logger.info('Started')


	try:
		optlist, args = getopt.getopt(sys.argv[1:],'x')
	except getopt.GetoptError:
		logger.info("Options error")
		sys.exit(2)

	predecessor = args[0]

	httpserver_port = 8003
	node = Node(httpserver_port)
	node.join(predecessor)
	# Start the server which handles incomming requests
	try:
		httpd = BackendHTTPServer(("",httpserver_port), BackendHttpHandler, node)
		logger.info("successfully started server")
		server_thread = threading.Thread(target = httpd.serve)
		server_thread.daemon = True
		server_thread.start()

		def handler(signum, frame):
			logger.info("Stopping http server...")
			httpd.stop()
		signal.signal(signal.SIGINT, handler)

	except:
		logger.info("Error: unable to http server thread")

	time.sleep(30)
	node.log_status()
	time.sleep(5)
	server_thread.join(5)

	# Wait for server thread to exit
	#
