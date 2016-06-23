#!/bin/bash
export PYTHONPATH=$PYTHONPATH:.
if luigi --module workflow CreateMap --local-scheduler --retcode-task-failed 1; then
	echo "LUIGI BUILD SUCCEEDED" >&2
	exit 0
else
	echo "LUIGI BUILD FAILED" >&2
	exit 1
fi
