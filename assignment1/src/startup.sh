#!/bin/bash

# Executable
directory="/home/jra020/mandatory-master/assignment1/src/precode/" #current working directory
executable="backendnode.py";

NUM_HOSTS=10
rm hostfile
sh generate_hosts.sh $NUM_HOSTS

IFS=$'\n' read -d '' -r -a nodes < hostfile
echo "${nodes[@]}"
# Lists of nodes
#nodes=("compute-4-1" "compute-4-2" "compute-4-3")
#nodes=("compute-4-1" "compute-4-2" "compute-4-3" "compute-5-1" "compute-5-2" "compute-5-3")
# Stop any running processes
for node in "${nodes[@]}"
do
  ssh $node bash -c "'pgrep -f '$directory$executable' | xargs kill'"
done

# Boot all processes
predecessor=${nodes[0]}
for node in "${nodes[@]}"
do
  echo "Booting node" $node
  sleep 1
  nohup ssh $node bash -c "'python $directory$executable $predecessor grep da * 2> grep-errors$node.txt'"  > /dev/null 2>&1 &
  predecessor=$node
done

# Wait/Run benchmarks
HEALTY=1
while [ $HEALTY -eq 1  ]; do
  trap 'break' 2
  sleep 1
  echo "Checking if each node is alive and well..."
  for node in "${nodes[@]}"
  do
    if ssh -q $node ps aux | grep $executable > /dev/null 2>&1 ;
    then
      echo "$node is alive"
    else
      echo "$node is dead"
      let HEALTY=0
    fi
  done
done

# Stop
for node in "${nodes[@]}"
do
  ssh $node bash -c "'pgrep -f '$executable' | xargs kill'"
  if ssh -q $node ps aux | grep $executable > /dev/null 2>&1 ;
  then
    echo "Error: unable to stop $node"
  else
    echo "Shut down $node"
  fi
done
