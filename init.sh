#!/bin/bash

docker compose up -d

GARAGE_ADDR=${GARAGE_ADDR:-"127.0.0.1:3901"}
CAPACITY=${CAPACITY:-1063256064}
DC=${DC:-dc1}
KEY_NAME=${KEY_NAME:-"mlonmcu-key"}
BUCKET=${BUCKET:-"mlonmcu"}

NODE_ID=$(docker compose exec garage /garage node id)
docker compose exec garage /garage node connect $NODE_ID@$GARAGE_ADDR
docker compose exec garage /garage layout assign $NODE_ID -z $DC -c $CAPACITY
docker compose exec garage /garage layout show
docker compose exec garage /garage layout apply --version 1
KEY_INFO=$(docker compose exec garage /garage key create $KEY_NAME)
docker compose exec garage /garage bucket allow $BUCKET --read --write --owner --key $KEY_NAME

KEY_ID=$(echo "$KEY_INFO" | grep "Key ID" | awk '{print $3}')
SECRET_KEY=$(echo "$KEY_INFO" | grep "Secret key" | awk '{print $3}')

docker compose exec garage /garage bucket list
docker compose exec garage /garage key list
docker compose exec garage /garage layout show
docker compose exec garage /garage status
docker compose exec garage /garage stats

echo "Key ID: $KEY_ID"
echo "Secret: $SECRET_KEY"
