To run the nodes:
- sh startup.sh

Changing the number of nodes can be done in startup.sh script.
To start up a new node can be done as follows:
- ssh compute-5-0
ssh into the node that you want to run.
- python node.py <compute...>
where <compute...> is a node currently on the network

Leaving form the network can be done.
ssh into the node that wants to leave the network
- ssh compute-5-0
find the pid of the proccess.
- ps aux | grep python
kill the process.
- kill *****
