#!/usr/bin/env sh

function info(){
    echo "$0 start|stop|restart"
}

function start(){
    nohup python3 main.py &>> ./log/forward_server.log &
    echo "Process started"
}

function stop(){
    ps -ef | grep 'main.py' | grep -v grep|awk '{print "kill -9 " $2}' | sh
    echo "Process stopped"
}

function restart(){
    stop
    sleep 2
    start
}

if [[ "$1" == "" ]];then
    info
elif [[ "$1" == "stop" ]];then
    stop
elif [[ "$1" == "start" ]];then
    start
elif [[ "$1" == "restart" ]];then
    restart
else
    info
fi
