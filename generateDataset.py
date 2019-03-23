import requests, time
from tqdm import tqdm
import pandas as pd
import spotipy
import re
from spotipy import oauth2
from spotipy import SpotifyException

from config import *

def get_scrobbles(method='recenttracks', username=lfusername , key=lfkey, limit=200, extended=0, page=1, pages=0):
    '''
    method: api method
    username/key: api credentials
    limit: api lets you retrieve up to 200 records per call
    extended: api lets you retrieve extended data for each track, 0=no, 1=yes
    page: page of results to start retrieving at
    pages: how many pages of results to retrieve. if 0, get as many as api can return.
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

scrobblesDF = get_scrobbles(pages=0)