import requests, time
from tqdm import tqdm
import pandas as pd
import numpy as np
import spotipy
import re
from spotipy import oauth2
from spotipy import SpotifyException

from config import * #get api keys from config.py


def getSpotifyTokenInfo():
    '''
    Used to get OAuth token from spotify.
    :return token_info dict
    :return sp_oauth object
    '''
    sp_oauth = oauth2.SpotifyOAuth(client_id=cid, client_secret=secret,
                                   redirect_uri='https://example.com/callback/',)
    token_info = sp_oauth.get_cached_token()
    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        print(auth_url)
        response = input('Paste the above link into your browser, then paste the redirect url here: ')

        code = sp_oauth.parse_response_code(response)
        token_info = sp_oauth.get_access_token(code)

        return token_info,sp_oauth

def tokenRefresh(token_info,sp_oauth):
    '''
    :param token_info dict
    :param sp_oauth object
    Used to refresh OAuth token if token expired
    '''
    global sp
    if  sp_oauth._is_token_expired(token_info):
        token_info_ref = sp_oauth.refresh_access_token(token_info['refresh_token'])
        token_ref = token_info_ref['access_token']
        sp = spotipy.Spotify(auth=token_ref)
        print("________token refreshed________")



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
    df['artist_name'] = artist_names
    df['artist_mbid'] = artist_mbids
    df['album_name'] = album_names
    df['album_mbid'] = album_mbids
    df['track_name'] = track_names
    df['track_mbid'] = track_mbids

    return df


def mapToSpotify(scrobblesDF):
    """
    Maps track names to spotifyID and adds track length,popularity,genre to dataframe.
    :param scrobblesDF : lastfm scrobbles dataframe
    :return dataframe with spotifyID ,track length,popularity,genre
    """
    track_ids = []
    length = []
    pop = []
    genre = []
    for index, row in tqdm(scrobblesDF.iterrows()):
        try:
            artist = re.sub("'", '', row['artist_name'])  # remove single quotes from queries
            track = re.sub("'", '', row['track_name'])

            searchDict = sp.search(q='artist:' + artist + ' track:' + track, type='track', limit=1, market='US') #api cakk

            print("\n"+track)
            print("Mapping spotifyID for " + str(index) + " out of " + str(len(scrobblesDF.index)-1))

            if len(searchDict['tracks']['items']) != 0:
                track_ids.append(searchDict['tracks']['items'][0]['id'])
                length.append(searchDict['tracks']['items'][0]['duration_ms'])
                pop.append(searchDict['tracks']['items'][0]['popularity'])
                artist_id = searchDict['tracks']['items'][0]['artists'][0]['id']
                artist = sp.artist(artist_id) #get genre from artist
                try:
                    genreA = artist['genres'][0]  #gets only the first genre from list of genres (may be inaccurate)
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
        except SpotifyException:
            if sp_oauth._is_token_expired(token_info):
                tokenRefresh(token_info,sp_oauth) #refresh OAuth token
            else:
                print("SpotifyException")

    scrobblesDF['trackID'] = pd.Series(track_ids)
    scrobblesDF['lengthMS'] = pd.Series(length)
    scrobblesDF['popularity'] = pd.Series(pop)
    scrobblesDF['genre_name'] = pd.Series(genre)

    return scrobblesDF

def mapAudioFeatures(scrobblesDF):  #todo: [for v2]pass 50 IDs at once in chunks to sp.audio_features to speedup
    '''
    Adds track features to dataframe with SpotifyID.
    :param scrobblesDF: dataframe with SpotifyID
    :return enriched dataframe with audio features
    '''
    danceabilitySeries = []
    energySeries = []
    keySeries = []
    loudnessSeries = []
    modeSeries = []
    speechinessSeries = []
    acousticnessSeries = []
    instrumentalnessSeries = []
    livenessSeries = []
    valenceSeries = []
    tempoSeries = []

    for index, row in tqdm(scrobblesDF.iterrows()):
        try:
            print("\n\nFetching features for " + str(index) + " out of " + str(len(scrobblesDF.index) - 1))
            if row['trackID'] is not np.nan:
                search_id = [str(row['trackID'])]
                feature = sp.audio_features(search_id) #api call
                try:
                    danceabilitySeries.append(feature[0]["danceability"])
                    energySeries.append(feature[0]["energy"])
                    keySeries.append(feature[0]["key"])
                    loudnessSeries.append(feature[0]["loudness"])
                    modeSeries.append(feature[0]["mode"])
                    speechinessSeries.append(feature[0]["speechiness"])
                    acousticnessSeries.append(feature[0]["acousticness"])
                    livenessSeries.append(feature[0]["liveness"])
                    valenceSeries.append(feature[0]["valence"])
                    tempoSeries.append(feature[0]["tempo"])
                    instrumentalnessSeries.append(feature[0]["instrumentalness"])
                except (TypeError, AttributeError, IndexError) :
                    print("\nTrack feature fetch failed for  " + row['track_name'])
                    danceabilitySeries.append(np.nan)
                    energySeries.append(np.nan)
                    keySeries.append(np.nan)
                    loudnessSeries.append(np.nan)
                    modeSeries.append(np.nan)
                    speechinessSeries.append(np.nan)
                    acousticnessSeries.append(np.nan)
                    livenessSeries.append(np.nan)
                    valenceSeries.append(np.nan)
                    tempoSeries.append(np.nan)
                    instrumentalnessSeries.append(np.nan)

            else:
                print("\nTrack ID not available for " + row['track_name'])
                danceabilitySeries.append(np.nan)
                energySeries.append(np.nan)
                keySeries.append(np.nan)
                loudnessSeries.append(np.nan)
                modeSeries.append(np.nan)
                speechinessSeries.append(np.nan)
                acousticnessSeries.append(np.nan)
                livenessSeries.append(np.nan)
                valenceSeries.append(np.nan)
                tempoSeries.append(np.nan)
                instrumentalnessSeries.append(np.nan)
                continue
        except SpotifyException :
            if sp_oauth._is_token_expired(token_info):
                tokenRefresh(token_info,sp_oauth) #refresh OAuth token
            else:
                print("SpotifyException")

    scrobblesDF['danceability'] = danceabilitySeries
    scrobblesDF['energy'] = energySeries
    scrobblesDF['key'] = keySeries
    scrobblesDF['loudness'] = loudnessSeries
    scrobblesDF['mode'] = modeSeries
    scrobblesDF['speechiness'] = speechinessSeries
    scrobblesDF['acousticness'] = acousticnessSeries
    scrobblesDF['liveness'] = livenessSeries
    scrobblesDF['instrumentalness'] = instrumentalnessSeries
    scrobblesDF['valence'] = valenceSeries
    scrobblesDF['tempo'] = tempoSeries

    return scrobblesDF

def generateDataset(lfusername,pages):
    '''
    :param lfusername: last.fm username
    :param pages: number of pages to retrieve, use pages = 0 to retrieve full listening history
    :return: dictionary with two dataframes (complete with timestamps and library contents)
    '''
    global token_info,sp,sp_oauth
    token_info, sp_oauth = getSpotifyTokenInfo()  # authenticate with spotify
    sp = spotipy.Spotify(auth=token_info['access_token'])  # create spotify object globally

    scrobblesDF_lastfm = get_scrobbles(username=lfusername,pages=pages)  # get all pages form lastfm with pages = 0

    scrobblesDF_condensed = scrobblesDF_lastfm[['artist_name', 'track_name']]

    scrobblesDF_uniques = scrobblesDF_condensed.groupby(['artist_name', 'track_name']).size().reset_index()
    scrobblesDF_uniques.rename(columns={0: 'frequency'}, inplace=True)

    scrobblesDF_wTrackID_uniques = mapToSpotify(scrobblesDF_uniques)
    scrobblesDF_wFeatures_uniques = mapAudioFeatures(scrobblesDF_wTrackID_uniques)

    scrobblesDF_complete = pd.merge(scrobblesDF_lastfm, scrobblesDF_wFeatures_uniques, how='left',on=['track_name', 'artist_name'])
    scrobblesDFdict = dict()
    scrobblesDFdict['complete'] = scrobblesDF_complete
    scrobblesDFdict['library'] = scrobblesDF_wFeatures_uniques

    return scrobblesDFdict


def mappingStats(scrobblesDF):
    '''
    :param scrobblesDFdict: dataframe with scrobbled tracks and trackIDs
    :return: tuple with number of unmapped and overall counts
    '''
    count = scrobblesDF['track_name'].count()
    naCount = scrobblesDF['trackID'].isnull().sum()
    return naCount, count

#driver code
start_time = time.time()  #get running time for the script
scrobblesDFdict = generateDataset(lfusername,0) #returns a dict
print("couldn't map "+str(mappingStats(scrobblesDFdict['complete'])[0])+"out of "+str(mappingStats(scrobblesDFdict['complete'])[1]) +"(with timestamps)")
print("================================")
print("couldn't map "+str(mappingStats(scrobblesDFdict['library'])[0])+"out of "+str(mappingStats(scrobblesDFdict['library'])[1]) +"(with timestamps)")

#scrobbles_complete.to_csv("data\LFMscrobbles.tsv", sep='\t') #using tsv as some attributes contain commas
end_time = time.time()

start_time = start_time/60
end_time = end_time/60 #show time in minutes


print("Finished in "+str(end_time-start_time)+" mins" )
