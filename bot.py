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
        endpoint = 'order'
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
        try:
            print("try instruments")
            test = " " + response[0]['symbol']
        except KeyError as e:
            response = self.get_instruments()
        return response
    
    def get_user(self):
        endpoint = f'user'
        url = self.base_url + endpoint
        headers = self.generate_signature('GET', endpoint)
        response = session.get(url, headers=headers).json()
        return response

    
class Bot():
    def __init__(self, _exchange):
        self.exchange = _exchange
        self.amount_of_top = 10
        self.pairs = []
        self.amount_in_usd = 150
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
                if pair['symbol'] == 'XBTUSD':
                    self.btc_price = pair['midPrice']
                    continue
                pairs.append(Pair(pair))
        pairs.sort(key=lambda x: x.profit, reverse=True)
        self.pairs = pairs[:self.amount_of_top]

    def calculate_contract_price(self, pair):
        price_in_btc = (pair.mid_price * pair.multiplier) / 10**8
        price_in_usd = price_in_btc * self.btc_price
        print("prices:", pair.symbol, price_in_btc, price_in_usd)
        return price_in_usd
    
    def open_positions(self):
        for pair in self.pairs:
            if pair.is_open: continue
            #print(pair.symbol)
            if pair.collateral == 'USDT':
                price = pair.mid_price
            elif pair.collateral == 'USD':
                price = self.calculate_contract_price(pair)
            else:
                continue
            quantity = int(self.amount_in_usd/price)
            quantity = int(quantity/pair.lots)*pair.lots
            print("quants:", pair.symbol, quantity)
            if pair.short:
                price = pair.ask_price
                side = "Sell"
            else:
                price = pair.bid_price
                side = "Buy"
            #print(self.exchange.place_order(pair.symbol, side, quantity, price))


class Pair():
    def __init__(self, pair):
        self.symbol = pair['symbol']
        self.bid_price = pair['bidPrice']
        self.ask_price = pair['askPrice']
        self.profit = (-2 * pair['makerFee']) + abs(pair['fundingRate'])
        self.short = True
        if pair['fundingRate'] < 0: self.short = False
        self.is_open = False
        self.multiplier = pair['multiplier']
        self.mid_price = pair['midPrice']
        self.collateral = pair['quoteCurrency']
        self.lots = pair['lotSize']
    
    def set_prices(self, _bid_price, _ask_price):
        self.bid_price = _bid_price
        self.ask_price = _ask_price

    def set_open(self, _is_open = True):
        self.is_open = _is_open

        
            


bitmex = Exchange(False)
bot = Bot(bitmex)
#bitmex.get_instruments()
bot.get_top_pairs()
#bot.open_positions()
# for pair in bot.pairs:
#     print(pair.symbol, pair.ask_price, pair.multiplier)
print(bitmex.place_order("MEMEUSDT", "Sell", 3300, 0.05))
#bot.open_positions()

