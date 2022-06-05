from google.cloud import firestore
import datetime
import time

class DbRecords:

    def __init__(self, doc_path: str = None) -> None:
        """Constructor

        Args:
            doc_path (str): Path of document in a collection
        """

        # Project ID is determined by the GCP_PROJECT environment variable
        self._db = firestore.Client()

        if doc_path:
            path_parts = doc_path.split('/documents/')[1].split('/')
            self._collection_path = path_parts[0]
            self._document_path = '/'.join(path_parts[1:])

    def add_convert_history_order_document_on_success(
        self,
        exchange: str,
        id: str, 
        future: str, 
        side: str, 
        size: float, 
        createdAt: str) -> None:
        """Add a sub collection document on successful order creation.

        Args:
            id (str): order id
            future (str): next market future
            side (str): order side
            size (float): order size
            createdAt (str): order creation date & time
        """
        col_ref = self._db.collection(self._collection_path).document(self._document_path).collection(u'order')
        col_ref.add({
            u'exchange': exchange,
            u'id': id,
            u'future': future,
            u'side': side,
            u'size': size,
            u'createdAt': createdAt
        })

    def add_convert_history_order_document_on_failure(self, error: str) -> None:
        """Add a sub collection document on order creation failure.

        Args:
            error (str): error message 
        """

        col_ref = self._db.collection(self._collection_path).document(self._document_path).collection(u'order')
        col_ref.add({u'error': error})

    def update_convert_history_document(self, status: str) -> None:
        """Update status of history document after order is successfully created 
        or encounter an error

        Args:
            status (str): status (eg: sent/error)
        """

        doc_ref = self._db.collection(self._collection_path).document(self._document_path)
        now = datetime.datetime.now()
        doc_ref.update({
            u'status': status,
            u'datetime': now.strftime("%Y-%m-%d %H:%M:%S")})
        
    def add_price_history_document(
        self,
        currency_pair: str, 
        rate: float, 
        market: str, 
        source: str = 'FTX') -> None:
        """Add a document to `price_histories` collection.

        Args:
            currency_pair (str): Currency pair used by user (eg: USD-BTC)
            rate (float): Market price
            source (str): Exchange (eg: FTX)
            market (str): Market used to get the price (eg: BTC-PERP)
        """
        col_ref = self._db.collection("price_histories")
        col_ref.add({
            u'currency_pair': currency_pair,
            u'rate': rate,
            u'source': source,
            u'market': market,
            u'timestamp': int(time.time())
        })
        
    def delete_old_price_history_documents(
        self,
        currency_pair: str):
        """Delete all old documents created 3 days before.

        Args:
            currency_pair (str): Currency pair used by user (eg: USD-BTC)
        """
        
        # Retrive the latest document for a given curreny pair
        col_ref = self._db.collection("price_histories")
        queryWhere = col_ref.where(u'currency_pair', u'==', currency_pair)
        queryOrderBy = queryWhere.order_by(u'timestamp', direction=firestore.Query.DESCENDING)
        queryLimt = queryOrderBy.limit(1)
        docs = queryLimt.stream()
        
        lastTimestamp = 0
        for doc in docs:
            lastTimestamp = doc.to_dict()['timestamp']
            break
        
        # No action to take
        if lastTimestamp == 0:
            return

        # Retrieve all old documents created before 3 day
        lastDay = datetime.datetime.fromtimestamp(lastTimestamp)
        oneDayAgo = lastDay - datetime.timedelta(3)
        newTimestamp = int(oneDayAgo.timestamp())
     
        # Delete all old documents created before 3 day
        col_ref = self._db.collection("price_histories")
        queryWhere = col_ref.where(u'currency_pair', u'==', currency_pair).where(u'timestamp', u'<=', newTimestamp)
        queryOrderBy = queryWhere.order_by(u'timestamp', direction=firestore.Query.DESCENDING)
        docs = queryOrderBy.stream()
        for doc in docs:
           doc.reference.delete()
    
    def get_market_price(
        self,
        currency_pair: str) -> float:
        """ Get market price for a given currency pair

        Args:
            currency_pair (str): curreny pair (eg: BTC-USD)

        Returns:
            float: market price
        """
        
         # Retrive the latest document for a given curreny pair
        col_ref = self._db.collection("price_histories")
        queryWhere = col_ref.where(u'currency_pair', u'==', currency_pair)
        queryOrderBy = queryWhere.order_by(u'timestamp', direction=firestore.Query.DESCENDING)
        queryLimt = queryOrderBy.limit(1)
        docs = queryLimt.stream()
        
        rate : float = 0
        for doc in docs:
            rate = doc.to_dict()['rate']
            break
    
        return rate
 
    def isNaN(self, num):
        return num != num
       
    def calculate_conversions_stats(self) -> None:
        """Calculate stats
        """

        user = {}
        col_ref = self._db.collection("convert_history")
        docs = col_ref.stream()
        
        total_users = 0
        total_from_usds_conversions = 0
        total_to_usds_conversions = 0
        for doc in docs:
            total_users = total_users + 1
            for sub_col_ref in doc.reference.collections():
                for sub_doc in sub_col_ref.stream():
                    from_currency = sub_doc.to_dict()['from_currency']
                    amount = sub_doc.to_dict()['amount']
                    status = sub_doc.to_dict()['status']
                    if status != 'done' and status != 'pending':
                        continue
                    
                    rate = sub_doc.to_dict()['rate']
                    if from_currency == 'USDS':
                        if 'FROM_USDS' in user:
                            user['FROM_USDS'] = user['FROM_USDS'] + amount
                        else:
                            user['FROM_USDS'] = amount
                        total_from_usds_conversions = total_from_usds_conversions + 1
                    else:
                        if 'TO_USDS' in user:
                            user['TO_USDS'] =  user['TO_USDS'] + (amount * rate)
                        else: 
                            user['TO_USDS'] = amount * rate
                        total_to_usds_conversions = total_to_usds_conversions + 1
                     
        print('Total number of users who performed conversion: {}'.format(total_users))
        print('[FROM USDS] Total number of conversions: {}'.format(total_from_usds_conversions))
        print('[FROM USDS] Total amount of conversions: {} USDS'.format(user['FROM_USDS']))
        print('[TO USDS] Total number of conversions: {}'.format(total_to_usds_conversions))
        print('[TO USDS] Total amount of conversions: {} USDS'.format(user['TO_USDS']))

    def calculate_total_paid_interest(self) -> None:
        """Calculate paid interest
        """

        col_ref = self._db.collection("interest_payment_histories")
        docs = col_ref.stream()
        
        total_users = 0
        total_interest_paid = 0
        for doc in docs:
            total_users = total_users + 1
            for sub_col_ref in doc.reference.collections():
                for sub_doc in sub_col_ref.stream():
                    total_interest_paid = total_interest_paid + sub_doc.to_dict()['amount']

        print('Total number of users to whom interest is paid: {}'.format(total_users))
        print('Total interest paid out: {} USDS'.format(total_interest_paid))
        
    
    def users_with_positive_balance(self) -> None:
        """list users with positive balances
        """

        print("Users with positive balances") 
        col_ref = self._db.collection("balances")
        docs = col_ref.stream()
        
        for doc in docs:
            hasBalance = False
            doc_params = doc.to_dict()
            msg = 'User: {}'.format(doc.id)
            for param in doc_params:
                balance = float("%.4f" % doc_params[param])
                if balance > 0:
                    hasBalance = True
                    msg+= ' {}:{}'.format(param,balance)
            if  hasBalance: 
                print(msg)
                
        print("\n\nUsers with positive pending balances") 
        col_ref = self._db.collection("pending_balances")
        docs = col_ref.stream()
        
        for doc in docs:
            hasBalance = False
            doc_params = doc.to_dict()
            msg = 'User: {}'.format(doc.id)         
            for param in doc_params:
                balance = float("%.4f" % doc_params[param])
                if balance > 0:
                    hasBalance = True
                    msg+= ' {}:{}'.format(param,balance)
            if  hasBalance: 
                print(msg)