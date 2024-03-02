import requests
import json
import time
import hashlib
import hmac
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from datetime import datetime

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
        #print(response)
        try: 
            print("try position")
            isOpen, quantity = response[0]['isOpen'], response[0]['currentQty']
        except KeyError as e:
            response = self.get_position()
        return response
    
    def place_order(self, symbol, side, quantity, price, reduce_only = False):
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
        if reduce_only:
            data['execInst'] = 'ParticipateDoNotInitiate', 'ReduceOnly'
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
        #self.pairs = []
        self.amount_in_usd = 10
        self.all_orders_filled = False
        self.waiting_time_for_filling = 3
        self.blackout_time = 3
        self.waiting_before_opening_positions = 16000
        self.ending_opening_positions = 10
        # self.my_last_bid = 0
        # self.my_last_ask = 0
        # self.my_last_quantity = 0


    def get_top_pairs(self):
        self.pairs = []
        response = self.exchange.get_instruments()
        pairs = []
        for pair in response:
            if pair['typ'] == 'FFWCSX':
                if pair['symbol'] == 'XBTUSD':
                    self.btc_price = pair['midPrice']
                    self.set_funding_time(pair['fundingTimestamp'])
                    continue
                if pair['quoteCurrency'] == 'USDT' or pair['quoteCurrency'] == 'USD':
                    pairs.append(Pair(pair))
        pairs.sort(key=lambda x: x.profit, reverse=True)
        self.pairs = pairs[:self.amount_of_top]

    def set_funding_time(self, funding_timestamp):
        self.funding_time = datetime.strptime(funding_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")

    def calculate_contract_price(self, pair):
        price_in_btc = (pair.mid_price * pair.multiplier) / 10**8
        price_in_usd = price_in_btc * self.btc_price
        #print("prices:", pair.symbol, price_in_btc, price_in_usd)
        return price_in_usd
    
    def open_positions(self):
        for pair in self.pairs:
            if pair.is_filled: continue
            #print(pair.symbol)
            if pair.collateral == 'USDT':
                price = pair.mid_price
            else:
                price = self.calculate_contract_price(pair)
            quantity = int(self.amount_in_usd/price)
            quantity = int(quantity/pair.lots)*pair.lots
            print("quants:", pair.symbol, quantity)
            self.update_prices(pair)
            if pair.short:
                price = pair.ask_price
                side = "Sell"
            else:
                price = pair.bid_price
                side = "Buy"
            print(self.exchange.place_order(pair.symbol, side, quantity, price))

    def update_prices(self, pair):
        bid, ask = self.exchange.get_quote(pair.symbol)
        pair.set_prices(bid, ask)

    def calculate_time(self):
        time_now = datetime.now()
        if self.funding_time < time_now:
            countdown = -1
        else:
            countdown = self.funding_time - time_now
        return countdown.seconds

    def keep_opening_positions(self):
        orders_filled = False
        while not orders_filled:
            seconds_until_funding = self.calculate_time()
            if seconds_until_funding < self.ending_opening_positions:
                break
            self.open_positions()
            time.sleep(self.waiting_time_for_filling)
            self.exchange.delete_all_orders()
            time.sleep(self.blackout_time)
            self.update_positions()
            orders_filled = self.check_fulfillness()

    def update_positions(self):
        positions = self.exchange.get_position()
        positions.reverse()
        for position in positions:
            for pair in self.pairs:
                if pair.symbol == position['symbol']:
                    pair.quantity = position['currentQty']
                    if pair.quantity != 0: pair.is_filled = True
                    #print(pair.symbol, pair.quantity)

    def check_fulfillness(self):
        orders_filled = True
        for pair in self.pairs:
            if not pair.is_filled: orders_filled = False
        return orders_filled
    
    def check_emptiness(self):
        pass
    
    def manage_times(self):
        self.get_top_pairs()
        seconds_until_funding = self.calculate_time()
        while seconds_until_funding > self.waiting_before_opening_positions:
            seconds_until_funding = self.calculate_time()
        self.get_top_pairs()
        self.keep_opening_positions()
        seconds_until_funding = self.calculate_time()
        while seconds_until_funding > 0:
            seconds_until_funding = self.calculate_time()
        self.keep_closing_positions()

    def keep_closing_positions(self):
        pass



class Pair():
    def __init__(self, pair):
        self.symbol = pair['symbol']
        self.bid_price = pair['bidPrice']
        self.ask_price = pair['askPrice']
        self.profit = (-2 * pair['makerFee']) + abs(pair['fundingRate'])
        self.short = True
        if pair['fundingRate'] < 0: self.short = False
        self.is_filled = False
        self.multiplier = pair['multiplier']
        self.mid_price = pair['midPrice']
        self.collateral = pair['quoteCurrency']
        self.lots = pair['lotSize']
        self.quantity = 0
    
    def set_prices(self, _bid_price, _ask_price):
        self.bid_price = _bid_price
        self.ask_price = _ask_price

    def set_filled(self, _is_filled = True):
        self.is_filled = _is_filled

        
            


bitmex = Exchange(False)
bot = Bot(bitmex)
#bitmex.get_instruments()
#bot.get_top_pairs()
#bot.open_positions()
# for pair in bot.pairs:
#     print(pair.symbol, pair.ask_price, pair.multiplier)
#print(bitmex.place_order("MEMEUSDT", "Sell", 3300, 0.05))
#bot.open_positions()
#bitmex.get_position()
#bot.update_positions()
#bot.calculate_time()
#bot.manage_times()
print(bitmex.place_order('ADAUSD', 'Buy', 10, 0.3, True))

