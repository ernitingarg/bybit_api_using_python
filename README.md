# bybit-exchange-api-functions

This repository aims to communicate with external apis.

## Overview

The aim of this repository is to interact with external apis (eg: FTX, Bybit) to book orders (spot,future etc) and get market price.

## Cloud functions

Currently, this repository is mainly used for below cloud functions:

- conversion_request_place_order_api
- UpdatePriceHistory
- purge_old_market_price

### _'conversion_request_place_order_api' function_

- This function place future order in `BYBIT` exchange and for stable coin (eg: `USDC`, `USDT`) additionally books spot order in `FTX` exchange.

- This function is triggered when user makes a conversion request from front end and a corresponding document is added by another backend cloud function `conversion_request` to firestore table `convert_history\{uid}\history\{assetType}`

- When a document is inserted into above firestore table, this function is auto triggered and an order is placed in bybit( and ftx) using external apis.

- On successful creation of order, a sub-document is inserted under sub-collection `order` with order details returned from bybit (and ftx). eg: `convert_history\{uid}\history\{assetType}\order\{id}\<details of order>`

- On failure, a subdocument is inserted under sub-scollection `order` with error details returned from bybit (and ftx). eg: `convert_history\{uid}\history\{assetType}\order\{id}\<error message>`

- After order book request is done, the final `status` of firestore document is updated from `pending` to `sent` or `error`. eg:
  `convert_history\{uid}\history\{assetType}\<{status = 'sent' or 'error'}>`

- There is pub/sub function `conversion_batch` which is auto triggered by scheduler job `convert_trigger` and is scheduled to run daily around 9.10 AM JST. The pub/sub function looks for all the documents of this table having status `sent` and do the conversion from `XYZ` to `USDS` or `USDS` to `XYZ` and finally marks the document status from `sent` to `done`

### _'UpdatePriceHistory' function_

- This function currently used `FTX` api exchange as its default.

- This cloud function is a pub/sub function which is auto triggered by schedule job `update_market_price_trigger` and is schedule to run after each minute.

- When this function is triggered, it gets the prices of all target markets configured in runtime enviornment variable `TARGET_MARKETS` (eg; BTC-PERP|ETH-PERP) using `FTX` api and save the price in a new document of table `price_histories`.

- This pre save/added price is used by front end conversion form/window for a given currency pair (eg: BTC-USD).

### _'purge_old_market_price' function_

- This cloud function is a pub/sub function which is auto triggered by schedule job `purge_old_market_price_trigger` and is schedule to run once daily at 2 AM JST time.

- This function auto purges/deletes all the old documents (older than 3 days) from `price_histories` table to avoid any future performance issue because of big size of table.

## Configuration/Setup

### Secret manager

- All API specific secrets have been added/uploaded to secret manager.

- Because above cloud functions run under default service account `App Engine default service account`, all secret keys must be created under same account, otherwise you will have to grant `Secret Manager Secret Accessor` role to another account

- Below are the scret keys currently used:

  - `BYBIT_IS_TESTNET` : `True` for non-production, `False` for production.
  - `BYBIT_API_KEY`
  - `BYBIT_API_SECRET`
  - `FTX_API_KEY`
  - `FTX_API_SECRET`
  - `FTX_SUB_ACCOUNT`

- Notes:

  - for `conversion_request_place_order_api` function, if you plan to change Bybit's API KEYS, you need to set static ip address used by cloud function in your api keys management. (refer below section for more details)

  - `UpdatePriceHistory` function always uses `FTX` exchange. (No static ip address is required)

### Runtime environment variables

- `conversion_request_place_order_api` no enviornment variables:

- `UpdatePriceHistory` and `purge_old_market_price_trigger` use below enviornment variables:

  - `TARGET_MARKET`: Current production setting is `BTC-PERP|ETH-PERP`

### Associating function egress with a static IP address

- This setup/configuration is required only for `conversion_request_place_order_api` function. The reason is, this function uses Bybit exchange which allows requests only from explicitly specified IP addresses and should be configured in Bybit API Key(s) in their portal. For FTX, there is no static ip required.

- As cloud function is a stateless service and doesn't have a static ip address. The idea is, first to route egress traffic from cloud function to VPC (Virtual private network) through VPC connector to adhere all the rules set on this VPC network and then setup Cloud NAT gateway with static ip address to give access to the function to connect to internet.

- More details and explained steps can be found here: https://cloud.google.com/functions/docs/networking/network-settings#associate-static-ip

- Below are the steps to follow:
  - Route function's egress through VPC network
    - Setup a VPC network
      - This step can be omitted as we will be using soteria's `default` VPC network.
    - Set up a Serverless VPC Access connector
      - In google cloud, go to `Serverless VPC access`
      - Enable `Serverless VPC Access API` (if not enabled before)
      - Click on `CREATE CONNECTOR`
        - Name = `soteria-connector`
        - Region = `us-central1` (or anything)
        - Network = `default` (choose VPC network of that region, let it be default)
        - Subnet = Select `Custom IP range` and in IP range enter `10.8.0.0`
      - Let other values to be defaulted one and click on `CREATE`
    - Set up Cloud NAT and specify a static IP address
      - In google cloud, go to `Cloud NAT`
      - Click on `CREATE NAT GATEWAY`
      - Name = `soteria-gateway`
      - VPC network= `default`
      - Region = `us-central1` (use same selected at the time of connector creation)
      - Cloud router = create a new router with name `soteria-router`
      - NAT Mapping/Source Internal = let `Primary and secondary ranges for all subnets` as default
      - NAT Mapping/NAT IP Address = `Manual` (Click on IP address, it will allow you to create a new static IP address, give the name `api-static-ip`)
      - Finally click on `CREATE`
- The static ip address created in last step has to be configured in Bybit API key. (Go to bybit portal and then `API` section and modify your key to add this ip address)

## Deployment

Make sure you have checked all steps mentioned in `Configuration/Setup` section.

Set the project enviornment

```
gcloud auth login
gcloud config set project <project name of the environment you want to deploy to>
```

### Deploying `conversion_request_place_order_api` function

```bash

# Existing function
gcloud functions deploy conversion_request_place_order_api

# New function
gcloud functions deploy conversion_request_place_order_api --entry-point=place_order_api --runtime=python37 --trigger-event=providers/cloud.firestore/eventTypes/document.create --trigger-resource=projects/{project_id}/databases/(default)/documents/convert_history/{uid}/history/{assetType} --vpc-connector=soteria-connector --egress-settings=all


# Note:
## Replace {project_id} with stagging/production project id
## Make sure vpc-connector is created already.
```

### Deploying `UpdatePriceHistory` function

```bash

# Existing function
gcloud functions deploy UpdatePriceHistory

# New function
gcloud functions deploy UpdatePriceHistory --entry-point=update_market_price --runtime=python37 --trigger-topic=update_market_price_topic --set-env-vars=TARGET_MARKETS="BTC-PERP|ETH-PERP"

# Note: Make sure topic and scheduler exists already
```

### Deploying `purge_old_market_price` function

```bash

# Existing function
gcloud functions deploy purge_old_market_price

# New function
gcloud functions deploy purge_old_market_price --entry-point=purge_old_market_price --runtime=python37 --trigger-topic=purge_old_market_price_topic --set-env-vars=TARGET_MARKETS="BTC-PERP|ETH-PERP" --timeout=540s

# Note: Make sure topic and scheduler exists already
```
