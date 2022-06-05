import bybit
import datetime


class BybitClient:

    def __init__(self, api_key: str, api_secret: str, test: bool=True) -> None:
        """Constructor

        Args:
            api_key (str): key of api
            api_secret (str): secret of api
            test (bool, optional): testnet or mainnet. Defaults to True.
        """
        self._client = bybit.bybit(test=test, api_key=api_key, api_secret=api_secret)

    def get_next_symbol_name(self, base_currency='BTC', quote_currency='USD') -> str:
        """Get name of next enabled and non-expired symbol

        Args:
            base_currency (str, optional): Base currency. Defaults to 'BTC'.
            quote_currency (str, optional): Quote currency. Defaults to 'USD'.

        Returns:
            str: Returns the name of next enabled and non-expired symbol
        """
        current_year = datetime.datetime.utcnow().strftime('%y')
        current_month_year = datetime.datetime.utcnow().strftime('%m%d')
        all_symbols = self._client.Symbol.Symbol_get().result()[0]['result']
        future_symbols = [symbol for symbol in all_symbols if 
                        symbol['base_currency'] == base_currency and 
                        symbol['quote_currency'] == quote_currency and 
                        symbol['status'] == 'Trading' and 
                        symbol['name'].startswith(base_currency + quote_currency) and 
                        symbol['name'].endswith(current_year) and
                        int(symbol['alias'][6:]) >= int(current_month_year) ]
        
        return min(future_symbols, key=lambda symbol:int(symbol['alias'][6:]))['name']

    def place_order(
        self, 
        symbol: str, 
        side: str, 
        qty: int, 
        order_type: str='Market',
        time_in_force='GoodTillCancel') -> dict:
        """Place an order

        Args:
            symbol (str): name of symbol (eg:BTCUSD)
            side (str): 'Buy' or 'Sell'
            qty (int): qty/size of order
            order_type (str, optional): Order type (Limit, Market etc). Defaults to 'Market'.
            time_in_force (str, optional): Time in force (GoodTillCancel/ImmediateOrCancel/FillOrKill/PostOnly). Defaults to GoodTillCancel.

        Returns:
            dict: returns the successfully placed order with dictonary of fields
        """
        data = self._client.FuturesOrder.FuturesOrder_new(
            symbol=symbol,
            side=side.title(),
            qty=qty,
            order_type=order_type.title(),
            time_in_force=time_in_force).result()[0]

        if data['result'] is not None:
            return data['result']
        else:
            raise Exception(data['ret_msg'])