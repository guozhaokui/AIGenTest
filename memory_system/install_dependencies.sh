#!/bin/bash
echo "============================================"
echo "Installing Memory System Dependencies"
echo "============================================"
echo

pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo
    echo "============================================"
    echo "Dependencies installed successfully!"
    echo "============================================"
else
    echo
    echo "============================================"
    echo "Error installing dependencies"
    echo "============================================"
fi
