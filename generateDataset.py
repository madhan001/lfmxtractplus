import requests, time
from tqdm import tqdm
import pandas as pd
import numpy as np
import spotipy
import re
import yaml
from spotipy import oauth2
from spotipy import SpotifyException

cid = secret = lfusername = lfkey = lftzone = None #vars for config.yaml

def loadCFG(yaml_filepath):
    """
    Load config vars from yaml
    :param yaml_filepath: path to config.yaml
    """
    global cid, secret, lfusername, lfkey, lftzone
    with open(yaml_filepath, 'r') as stream:
        config = yaml.load(stream)
    cid = config['sp_cid']
    secret = config['sp_secret']
    lfusername = config['lf_username']
    lfkey = config['lf_key']
    lftzone = config['lf_tzone']

def getSpotifyTokenInfo():
    '''
    Get OAuth token from spotify.
    :return token_info dict
    :return sp_oauth object
    '''
    sp_oauth = oauth2.SpotifyOAuth(client_id=cid, client_secret=secret,
                                   redirect_uri='https://example.com/callback/')
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

def authenticate():
    '''
    authenticate with spotify
    '''
    global token_info,sp,sp_oauth
    token_info, sp_oauth = getSpotifyTokenInfo()  # authenticate with spotify
    sp = spotipy.Spotify(auth=token_info['access_token'])  # create spotify object globally

def getScrobbles(username = lfusername, method='recenttracks', key=lfkey, time_zone = lftzone, limit=200, page=1, pages=0):
    '''
    :param method: api method
    :param username/key: api credentials
    :param limit: api lets you retrieve up to 200 records per call
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
    extended = 0
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
    df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert(time_zone) #use your own timezone
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
    :return scrobblesDF : dataframe with spotifyID ,track length,popularity,genre
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

def getPlaylist(user = 'billboard.com', playlist_id = '6UeSakyzhiEt4NB3UAd6NQ'):
    '''
    maps track features to a playlist (Billboard Hot 100 is the default playlist)
    :param user: username of the playlist owner
    :param playlist_id: playlist id (found at the end of a playlist url)
    :return: a dataframe with audio features of a playlist
    '''

    trackID = []
    track = []
    artist = []
    artistID = []
    genre = []
    lengthMS = []
    popularity = []

    playlist = sp.user_playlist(user=user ,playlist_id=playlist_id)
    count = playlist['tracks']['total']
    print("Fetching playlist")
    for i in tqdm(range(count)):
        #print('fetching   ' + str(i) + ' out of ' + str(count) + '   ' + playlist['tracks']['items'][i]['track']['id'])
        trackID.append(playlist['tracks']['items'][i]['track']['id'])
        track.append(playlist['tracks']['items'][i]['track']['name'])
        lengthMS.append(playlist['tracks']['items'][i]['track']['duration_ms'])
        popularity.append(playlist['tracks']['items'][i]['track']['popularity'])
        artist.append(playlist['tracks']['items'][i]['track']['artists'][0]['name'])
        artistID.append(playlist['tracks']['items'][i]['track']['artists'][0]['id'])

        artistOb = sp.artist(artistID[i])
        try:
            genreA = artistOb['genres'][0]
            genre.append(genreA)
        except IndexError:
            genre.append(None)

    playlistDF = pd.DataFrame()

    playlistDF['track'] = pd.Series(track)
    playlistDF['trackID'] = pd.Series(trackID)
    playlistDF['artist'] = pd.Series(artist)
    playlistDF['artistID'] = pd.Series(artistID)
    playlistDF['genre'] = pd.Series(genre)
    playlistDF['lengthMS'] = pd.Series(lengthMS)
    playlistDF['popularity'] = pd.Series(popularity)

    playlistDF = mapAudioFeatures(playlistDF)

    return playlistDF

def generateDataset(lfuname = lfusername,pages=0):
    '''
    :param lfuname: last.fm username
    :param pages: number of pages to retrieve, use pages = 0 to retrieve full listening history
    :return: dictionary with two dataframes ('complete' with timestamps and 'library' with library contents)
    '''
    authenticate()
    scrobblesDF_lastfm = getScrobbles(username=lfuname, key=lfkey, pages=pages, time_zone=lftzone)  # get all pages form lastfm with pages = 0

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

def unmappedTracks(scrobblesDF):
    '''
    :param scrobblesDF: dataframe with scrobbled tracks and trackIDs
    :return scrobblesDF: dataframe containing tracks with no trackIDs
    '''

    noTrackID_df = scrobblesDF[scrobblesDF['trackID'].isnull()]
    return noTrackID_df



def main():
    start_time = time.time()  #get running time for the script

    loadCFG('config.yaml')
    print(lfkey)
    print(lfusername)
    authenticate() #authenicate with spotify

    scrobblesDFdict = generateDataset(lfuname = lfusername, pages = 1) #returns a dict of dataframes
    scrobblesDFdict['library'].head(20)
    print("================================")
    #scrobbles_complete.to_csv("data\LFMscrobbles.tsv", sep='\t') #using tsv as some attributes contain commas

    end_time = time.time()

    start_time = start_time/60
    end_time = end_time/60 #show time in minutes


    print("Finished in "+str(end_time-start_time)+" mins" )

if __name__ == '__main__':
    main()