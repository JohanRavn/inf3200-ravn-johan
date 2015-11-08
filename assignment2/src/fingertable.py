import hashlib

# Class for the finger table
class FingerTable():

	def __init__(self, mEntries):
		self.table = []
		self.mEntries = mEntries
		for i in range(0,self.mEntries):
			self.table.append([])

    # Create or update a finger
	def new_entry(self, i, myidentifier, identity):

		value = int((myidentifier + pow(2,(i+1)-1)) % pow(2,self.mEntries))
		fingerIdentifier = int("0x"+hashlib.sha1(identity).hexdigest(),0) % pow(2,self.mEntries)
		finger =[value, identity, int(fingerIdentifier)]
		self.table[i] = finger

    # Finds the best finger form the table to pass the message to
    # not used in the code
	def find_closest_finger(self, identifier):
		if identifier == self.table[0][0]:
			return self.table[0][1]
		for i in range(1, self.mEntries-1):
			# corner case
			if self.table[i][0] > self.table[i+1][0]:
				if identifier <= self.table[i+1][0] or identifier > self.table[i][0]:
					return self.table[i+1][1]
			else:
				if identifier > self.table[i][0] and identifier <= self.table[i+1][0]:
					return self.table[i+1][1]
		return self.table[4][1]


    # Helper functions
	def get_succ_identifier(self):
		return self.table[0][2]

	def get_succ_identity(self):
		return self.table[0][1]

	def get_finger_identifier(self, i):
		return self.table[i][2]

	def get_finger_identity(self, i):
		return self.table[i][1]
