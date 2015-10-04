import BaseHTTPServer

MAX_CONTENT_LENGHT = 1024		# Maximum length of the content of the http request (1 kilobyte)
MAX_STORAGE_SIZE = 104857600


# Handler for incomming request to a node
class BackendHttpHandler(BaseHTTPServer.BaseHTTPRequestHandler):

	# Used when the frontend sends a GET message
	def do_GET(self):
		key = self.path
		value = node.frontend_get_value(key)
		if value is None:
			self.sendErrorResponse(404, "Key not found")
			return

		self.send_response(200)
		self.send_header("Content-type", "application/octet-stream")
		self.end_headers()

		self.wfile.write(value)

    # Used when the frontend sends a PUT message
	def do_PUT(self):
		contentLength = int(self.headers['Content-Length'])


		if contentLength <= 0 or contentLength > MAX_CONTENT_LENGHT:
			self.sendErrorResponse(400, "Content body to large")
			return

		#node.size += contentLength
		if node.size > MAX_STORAGE_SIZE:
			self.sendErrorResponse(400, "Storage server(s) exhausted")
			return

		node.frontend_put_value(self.path, self.rfile.read(contentLength), contentLength)
		self.send_response(200)
		self.send_header("Content-type", "application/octet-stream")
		self.end_headers()

    # Used to handle gets between the nodes
	def do_GET_VALUE(self):
		key = self.path
		value = node.operation_get_value(key)
		if value is None:
			self.sendErrorResponse(404, "Key not found")
			return

		self.send_response(200)
		self.send_header("Content-type", "application/octet-stream")
		self.end_headers()

		self.wfile.write(value)

    # Used to handle puts between the nodes
	def do_PUT_VALUE(self):
		contentLength = int(self.headers['Content-Length'])


		if contentLength <= 0 or contentLength > MAX_CONTENT_LENGHT:
			self.sendErrorResponse(400, "Content body to large")
			return

		#node.size += contentLength
		if node.size > MAX_STORAGE_SIZE:
			self.sendErrorResponse(400, "Storage server(s) exhausted")
			return

		node.operation_put_value(self.path, self.rfile.read(contentLength), contentLength)
		self.send_response(200)
		self.send_header("Content-type", "application/octet-stream")
		self.end_headers()

    # Findes the successor of a key
	def do_GET_SUCCESSOR(self):
		identifier = self.path
		successor = node.operation_get_successor(int(identifier))
		if successor == False:
			self.senfErrorResponse(404, "Successor not found")
			return

		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		self.wfile.write(successor)

    # A newly joined node will send a message to tell all other nodes that they need
    # to update their finger table
	def do_UPDATE_FINGER_TABLE(self):
		identity = self.path
		contentLength = int(self.headers['Content-Length'])
		self.send_response(200)
		self.send_header("Content-type", "application/octet-stream")
		self.end_headers()
		node.operation_update_finger_table(identity, self.rfile.read(contentLength))

    # A newly joined node will tell its predecessor that is needs to update its successor
	def do_UPDATE_PREDECESSOR(self):
		contentLength = int(self.headers['Content-Length'])
		self.send_response(200)
		self.send_header("Content-type", "application/octet-stream")
		self.end_headers()
		node.operation_update_predecessor(self.path,self.rfile.read(contentLength))


	def sendErrorResponse(self, code, msg):
		self.send_response(code)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		self.wfile.write(msg)

# Set up a server for each node to accept incomming request
class BackendHTTPServer(BaseHTTPServer.HTTPServer):

	def __init__(self, server_address, handler, nodeobj):
		BaseHTTPServer.HTTPServer.__init__(self, server_address, handler)
		global node
		node = nodeobj

	def server_bind(self):
		BaseHTTPServer.HTTPServer.server_bind(self)
		self.socket.settimeout(1)
		self.run = True

	def get_request(self):
		while self.run == True:
			try:
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
