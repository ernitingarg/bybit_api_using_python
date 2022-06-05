from ftx_client import *
from bybit_client import *
from secret_manager import *
from db_records import *
import os

# Get secret keys from secret manager and initialize exchange api client
_BYBIT_IS_TESTNET = get_secret_key("BYBIT_IS_TESTNET")
_BYBIT_API_KEY = get_secret_key("BYBIT_API_KEY")
_BYBIT_API_SECRET = get_secret_key("BYBIT_API_SECRET")
_bybit_client = BybitClient(_BYBIT_API_KEY, _BYBIT_API_SECRET, eval(_BYBIT_IS_TESTNET))

_FTX_API_ENDPOINT = 'https://ftx.com/api/'
_FTX_API_KEY = get_secret_key("FTX_API_KEY")
_FTX_API_SECRET = get_secret_key("FTX_API_SECRET")
_FTX_SUB_ACCOUNT = get_secret_key("FTX_SUB_ACCOUNT")
_ftx_client = FtxClient(_FTX_API_ENDPOINT, _FTX_API_KEY, _FTX_API_SECRET, _FTX_SUB_ACCOUNT)

STABLE_COINS = ['USDC', 'USDT']
    
def place_order_api(event, context):
    """Place an order on firestore document creation trigger
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """

    resource_string = context.resource
    print(f"Function triggered on firestore document creation: {resource_string}.")

    from_currency = next(iter(event['value']['fields']['from_currency'].values()))
    to_currency = next(iter(event['value']['fields']['to_currency'].values()))
    rate = float(next(iter(event['value']['fields']['rate'].values())))
    amount = float(next(iter(event['value']['fields']['amount'].values())))
    print("frontend input: from_currency=%s, to_currency= %s, rate=%s, amount=%s" % (from_currency, to_currency, rate, amount))

    db_records = DbRecords(resource_string)

    try:
        result = __place_bybit_future_order(from_currency, to_currency, amount, rate)
            
        # Add sub collection document to firestore to record order information
        db_records.add_convert_history_order_document_on_success(
            'bybit',
            result['order_id'], 
            result['symbol'], 
            result['side'], 
            result['qty'], 
            result['created_at'])

        # Specific usecase for stable coin USDC & USDT
        if from_currency in STABLE_COINS or to_currency in STABLE_COINS:
            result = __place_ftx_spot_order(from_currency, to_currency, amount)
            
            if result is not None:
                # Add sub collection document to firestore to record order information
                db_records.add_convert_history_order_document_on_success(
                    'ftx',
                    result['id'], 
                    result['market'], 
                    result['side'], 
                    result['size'], 
                    result['createdAt'])
            
        # Update history document with status 'sent'    
        db_records.update_convert_history_document("sent")

    except Exception as e:
        print(str(e))
       
        # Add sub collection document to firestore to record failure information
        db_records.add_convert_history_order_document_on_failure(str(e))

        # Update history document with status 'error' 
        db_records.update_convert_history_document("error")
        
def update_market_price(event, context):
    """Update price history for target markets using ftx api

    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    try:
        target_markets = os.environ["TARGET_MARKETS"]
        db_records = DbRecords()
        
        for target_market in target_markets.split('|'):
            try:
                market = target_market.strip()
                price = _ftx_client.get_single_market_price(market)
                if price <= 0:
                    print("price is less than zero for target market '%s'" % market)
                else:
                    currency_pair = "{0}-USD".format(target_market.split('-')[0])
                    
                    # Add latest market price in table
                    db_records.add_price_history_document(currency_pair, price, market)
            except Exception as e:
                print(e)
                pass
    except Exception as e:
        print(e)
        
def purge_old_market_price(event, context):
    """Purge/delete old price histories (older than 3 days) for target markets

    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    try:
        target_markets = os.environ["TARGET_MARKETS"]
        db_records = DbRecords()
        
        for target_market in target_markets.split('|'):
            try:
                market = target_market.strip()
                
                # old records don't have market field, so use currency_pair
                currency_pair = "{0}-USD".format(target_market.split('-')[0])
                    
                # Delete old prices from table added 3 days before.
                print("start purging old data for target market '%s'" % market)
                db_records.delete_old_price_history_documents(currency_pair)
                print("finished purging old data for target market '%s'" % market)
            except Exception as e:
                print(e)
                pass
    except Exception as e:
        print(e)
        
def calculate_stats(event, context):
    """Calculate stats

    """
    db_records = DbRecords()
    db_records.calculate_conversions_stats()
    db_records.calculate_total_paid_interest()

def list_user_with_positive_balance(event, context):
    """List users

    """
    db_records = DbRecords()
    db_records.users_with_positive_balance()

# In ftx, amount & side is w.r.t BTC        
def __place_ftx_spot_order(
    from_currency: str,
    to_currency: str,
    amount: float) -> dict:
    
    # do nothing if conversion is not for stable coin
    if from_currency not in STABLE_COINS and to_currency not in STABLE_COINS:
        return
    
    db_records = DbRecords()
    rate = db_records.get_market_price('BTC-USD')
    print("rate for market=BTC-USD is %s" % (rate))
    
    if to_currency in STABLE_COINS:
        side = 'sell'
        size = (amount/rate)
    else:
        side = 'buy'
        size = (amount/rate)
   
    # As we don't have market for BTC/USDC, lets use BTC/USD
    market = 'BTC/USD' if (from_currency == 'USDC' or to_currency == 'USDC') else 'BTC/USDT'

    # Api call for placing spot order
    print("FTX api call: placing ftx spot order for market=%s, side=%s, qty=%s" % (market, side, size))
    result = _ftx_client.place_order(market, side, size)
    print(result)
    return result

# in bybit amount is always in USD & side is w.r.t BTC or ETH
def __place_bybit_future_order(
    from_currency: str,
    to_currency: str,
    amount: float,
    rate: float) -> dict:
    
    if to_currency == 'USDS':
        base_currency = 'BTC' if from_currency in STABLE_COINS else from_currency
        side = 'Sell'
        qty = int(amount*rate)
    else:
        base_currency = 'BTC' if to_currency in STABLE_COINS else to_currency
        side = 'Buy'
        qty = int(amount)

    # Api call for getting next symbol name
    print("Bybit api call: getting next future symbol name for '%sUSD'" % base_currency)
    symbol = _bybit_client.get_next_symbol_name(base_currency)
    
    # Api call for placing future order
    print("Bybit api call: placing bybit future order for symbol=%s, side=%s, qty=%s" % (symbol, side, qty))
    result = _bybit_client.place_order(symbol, side, qty)
    print(result)
    return result
    