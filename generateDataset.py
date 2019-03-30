import requests, time
from tqdm import tqdm
import pandas as pd
import numpy as np
import spotipy
import re
from spotipy import oauth2
from spotipy import SpotifyException

from config import *

class Authentication:

    def __init__(self, spot_cid ,spot_secret):
        '''
        Initialize Authentication object
        :param spot_cid: Spotify client ID
        :param spot_secret: Spotify client secret
        '''
        self.cid = spot_cid
        self.secret = spot_secret

    def getSpotifyToken(self):
        '''
        Used to get OAuth token from spotify.
        :return OAuth token
        '''
        self.sp_oauth = oauth2.SpotifyOAuth(client_id=self.cid, client_secret=self.secret,
                                       redirect_uri='https://example.com/callback/',
                                       scope='user-library-read')
        self.token_info = self.sp_oauth.get_cached_token()
        if not self.token_info:
            auth_url = self.sp_oauth.get_authorize_url()
            print(auth_url)
            response = input('Paste the above link into your browser, then paste the redirect url here: ')

            code = self.sp_oauth.parse_response_code(response)
            self.token_info = self.sp_oauth.get_access_token(code)

            token = self.token_info['access_token']
            return token

    def tokenRefresh(self): #todo:fix an issue where tokenRefresh() runs over and over after an exception
        '''
        Used to refresh OAuth token if running time exceeds 60 mins
        '''
        global sp
        if  self.sp_oauth._is_token_expired(self.token_info):  # todo refer https://stackoverflow.com/questions/11154634/call-nested-function-in-python
            self.token_info = self.sp_oauth.refresh_access_token(self.token_info['refresh_token'])
            self.token = self.token_info['access_token']
            sp = spotipy.Spotify(auth=self.token) #hmmmm may be faulty
        print("________token refreshed_______")




Au = Authentication(spot_secret=secret, spot_cid=cid)
sp = spotipy.Spotify(auth=Au.getSpotifyToken()) #create spotify object globally

