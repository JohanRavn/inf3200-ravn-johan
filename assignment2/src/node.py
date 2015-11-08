import logging
import socket, errno
import getopt
import sys
import hashlib
import threading
import signal
import httplib
import time

from fingertable import FingerTable
from backendserver import BackendHTTPServer, BackendHttpHandler

mEntries = 10

class NodeCommunication:
    def start_get_conn(self, code, hostName, portNumber, key, value = None):
        conn = httplib.HTTPConnection(hostName, portNumber)
        # Try to start connection, if it fails wait 500 ms and try again
        while True:
            try:
                conn.request(code, key, value)
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

    def update_predecessor(self, hostName, portNumber, identity, newIdentity):
        self.start_put_conn("UPDATE_PREDECESSOR", hostName, portNumber, identity, newIdentity)


    def check_alive(self, hostName, portNumber):
        return self.start_get_conn("GET_ALIVE", hostName, portNumber)

    def request_successor(self, hostName, portNumber, identifier):
        return self.start_get_conn("GET_SUCCESSOR", hostName, portNumber, identifier)

    def election(self, hostName, portNumber, identifier, stopIdentity):
        return self.start_get_conn("ELECTION", hostName, portNumber,identifier, stopIdentity)

    def broadcast_leader(self, hostName, portNumber, leader, stopIdentity):
        return self.start_put_conn("PUT_LEADER", hostName, portNumber, leader, stopIdentity)

class NodeHelper():
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

class NodeOperations(NodeHelper):
    def log_status(self):
        logger.info("my identity = " + self.identity)
        logger.info("my identifyer = " + str(self.identifier))
        for i in range(0,mEntries):
            logger.info("my successor = "+ str(self.fingerTable.table[i]))

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

    def operation_election(self, identifier, stopIdentity):
        # Leader elction, iam the leader if my identifier is bigger than all others
        if self.identifier > int(identifier):
            # if we have reached all nodes
            if stopIdentity == self.fingerTable.get_succ_identity():
                return self.identity
            # pass ahead with new identifier
            res = self.election(self.fingerTable.get_succ_identity(), self.portNumber, str(self.identifier), stopIdentity)
            # if none set myself to leader
            if res == "None":
                return self.identity
            else:
                return res
        #  Pass ahead if i am not a possible leader
        # also check if we have reached all nodes
        if stopIdentity == self.fingerTable.get_succ_identity():
            return "None"
        else:
            return self.election(self.fingerTable.get_succ_identity(), self.portNumber, str(identifier), stopIdentity)

    # broadcast new leader
    def operation_put_leader(self, leader, stopIdentity):
        self.leader = leader
        if self.fingerTable.get_succ_identity() != stopIdentity:
            self.broadcast_leader(self.fingerTable.get_succ_identity(), self.portNumber, self.leader, stopIdentity)

    def frontend_get_current_leader(self, path):
        # Start first election if leader is None

        # Check if a current leader is available
        if self.leader == "None":
            # start eleciton
            res = self.election(self.fingerTable.get_succ_identity(), self.portNumber, str(self.identifier), self.identity)
            # If answer is none, i am the lader
            if res == "None":
                self.leader = self.identity
            # I am not the leader
            else:
                self.leader = res

            #Broadcast leader
            self.broadcast_leader(self.fingerTable.get_succ_identity(), self.portNumber, self.leader, self.identity)



        #logger.info("leader = %s", self.leader)
        return self.leader + ":" + str(self.portNumber)

    def frontend_get_nodes(self, path):
        return str(self.fingerTable.get_succ_identity()) + ":"+ str(self.portNumber) + "\n"
        #self.request_nodes(self.fingerTable.get_succ_identity(), self.portNumber, node_list, self.identity)
        # Broadcast list to

    def operation_update_predecessor(self,oldIdentity, newIdentity):
        self.log_status()
        if(self.fingerTable.get_succ_identity() == oldIdentity):
            self.fingerTable.new_entry(0, self.identifier, newIdentity)
        else:
            self.update_predecessor(self.fingerTable.get_succ_identity(), self.portNumber, oldIdentity, newIdentity)

class Node(NodeCommunication, NodeOperations, NodeHelper):

    def __init__(self, portNumber):
        self.portNumber = portNumber
        self.size = 0
        self.identity = socket.gethostname().rstrip(".local")
        self.leader = "None"
        self.identifier = int("0x"+hashlib.sha1(self.identity).hexdigest(),0) % pow(2,mEntries)
        logger.info(" My identifier = " + str(self.identifier))
        # initalize fingertable
        self.fingerTable = FingerTable(mEntries)

    def join(self, predecessor):
        # Join the system. Find my place
        # corner case for first node
        if predecessor == socket.gethostname().rstrip(".local"):
            # Create entires in the fingertable with myself
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
        self.update_predecessor(successor, self.portNumber, successor, self.identity)
        # Calculate the rest of the fingers
        self.find_fingers(self.identifier, self.portNumber)
        # send message to all others nodes, that they should update their finger table
        #self.update_others_finger_table(self.fingerTable.get_succ_identity(), self.portNumber, self.fingerTable.get_succ_identity(), self.identity)
    def leave(self):
        # Update my predecessor with new successor

        if self.leader == self.identity:
            self.broadcast_leader(self.fingerTable.get_succ_identity(), self.portNumber, "None", self.identity)
        self.update_predecessor(self.fingerTable.get_succ_identity(), self.portNumber, self.identity, self.fingerTable.get_succ_identity())

    def find_fingers(self, identifier, portNumber):
        for i in range(2, mEntries + 1):
            value = int((identifier + pow(2,i-1)) % pow(2,mEntries))

            if value < identifier:
                value += pow(2,mEntries)+1
            successor = self.check_corner_cases(value)
            if successor is None:
                successor = self.request_successor(self.fingerTable.get_succ_identity(), portNumber, str(value))
            self.fingerTable.new_entry(i-1, identifier, successor)


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

    # Start the server which handles incomming requests
    try:
        httpd = BackendHTTPServer(("",httpserver_port), BackendHttpHandler, node)
        logger.info("successfully started server")
        server_thread = threading.Thread(target = httpd.serve)
        logger.info("started thread")
        server_thread.daemon = True
        server_thread.start()
        logger.info("starte thread sucesfully")



    except:
        logger.info("Error: unable to http server thread")


    node.join(predecessor)

    def handler(signum, frame):
        logger.info("We got sigterm")
        node.leave()
        httpd.stop()
    signal.signal(signal.SIGTERM, handler)
    server_thread.join(50)

    node.log_status()
    logger.info("stopping.....")
