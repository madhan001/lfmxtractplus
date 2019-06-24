import requests, time
from tqdm import tqdm
import pandas as pd
import numpy as np
import spotipy
import re
import yaml
import logging
from spotipy import oauth2
from spotipy import SpotifyException

cid = secret = lfkey = logPath = None  # vars for config.yaml
logger = None # global logger

#todo: refactor variable names to align with PEP

def init_logger():
    '''
    Initialize logger globally

    '''
    global logPath, logger
    logging.basicConfig(filename=logPath, format='%(asctime)s %(levelname)s %(message)s', filemode='w')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)


def load_cfg(yaml_filepath):
    """
    Load config vars from yaml
    :param yaml_filepath: path to config.yaml
    """
    global cid, secret, lfkey, logPath
    with open(yaml_filepath, 'r') as stream:
        config = yaml.safe_load(stream)
    cid = config['sp_cid']
    secret = config['sp_secret']
    lfkey = config['lf_key']
    logPath = config['log_path']

def get_spotify_token():
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

        return token_info, sp_oauth


def token_refresh(token_info, sp_oauth):
    '''
    Used to refresh OAuth token if token expired
    :param token_info dict
    :param sp_oauth object
    '''
    global sp
    if sp_oauth._is_token_expired(token_info):
        token_info_ref = sp_oauth.refresh_access_token(token_info['refresh_token'])
        token_ref = token_info_ref['access_token']
        sp = spotipy.Spotify(auth=token_ref)
        logger.info("________token refreshed________")


def authenticate():
    '''
    authenticate with spotify
    '''
    global token_info, sp, sp_oauth
    token_info, sp_oauth = get_spotify_token()  # authenticate with spotify
    sp = spotipy.Spotify(auth=token_info['access_token'])  # create spotify object globally


def get_scrobbles(username, method='recenttracks', timezone ='Asia/Kolkata', limit=200, page=1, pages=0):
    '''
    Retrieves scrobbles from lastfm for a user
    :param method: api method
    :param username: last.fm username for retrieval
    :param timezone: timezone of the user (must correspond with the timezone in user's settings)
    :param limit: api lets you retrieve up to 200 records per call
    :param page: page of results to start retrieving at
    :param pages: how many pages of results to retrieve. if 0, get as many as api can return.

    :return dataframe with lastfm scrobbles
    '''


    # initialize url and lists to contain response fields
    print("\nFetching data from last.fm for user "+ username)
    url = 'https://ws.audioscrobbler.com/2.0/?method=user.get{}&user={}&api_key={}&limit={}&page={}&format=json'
    responses = []
    artist_names = []
    artist_mbids = []
    album_names = []
    album_mbids = []
    track_names = []
    track_mbids = []
    timestamps = []
    # read from loadCFG()
    key = lfkey
    # make first request, just to get the total number of pages
    request_url = url.format(method, username, key, limit, page)
    response = requests.get(request_url).json()
    #error handling
    if 'error' in response:
        print("Error code : " + str(response['error']))
        logging.critical("Error code : " + str(response['error']))
        print("Error message : " + response['message'])
        logging.critical("Error message : " + response['message'])
        return None

    total_pages = int(response[method]['@attr']['totalPages'])
    total_scrobbles = int(response[method]['@attr']['total'])
    if pages > 0:
        total_pages = min([total_pages, pages])

    print('{} total tracks scrobbled by the user'.format(total_scrobbles))
    print('{} total pages to retrieve'.format(total_pages))

    # request each page of data one at a time
    for page in tqdm(range(1, int(total_pages) + 1, 1)):
        time.sleep(0.20)
        request_url = url.format(method, username, key, limit, page)
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
    df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert(timezone)
    df['artist_name'] = artist_names
    df['artist_mbid'] = artist_mbids
    df['album_name'] = album_names
    df['album_mbid'] = album_mbids
    df['track_name'] = track_names
    df['track_mbid'] = track_mbids

    return df


def map_to_spotify(scrobblesDF):
    """
    Maps track names to spotifyID and adds track length,popularity,genre to dataframe.
    :param scrobblesDF : lastfm scrobbles dataframe
    :return scrobblesDF : dataframe with spotifyID ,track length,popularity,genre
    """
    track_ids = []
    length = []
    pop = []
    genre = []
    print("\nFetching SpotifyID for tracks")
    for index, row in tqdm(scrobblesDF.iterrows(), total=scrobblesDF.shape[0]):
        try:
            artist = re.sub("'", '', row['artist_name'])  # remove single quotes from queries
            track = re.sub("'", '', row['track_name'])

            searchDict = sp.search(q='artist:' + artist + ' track:' + track, type='track', limit=1,
                                   market='US')  # api cakk

            logging.debug("Mapping spotifyID for " + track)
            # logging.debug("Mapping spotifyID for " + str(index) + " out of " + str(len(scrobblesDF.index)-1))

            if len(searchDict['tracks']['items']) != 0:
                track_ids.append(searchDict['tracks']['items'][0]['id'])
                length.append(searchDict['tracks']['items'][0]['duration_ms'])
                pop.append(searchDict['tracks']['items'][0]['popularity'])
                artist_id = searchDict['tracks']['items'][0]['artists'][0]['id']
                artist = sp.artist(artist_id)  # get genre from artist
                try:
                    genreA = artist['genres'][0]  # gets only the first genre from list of genres (may be inaccurate)
                    genre.append(genreA)
                except IndexError:
                    genre.append(np.nan)
            else:
                track_ids.append(np.nan)
                length.append(np.nan)
                pop.append(np.nan)
                genre.append(np.nan)
                logging.warning("failed to map " + track)
        except SpotifyException:
            if sp_oauth._is_token_expired(token_info):
                token_refresh(token_info, sp_oauth)  # refresh OAuth token
            else:
                logging.critical("SpotifyException")

    scrobblesDF['trackID'] = pd.Series(track_ids)
    scrobblesDF['lengthMS'] = pd.Series(length)
    scrobblesDF['popularity'] = pd.Series(pop)
    scrobblesDF['genre_name'] = pd.Series(genre)

    unmapped_cnt = scrobblesDF['trackID'].isna().sum()
    print("tracks without spotifyID : "+str(unmapped_cnt))

    return scrobblesDF


def map_audio_features(scrobblesDF):  # todo: [for v2]pass 50 IDs at once in chunks to sp.audio_features to speedup
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
    print("\nFetching audio features for tracks")
    for index, row in tqdm(scrobblesDF.iterrows(), total=scrobblesDF.shape[0]):
        try:
            logging.debug("Fetching features for " + str(index) + " out of " + str(len(scrobblesDF.index) - 1))
            if row['trackID'] is not np.nan:
                search_id = [str(row['trackID'])]
                feature = sp.audio_features(search_id)  # api call
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
                except (TypeError, AttributeError, IndexError):
                    logging.warning("\nTrack feature fetch failed for  " + row['track_name'])
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
                logging.warning("\nTrack ID not available for " + row['track_name'])
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
        except SpotifyException:
            if sp_oauth._is_token_expired(token_info):
                token_refresh(token_info, sp_oauth)  # refresh OAuth token
            else:
                logging.critical("SpotifyException")

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

    unmapped_cnt = scrobblesDF['trackID'].isna().sum()
    print("tracks without audio features : " + str(unmapped_cnt))

    return scrobblesDF


def get_playlist(user='billboard.com', playlist_id='6UeSakyzhiEt4NB3UAd6NQ'):
    '''
    retrives audio features of a playlist (Billboard Hot 100 is the default playlist)
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

    playlist = sp.user_playlist(user=user, playlist_id=playlist_id)
    count = playlist['tracks']['total']
    print("Fetching playlist")
    for i in tqdm(range(count)):
        # print('fetching   ' + str(i) + ' out of ' + str(count) + '   ' + playlist['tracks']['items'][i]['track']['id'])
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

    playlistDF = map_audio_features(playlistDF)

    return playlistDF


def generate_dataset(lfusername, timezone ='Asia/Kolkata', pages=0):
    '''
    Gets user's listening history and enriches it with Spotify audio features
    :param lfusername: last.fm username
    :param timezone: timezone of the user (must correspond with the timezone in user's settings)
    :param pages: number of pages to retrieve, use pages = 0 to retrieve full listening history
    :return scrobblesDFdict: dictionary with two dataframes ('complete' with timestamps and 'library' with library contents)
    '''
    scrobblesDF_lastfm = get_scrobbles(username=lfusername, timezone=timezone, pages=pages)  # get all pages form lastfm with pages = 0

    scrobblesDF_condensed = scrobblesDF_lastfm[['artist_name', 'track_name']]

    scrobblesDF_uniques = scrobblesDF_condensed.groupby(['artist_name', 'track_name']).size().reset_index()
    scrobblesDF_uniques.rename(columns={0: 'frequency'}, inplace=True)

    scrobblesDF_wTrackID_uniques = map_to_spotify(scrobblesDF_uniques)
    scrobblesDF_wFeatures_uniques = map_audio_features(scrobblesDF_wTrackID_uniques)

    scrobblesDF_complete = pd.merge(scrobblesDF_lastfm, scrobblesDF_wFeatures_uniques, how='left',
                                    on=['track_name', 'artist_name'])
    scrobblesDFdict = dict()
    scrobblesDFdict['complete'] = scrobblesDF_complete
    scrobblesDFdict['library'] = scrobblesDF_wFeatures_uniques

    return scrobblesDFdict


def unmapped_tracks(scrobblesDF):
    '''
    :param scrobblesDF: dataframe with scrobbled tracks and trackIDs
    :return scrobblesDF: dataframe containing tracks with no trackIDs
    '''

    noTrackID_df = scrobblesDF[scrobblesDF['trackID'].isnull()]
    return noTrackID_df

def initialize(cfgPath):
    '''
    calls functions needed for initialization, handles loading config file,
    initializing logger object, initializing Spotipy object.

    To be called before calling other functions.

    :param cfgPath: filepath for config.yaml
    '''
    load_cfg(cfgPath)
    init_logger()
    authenticate()

def main():
    start_time = time.time()  # get running time for the script

    load_cfg('C:\\Users\Madhan\PycharmProjects\lfm4pandas\config.yaml')
    init_logger()
    authenticate()  # authenticate with spotify

    scrobblesDFdict = generate_dataset(lfusername='madhan_001', pages=1)  # returns a dict of dataframes
    dic = scrobblesDFdict

    # scrobbles_complete.to_csv("data\LFMscrobbles.tsv", sep='\t') #using tsv as some attributes contain commas

    end_time = time.time()

    start_time = start_time / 60
    end_time = end_time / 60  # show time in minutes

    print("Finished in " + str(end_time - start_time) + " mins")


if __name__ == '__main__':

    main()
