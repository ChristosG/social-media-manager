#!/bin/bash
KEY=$(openssl rand -base64 48)
echo "API_KEY=${KEY}"
