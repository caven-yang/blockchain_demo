import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4

import requests
import random
from flask import Flask, jsonify, request


class Blockchain:
    def __init__(self, proof=100, mining_rate=4):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()
        self.mining_rate = mining_rate
        # Create the genesis block
        self.new_block(previous_hash='1', proof=proof)
        self.proof_sum = 0
        self.proof_cnt = 0

    @property
    def mining_cost(self):
        return float(self.proof_sum) / self.proof_cnt

    def clone(self):
        copy = Blockchain()
        copy.current_transactions = [t.copy() for t in self.current_transactions]
        copy.chain = [c.copy() for c in self.chain]
        copy.nodes = self.nodes.copy()
        return copy

    def register_node(self, address):
        """
        Add a new node to the list of nodes

        :param address: Address of node. Eg. 'http://192.168.0.5:5000'
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain, silence=False):
        """
        Determine if a given blockchain is valid

        :param chain: A blockchain
        :return: True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            if silence:
                pass
            else:
                print(f'{last_block}')
                print(f'{block}')
                print("\n-----------\n")
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof'], self.mining_rate):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        This is our consensus algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.

        :return: True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain, silence=True):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, previous_hash):
        """
        Create a new Block in the Blockchain

        :param proof: The proof given by the Proof of Work algorithm
        :param previous_hash: Hash of previous Block
        :return: New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # Reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount, signature=None, msg=None):
        """
        Creates a new transaction to go into the next mined Block

        :param sender: Address of the Sender
        :param recipient: Address of the Recipient
        :param amount: Amount
        :return: The index of the Block that will hold this transaction
        """
        transaction = {
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
            
        }
        if msg and signature:
            transaction['signature'] = signature
            transaction['message'] = msg
        self.current_transactions.append(transaction)

        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

    def transaction(self, index):
        if not self.current_transactions:
            return "N/A"
        else:
            return self.current_transactions[index]

    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a Block

        :param block: Block
        """

        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()


    def work_for_proof(self):
        last_block = self.last_block
        last_proof = last_block['proof']
        return self.proof_of_work(last_proof)

    def proof_of_work(self, last_proof):
        """
        Simple Proof of Work Algorithm:
         - Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
         - p is the previous proof, and p' is the new proof
        """

        proof = 0
        while self.valid_proof(last_proof, proof, self.mining_rate) is False:
            proof += 1
            
        self.proof_sum += proof
        self.proof_cnt += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof, mining_rate):
        """
        Validates the Proof

        :param last_proof: Previous Proof
        :param proof: Current Proof
        :return: True if correct, False if not.
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == ("0" * mining_rate)

    def print_chain(self):
        for block in self.chain:
            print(f"\t{block}")

    # only get the longest blockchains
    # return tuple of valid chains vs invalid
    def valid_vs_invalid(blockchains):
        max_len = 0
        for blockchain in blockchains:
            if not blockchain.valid_chain(blockchain.chain, silence=True):
                continue
            l = len(blockchain.chain)
            if l > max_len:
                max_len = l
    
        valid = []
        invalid = []
        for bc in blockchains:
            l = len(bc.chain)
            if l == max_len:
                valid.append(bc)
            else:
                invalid.append(bc)
        return valid, invalid

# simulator for generation of (public, private) key pairs
class PyCryptoSim(object):
    def __init__(self):
        self.pairs = {}

    # public, private key tuple
    def key_pair(self, msg=None):
        if msg is None:
            msg = ''
        public = (str(uuid4()) + msg).replace('-', '')
        private = (str(uuid4()) + msg).replace('-', '')
        while True:
            if self.pairs.get(public) is None:
                self.pairs[public] = private
                break
        if self.pairs[public] != private:
            raise Exception('Error in the crypto simulator')
        return (public, private)

    def commit(self, private, msg):
        block_string = f"{private}{msg}".encode()[:64]
        return hashlib.sha256(block_string).hexdigest()

    def verify(self, public, msg, commit):
        my_sk = self.pairs.get(public) 
        if my_sk is None:
            return False
        return self.commit(my_sk, msg) == commit

class Ent(object):
    def __init__(self, name):
        self.name = name
        # mapping public keys to private keys
        self.keys = {}
        self.crypto = PyCryptoSim()

    def new_address(self):
        (public, private) = self.crypto.key_pair()
        self.keys[public] = private
        return public

    def gives(self, blockchain, recepient,  amount=1):
        copy = blockchain.clone()
        held, balance = self.balance(blockchain)
        if amount > held:
            raise Exception(f"{self.name}: insufficient balance")

        due = amount
        for payer, coins in balance.items():
            if coins < 0:
                raise Exception(f"address {payer} has negative balance")
            elif coins == 0:
                continue
            else:
                if due > coins:
                    pay = coins
                else:
                    pay = due
                due = due - pay
                # We need to sign
                msg = int(time())
                copy.new_transaction(
                    sender=payer,
                    recipient=recepient.new_address(),
                    amount=pay,
                    msg=msg,
                    signature=self.crypto.commit(payer, msg)
                )

                if due == 0:
                    break
                elif due < 0:
                    raise Exception("overpayed!")

        last_block = copy.last_block
        previous_hash = copy.hash(last_block)
        proof = copy.work_for_proof()
        copy.new_block(proof, previous_hash)
        return copy

    # Iterate through the blockchain
    def balance(self, blockchain, verbose=False):
        # A map of public address to balance
        balance = {}
        for pk, sk in self.keys.items():
            balance[pk] = 0

        for pk, sk in self.keys.items():
            for block in blockchain.chain:
                transactions = block.get('transactions')
                if not transactions:
                    continue
                for transaction in transactions:
                    recepient = transaction.get("recipient")
                    sender = transaction.get("sender")
                    amount = transaction.get("amount")
                    # verify that the sk matches the sender address
                    if pk == sender:
                        msg = str(time())
                        if self.crypto.verify(
                            public=sender,
                            msg=msg,
                            commit=self.crypto.commit(sk, msg),
                        ):
                            balance[pk] -= amount
                    if pk == recepient:
                        msg = uuid4()
                        if self.crypto.verify(
                            public=recepient,
                            msg=msg,
                            commit=self.crypto.commit(sk, msg),
                        ):
                            balance[pk] += amount

        total = 0
        for pk, b in balance.items():
            total += b
        return total, balance

    def mine(self, blockchain, speed=None):
        if speed and random.random() > 1.0/speed:
            return None
        copy = blockchain.clone()
        last_block = copy.last_block
        last_proof = last_block['proof']
        proof = copy.work_for_proof()
        copy.new_transaction(
            sender='from mine',
            recipient=self.new_address(),
            amount=1,
        )

        # Forge the new Block by adding it to the chain
        previous_hash = copy.hash(last_block)
        copy.new_block(proof, previous_hash)
        return copy

    def some_fake(self, blockchain):
        faked = blockchain.clone()
        for i in range(len(faked.chain)):
            block = faked.chain[i]
            transactions = block.get("transactions")
            for transaction in transactions:
                recepient = transaction.get("recipient", None)
                if recepient:
                    recepient = self.new_address(),
                    transaction = transaction.copy()
                    transaction["recipient"] = recepient
                    transactions = transactions.copy()
                    transactions.append(transaction)
                    block = block.copy()
                    block["transactions"] = transactions
                    faked.chain[i] = block                    
                    return faked
        return faked

    def validate_blockchain(self, blockchain):
        if blockchain.valid_chain(chain=blockchain.chain, silence=True):
            action = "accepts"
        else:
            action =  "rejects"
        return f"{self.name} {action} the blockchain"

    def register_nodes(self, nodes=[]):

        for node in nodes:
            blockchain.register_node(node)

# Instantiate the Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    # We run the proof of work algorithm to get the next proof...
    proof = blockchain.proof_of_work(last_proof)

    # We must receive a reward for finding the proof.
    # The sender is "0" to signify that this node has mined a new coin.
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # Forge the new Block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Create a new Transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
