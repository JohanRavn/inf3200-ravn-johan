import BaseHTTPServer
import sys
import getopt
import threading
import signal
import socket
import httplib
import random
import string

MAX_CONTENT_LENGHT = 1024		# Maximum length of the content of the http request (1 kilobyte)
MAX_STORAGE_SIZE = 104857600	# Maximum total storage allowed (100 megabytes)

storageBackendNodes = list()
httpdServeRequests = True

class StorageServerFrontend:

	def __init__(self):
		self.map = dict()		# (Remove this) Dictionary which holds the key/value pairs
		self.size = 0


	def sendGET(self, key):
		node = random.choice(storageBackendNodes)
		print node
		try:
			conn = httplib.HTTPConnection(node, 8003)
			print "sending get to " + node + " with key " + key

			conn.request("GET", key)
			response = conn.getresponse()
			if response.status != 200:
				print response.reason
				return False

			return response.read()
		except:
			print "Unable to send GET request"
			return False
		return self.map.get(key)

	def sendPUT(self, key, value, size):
		self.size = self.size + size
		node = random.choice(storageBackendNodes)


		try:
			conn = httplib.HTTPConnection(node, 8003)
			print "sending put to " + node + " with key " + key + " and value "+ value

			conn.request("PUT", key, value)
			response = conn.getresponse()
			print response.status

		except:
			print "failed to send put"
			return False

		return True
		#self.map[key] = value


class FrontendHttpHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	global frontend
	frontend = StorageServerFrontend()
	# Returns the
	def do_GET(self):
		print "do_GET"
		key = self.path
		value = frontend.sendGET(key)

		if value is None:
			self.sendErrorResponse(404, "Key not found")
			return

		# Write header
		self.send_response(200)
		self.send_header("Content-type", "application/octet-stream")
		self.end_headers()

		# Write Body
		self.wfile.write(value)

	def do_PUT(self):
		contentLength = int(self.headers['Content-Length'])

		if contentLength <= 0 or contentLength > MAX_CONTENT_LENGHT:
			self.sendErrorResponse(400, "Content body to large")
			return

		frontend.size += contentLength
		if frontend.size > MAX_STORAGE_SIZE:
			self.sendErrorResponse(400, "Storage server(s) exhausted")
			return

		# Forward the request to the backend servers
		frontend.sendPUT(self.path, self.rfile.read(contentLength), contentLength)

		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()

	def sendErrorResponse(self, code, msg):
		self.send_response(code)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		self.wfile.write(msg)

class FrontendHTTPServer(BaseHTTPServer.HTTPServer):
	def server_bind(self):
		BaseHTTPServer.HTTPServer.server_bind(self)
		self.socket.settimeout(1)
		self.run = True

	def get_request(self):
		while self.run == True:
			try:
				#print "Recieve GET request from test script"
				sock, addr = self.socket.accept()
				sock.settimeout(None)
				return (sock, addr)
			except socket.timeout:
				if not self.run:
					raise socket.error

	def stop(self):
		self.run = False

	def serve(self):
		while self.run == True:
			self.handle_request()

class StorageServerTest:

	testsToRun = 100

	def __init__(self, url, portnumber):
		self.url = url
		self.portnumber = portnumber

	def generateKeyValuePair(self):
		key = ''
		value = ''

		for i in range(random.randint(10, 20)):
			key += random.choice(string.letters)

		for i in range(random.randint(20, 40)):
			value += random.choice('1234567890')

		return key, value

	def run(self):
		keyValuePairs = dict()

		# Generate random unique key, value pairs
		for i in range(self.testsToRun):
			while True:
				key, value = self.generateKeyValuePair()
				if key not in keyValuePairs:
					break
			keyValuePairs[key] = value

		# Call put to insert the key/value pairs
		for key, value in keyValuePairs.iteritems():
			if self.putTestObject(key, value) != True:
				print "Error putting", key, value
				return False

		# Validate that all key/value pairs are found
		for key, value in keyValuePairs.iteritems():
			if self.getTestObject(key, value) != True:
				print "Error getting", key, value
				return False

		return True


	def getTestObject(self, key, value):
		print "GET(key, value):", key, value

		try:
			conn = httplib.HTTPConnection("localhost", self.portnumber)
			conn.request("GET", key)
			response = conn.getresponse()
			if response.status != 200:
				#print response.reason
				return False

			retrievedValue = response.read()
		except:
			print "Unable to send GET request"
			return False

		if value != retrievedValue:
			print "Value is not equal to retrieved value", value, "!=", retrievedValue
			return False

		return True

	def putTestObject(self, key, value):
		#print "PUT(key, value):", key, value

		try:
			conn = httplib.HTTPConnection("localhost", self.portnumber)
			conn.request("PUT", key, value)
			response = conn.getresponse()

		except:
			return False

		return True

if __name__ == '__main__':

	run_tests = False
	httpserver_port = 8003

	try:
		optlist, args = getopt.getopt(sys.argv[1:], 'x', ['runtests', 'port='])
	except getopt.GetoptError:
		print sys.argv[0] + ' [--port portnumber(default=8000)] [--runtests] compute-1-1 compute-1-1 ... compute-N-M'

	if len(args) <= 0:
		print sys.argv[0] + ' [--port portnumber(default=8000)] [--runtests] compute-1-1 compute-1-1 ... compute-N-M'

	for opt, arg in optlist:
		if opt in ("-runtests", "--runtests"):
			run_tests = True
		elif opt in ("-port", "--port"):
			httpserver_port = int(arg)

	# Nodelist
	#for node in args:
	#	storageBackendNodes.append(node)
	#	print "Added", node, "to the list of nodes"
	f = open("hostfile")
	#lines = f.read()
	for node in f:
		#print lines
		storageBackendNodes.append(node.rstrip("\n"))
	print storageBackendNodes
	f.close
	# Start the webserver which handles incomming requests
	try:
		httpd = FrontendHTTPServer(("",httpserver_port), FrontendHttpHandler)
		server_thread = threading.Thread(target = httpd.serve)
		server_thread.daemon = True
		server_thread.start()

		def handler(signum, frame):
			print "Stopping http server..."
			httpd.stop()
		signal.signal(signal.SIGINT, handler)

	except:
		print "Error: unable to http server thread"

	# Run a series of tests to verify the storage integrity
	if run_tests:
		print "Running tests..."
		tests = StorageServerTest("localhost", httpserver_port)
		tests.run()

		httpd.stop()
	# Wait for server thread to exit
	server_thread.join(1000)
