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

def get_scrobbles(method='recenttracks', username=lfusername , key=lfkey, limit=200, extended=0, page=1, pages=0):
    '''
    :param method: api method
    :param username/key: api credentials
    :param limit: api lets you retrieve up to 200 records per call
    :param extended: api lets you retrieve extended data for each track, 0=no, 1=yes
    :param page: page of results to start retrieving at
    :param pages: how many pages of results to retrieve. if 0, get as many as api can return.

    :return dataframe with lastfm scrobbles
    '''
    # initialize url and lists to contain response fields
    print("Fetching data from last.fm")
    url = 'https://ws.audioscrobbler.com/2.0/?method=user.get{}&user={}&api_key={}&limit={}&extended={}&page={}&format=json'
    responses = []
    artist_names = []
    artist_mbids = []
    album_names = []
    album_mbids = []
    track_names = []
    track_mbids = []
    timestamps = []

    # make first request, just to get the total number of pages
    request_url = url.format(method, username, key, limit, extended, page)
    response = requests.get(request_url).json()
    total_pages = int(response[method]['@attr']['totalPages'])
    if pages > 0:
        total_pages = min([total_pages, pages])

    print('{} total pages to retrieve'.format(total_pages))

    # request each page of data one at a time
    for page in tqdm(range(1, int(total_pages) + 1, 1)):
        time.sleep(0.20)
        request_url = url.format(method, username, key, limit, extended, page)
        responses.append(requests.get(request_url))

    # parse the fields out of each scrobble in each page (aka response) of scrobbles
    for response in responses:
        scrobbles = response.json()
        for scrobble in scrobbles[method]['track']:
            # only retain completed scrobbles (aka, with timestamp and not 'now playing')
            if 'date' in scrobble.keys():
                artist_names.append(scrobble['artist']['#text'])
                artist_mbids.append(scrobble['artist']['mbid'])
                album_names.append(scrobble['album']['#text'])
                album_mbids.append(scrobble['album']['mbid'])
                track_names.append(scrobble['name'])
                track_mbids.append(scrobble['mbid'])
                timestamps.append(scrobble['date']['uts'])

    # create and populate a dataframe to contain the data
    df = pd.DataFrame()
    df['timestamp'] = timestamps
    df['datetime'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
    df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata') #use your own timezone
    df['artist'] = artist_names
    df['artist_mbid'] = artist_mbids
    df['album'] = album_names
    df['album_mbid'] = album_mbids
    df['track'] = track_names
    df['track_mbid'] = track_mbids

    return df


def mapToSpotify(sp,scrobblesDF): #todo : [for v2]use a better approach instead of bruteforcing
    """
    Maps track names to spotifyID and adds track length,popularity,genre to dataframe.
    :param sp : spotipy object
    :param scrobblesDF : lastfm scrobbles dataframe
    :return dataframe with spotifyID ,track length,popularity,genre
    """
    track_ids = []
    length = []
    pop = []
    genre = []
    for index, row in tqdm(scrobblesDF.iterrows()):
        try:
            artist = re.sub("'", '', row['artist'])  # remove single quotes from queries
            track = re.sub("'", '', row['track'])

            searchDict = sp.search(q='artist:' + artist + ' track:' + track, type='track', limit=1, market='US') #using US for max compatibility

            print("\n"+track)
            print("Mapping spotifyID for " + str(index) + " out of " + str(len(scrobblesDF.index)))

            if len(searchDict['tracks']['items']) != 0:
                track_ids.append(searchDict['tracks']['items'][0]['id'])
                length.append(searchDict['tracks']['items'][0]['duration_ms'])
                pop.append(searchDict['tracks']['items'][0]['popularity'])
                artist_id = searchDict['tracks']['items'][0]['artists'][0]['id']
                artist = sp.artist(artist_id) #get genre from artist
                try:
                    genreA = artist['genres'][0]  #gets only the first genre from list of genres
                    genre.append(genreA)
                except IndexError:
                    genre.append(np.nan)
            else:
                print('\n')
                track_ids.append(np.nan)
                length.append(np.nan)
                pop.append(np.nan)
                genre.append(np.nan)
                print("failed to map " + track)
        except SpotifyException as e:
            Au.tokenRefresh()

    scrobblesDF['trackID'] = pd.Series(track_ids)
    scrobblesDF['lengthMS'] = pd.Series(length)
    scrobblesDF['popularity'] = pd.Series(pop)
    scrobblesDF['genre'] = pd.Series(genre)

    return scrobblesDF

def get_scrobbles(method='recenttracks', username=lfusername , key=lfkey, limit=200, extended=0, page=1, pages=0):
    '''
    :param method: api method
    :param username/key: api credentials
    :param limit: api lets you retrieve up to 200 records per call
    :param extended: api lets you retrieve extended data for each track, 0=no, 1=yes
    :param page: page of results to start retrieving at
    :param pages: how many pages of results to retrieve. if 0, get as many as api can return.

    :return dataframe with lastfm scrobbles
    '''
    # initialize url and lists to contain response fields
    print("Fetching data from last.fm")
    url = 'https://ws.audioscrobbler.com/2.0/?method=user.get{}&user={}&api_key={}&limit={}&extended={}&page={}&format=json'
    responses = []
    artist_names = []
    artist_mbids = []
    album_names = []
    album_mbids = []
    track_names = []
    track_mbids = []
    timestamps = []

    # make first request, just to get the total number of pages
    request_url = url.format(method, username, key, limit, extended, page)
    response = requests.get(request_url).json()
    total_pages = int(response[method]['@attr']['totalPages'])
    if pages > 0:
        total_pages = min([total_pages, pages])

    print('{} total pages to retrieve'.format(total_pages))

    # request each page of data one at a time
    for page in tqdm(range(1, int(total_pages) + 1, 1)):
        time.sleep(0.20)
        request_url = url.format(method, username, key, limit, extended, page)
        responses.append(requests.get(request_url))

    # parse the fields out of each scrobble in each page (aka response) of scrobbles
    for response in responses:
        scrobbles = response.json()
        for scrobble in scrobbles[method]['track']:
            # only retain completed scrobbles (aka, with timestamp and not 'now playing')
            if 'date' in scrobble.keys():
                artist_names.append(scrobble['artist']['#text'])
                artist_mbids.append(scrobble['artist']['mbid'])
                album_names.append(scrobble['album']['#text'])
                album_mbids.append(scrobble['album']['mbid'])
                track_names.append(scrobble['name'])
                track_mbids.append(scrobble['mbid'])
                timestamps.append(scrobble['date']['uts'])

    # create and populate a dataframe to contain the data
    df = pd.DataFrame()
    df['timestamp'] = timestamps
    df['datetime'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
    df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata') #use your own timezone
    df['artist'] = artist_names
    df['artist_mbid'] = artist_mbids
    df['album'] = album_names
    df['album_mbid'] = album_mbids
    df['track'] = track_names
    df['track_mbid'] = track_mbids

    return df


def mapToSpotify(sp,scrobblesDF): #todo : [for v2]use a better approach instead of bruteforcing
    """
    Maps track names to spotifyID and adds track length,popularity,genre to dataframe.
    :param sp : spotipy object
    :param scrobblesDF : lastfm scrobbles dataframe
    :return dataframe with spotifyID ,track length,popularity,genre
    """
    track_ids = []
    length = []
    pop = []
    genre = []
    for index, row in tqdm(scrobblesDF.iterrows()):
        try:
            artist = re.sub("'", '', row['artist'])  # remove single quotes from queries
            track = re.sub("'", '', row['track'])

            searchDict = sp.search(q='artist:' + artist + ' track:' + track, type='track', limit=1, market='US') #using US for max compatibility

            print("\n"+track)
            print("Mapping spotifyID for " + str(index) + " out of " + str(len(scrobblesDF.index)))

            if len(searchDict['tracks']['items']) != 0:
                track_ids.append(searchDict['tracks']['items'][0]['id'])
                length.append(searchDict['tracks']['items'][0]['duration_ms'])
                pop.append(searchDict['tracks']['items'][0]['popularity'])
                artist_id = searchDict['tracks']['items'][0]['artists'][0]['id']
                artist = sp.artist(artist_id) #get genre from artist
                try:
                    genreA = artist['genres'][0]  #gets only the first genre from list of genres
                    genre.append(genreA)
                except IndexError:
                    genre.append(np.nan)
            else:
                print('\n')
                track_ids.append(np.nan)
                length.append(np.nan)
                pop.append(np.nan)
                genre.append(np.nan)
                print("failed to map " + track)
        except SpotifyException as e:
            Au.tokenRefresh()

    scrobblesDF['trackID'] = pd.Series(track_ids)
    scrobblesDF['lengthMS'] = pd.Series(length)
    scrobblesDF['popularity'] = pd.Series(pop)
    scrobblesDF['genre'] = pd.Series(genre)

    return scrobblesDF


Au = Authentication(spot_secret=secret, spot_cid=cid)
sp = spotipy.Spotify(auth=Au.getSpotifyToken()) #create spotify object globally

start_time = time.time() #get running time for the script

scrobblesDF = get_scrobbles(pages=0)#get all pages form lastfm with pages = 0
scrobblesDF2 = mapToSpotify(sp, scrobblesDF)
scrobblesDF2.to_csv("data\LFMscrobbles.tsv", sep='\t') #using different dataframes to debug

end_time = time.time()

start_time = start_time/60
end_time = end_time/60


print("Finished in "+str(end_time-start_time)+" mins" )
