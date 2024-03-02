import requests
import json
import time
import hashlib
import hmac
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(connect=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

class Exchange():
    def __init__(self, testnet = True):
        if testnet:
            self.base_url = 'https://testnet.bitmex.com/api/v1/'
        else:
            self.base_url = 'https://www.bitmex.com/api/v1/'
        #self.symbol = 'XBTUSDT'
        #self.standard_quantity = 1000
    
    def generate_signature(self, method, endpoint, data = ''):
        url = '/api/v1/' + endpoint
        api_key = os.getenv("API_KEY")
        api_secret = os.getenv("SECRET_KEY")
        expires = int(round(time.time()) + 5)
        message = method + url + str(expires) + data
        signature = hmac.new(bytes(api_secret, 'utf-8'), bytes(message, 'utf-8'), digestmod=hashlib.sha256).hexdigest()
        return {
            'api-expires': str(expires),
            'api-key': api_key,
            'api-signature': signature
        }
    
    def get_quote(self, symbol):
        endpoint = f'quote?symbol={symbol}&count=1&reverse=true'
        url = self.base_url + endpoint
        headers = self.generate_signature('GET', endpoint)
        response = session.get(url, headers=headers).json()
        try:
            print("try quote")
            bid, ask = response[0]['bidPrice'], response[0]['askPrice']
        except KeyError as e:
            bid,ask = self.get_quote()
        return bid, ask
    
    def get_position(self):
        #endpoint = f'position?filter=%7B%22symbol%22%3A%20%22{self.symbol}%22%7D'
        endpoint = 'position'
        url = self.base_url + endpoint
        headers = self.generate_signature('GET', endpoint)
        response = session.get(url, headers=headers).json()
        print(response)
        try: 
            print("try position")
            isOpen, quantity = response[0]['isOpen'], response[0]['currentQty']
        except KeyError as e:
            isOpen, quantity = self.get_position()
        return isOpen, quantity
    
    def place_order(self, symbol, side, quantity, price):
        endpoint = 'order?type=IFXXXP'
        url = self.base_url + endpoint
        data = {
            'symbol': symbol,
            'side': side,
            'orderQty': quantity,
            'price': price,
            'ordType': 'Limit',
            'execInst' : 'ParticipateDoNotInitiate',
            'typ': 'IFXXXP'
        }
        data_json = json.dumps(data)
        headers = self.generate_signature('POST', endpoint, data_json)
        headers['Content-Type'] = 'application/json'
        response = session.post(url, headers=headers, data=data_json).json()
        return response
    
    def delete_all_orders(self):
        endpoint = f'order/all'
        url = self.base_url + endpoint
        headers = self.generate_signature('DELETE', endpoint)
        response = session.delete(url, headers=headers).json()
        return response
    
    def get_instruments(self):
        endpoint = f'instrument/active'
        url = self.base_url + endpoint
        headers = self.generate_signature('GET', endpoint)
        response = session.get(url, headers=headers).json()
        # symbol = response[0]['symbol']
        # try:
        #     print("try instruments")
        #     symbol = response[0]['symbol']
        #     print(type(symbol))
        #     print(type(symbol) is str)
        #     print(type(symbol) is int)
        #     instruments = response[0]['bidPrice'], response[0]['askPrice']
        # except KeyError as e:
        #     bid,ask = self.get_quote()
        #     pass
        return response

    
class Bot():
    def __init__(self, _exchange):
        self.exchange = _exchange
        self.amount_of_top = 5
        self.pairs = []
        # self.sleeping_time = 5
        # self.black_time = 15
        # self.my_last_bid = 0
        # self.my_last_ask = 0
        # self.my_last_quantity = 0

    def get_top_pairs(self):
        response = self.exchange.get_instruments()
        pairs = []
        for pair in response:
            if pair['typ'] == 'FFWCSX':
                pairs.append(Pair(pair))
        # for pair in pairs:
        #     print(pair.symbol, pair.profit)
        #     print()
        pairs.sort(key=lambda x: x.profit, reverse=True)
        pairs = pairs[:self.amount_of_top]
        #print("sorted!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        for pair in pairs:
            print(pair.symbol, pair.profit)
            print()


class Pair():
    def __init__(self, pair):
        self.symbol = pair['symbol']
        self.bid_price = pair['bidPrice']
        self.ask_price = pair['askPrice']
        self.profit = (-2 * pair['makerFee']) + abs(pair['fundingRate'])
        self.short = True
        if pair['fundingRate'] < 0: self.short = False
        self.isOpen = False

    #  def ini2(self, _symbol, _bid_price, _ask_price, _funding_rate, _maker_fee):
    #     self.symbol = _symbol
    #     self.bid_price = _bid_price
    #     self.ask_price = _ask_price
    #     self.profit = (-2 * _maker_fee) + abs(_funding_rate)
    #     self.short = True
    #     if _funding_rate < 0: self.short = False
    #     self.isOpen = False
    
    def set_prices(self, _bid_price, _ask_price):
        self.bid_price = _bid_price
        self.ask_price = _ask_price

    def set_open(self):
        self.isOpen = True
        
            


bitmex = Exchange(False)
bot = Bot(bitmex)
#bitmex.get_instruments()
bot.get_top_pairs()


