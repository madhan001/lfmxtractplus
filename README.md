# lfmxtractplus

## Description
lfmxtractplus is a library for extracting [Last.fm](https://last.fm) scrobbles with spotify [audio features](https://developer.spotify.com/documentation/web-api/reference/tracks/get-audio-features/) for use with [Pandas](https://pandas.pydata.org/)

## Working 
The user's scrobbles are retrieved using last.fm's API with the [user.getRecentTracks](https://www.last.fm/api/show/user.getRecentTracks) endpoint.
As last.fm's API doesn't provide a method to directly retrieve Spotify [audio features](https://developer.spotify.com/documentation/web-api/reference/tracks/get-audio-features/)
we use the [sp.search()](https://github.com/madhan001/lfmxtractplus/blob/76ccdd2a257bc1f39d9d5b6e34bf0c67a18f50ce/lfmxtractplus/export_data.py#L207) method to search Spotify for the track's spotifyID (trackID) and use the spotifyID to retrieve the audio feature of each track using the [sp.audio_features()](https://github.com/madhan001/lfmxtractplus/blob/76ccdd2a257bc1f39d9d5b6e34bf0c67a18f50ce/lfmxtractplus/export_data.py#L270) method.

## Installation
If you already have [Python](http://www.python.org/) on your system you can install the library simply by downloading the distribution, unpack it and install in the usual fashion:

```bash
python setup.py install
```

You can also install it using a popular package manager with

```bash
pip install lfmxtractplus
```

or

```bash
easy_install lfmxtractplus
```

## Dependencies

- [spotipy](https://spotipy.readthedocs.io/en/latest/) >= 2.4.4
- [pandas](https://pandas.pydata.org/) >= 0.22.0
- [PyYAML](https://pyyaml.org/) >= 5.1.1
- [numpy](https://www.numpy.org/) >= 1.14.0
- [requests](https://2.python-requests.org/en/master/) >= 2.22.0
- [tqdm](https://tqdm.github.io/) >= 4.31.1

## Quick Start

To get started,simply install lfmxtractplus, initialize with config.yaml, visit the link displayed and login with your Spotify account, copy and paste the redirect url back into the Python prompt
 and call methods:

```python
import lfmxtractplus.export_data as lf
import pandas as pd

lf.initialize('config.yaml')
scrobbles_dict = lf.generate_dataset(lfusername='madhan_001', pages=0)
scrobbles_df = scrobbles_dict['complete']
```
### config.yaml

This file must contain the API keys for last.fm and spotify.

```yaml
#spotify api credentials (visit https://developer.spotify.com)
sp_cid:  #spotify client ID
sp_secret:  #spotify client secret
#last.fm api key (visit https://www.last.fm/api)
lf_key:  #last.fm API key
#filepath for log file
log_path: '\logs\\output.log' #path for output.log
```
## Documentation 

### initialize(cfgPath)
Calls functions needed for initialization, handles loading config file,
initializing logger object, initializing Spotipy object.

Visit the link displayed and login with your Spotify account, copy and paste the redirect url back into the Python prompt.

To be called before calling other functions.

    :param cfgPath: filepath for config.yaml

### generate_dataset(lfusername, timezone='Asia/Kolkata', pages=0)
Gets user's listening history and enriches it with Spotify audio features.
    
    :param lfusername: last.fm username
    :param timezone: timezone of the user (must correspond with the timezone in user's settings)
    :param pages: number of pages to retrieve, use pages = 0 to retrieve full listening history
    
    :return scrobblesDFdict: dictionary with two dataframes ('complete' with timestamps and 'library' with library contents)

Warning : Does not support multiple timezones for scrobbles    
   
### get_playlist(user='billboard.com', playlist_id='6UeSakyzhiEt4NB3UAd6NQ')

Retrieves audio features of a playlist (Billboard Hot 100 is the default playlist)
    
    :param user: username of the playlist owner
    :param playlist_id: playlist id (found at the end of a playlist url)
    
    :return: a dataframe with audio features of a playlist
    
### unmapped_tracks(scrobblesDF)

Returns a dataframe tracks that couldn't be mapped to spotify.

    :param scrobblesDF: dataframe with scrobbled tracks and trackIDs
    
    :return scrobblesDF: dataframe containing tracks with no trackIDs

## Reporting issues

If you have suggestions, bugs or other issues specific to this library, file an issue on GitHub. Or just send me a pull request.
