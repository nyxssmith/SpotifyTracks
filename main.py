from fastapi import FastAPI
from fastapi.responses import HTMLResponse,RedirectResponse
import requests
import uvicorn
import threading
import time
from savify import Savify
from savify.types import Type, Format, Quality
from savify.utils import PathHolder
import logging

# static info
client_id=""
client_secret=""
# local address
redirect_uri="http://localhost:8762/callback/"

# access token and ttl
global access_token
access_token = ""
global ttl
ttl = 0

from savify.logger import Logger

# interval to check in seconds
global song_tracker_interval
song_tracker_interval = 1800 # 30 min

global song_download_interval
song_download_interval = 120 # check every 2 min to download or not

song_download_dir = "/downloads"
song_db_dir = "/db"

app = FastAPI()


savify_logger = Logger(log_location='path/for/logs', log_level=logging.INFO) # Silent output

global Savifyer
Savifyer = Savify(ydl_options={},api_credentials=(client_id,client_secret),path_holder=PathHolder(downloads_path=song_download_dir),logger=savify_logger)
"""
Savifyer = Savify(api_credentials=(client_id,client_secret),
                  quality=Quality.BEST,
                    download_format=Format.MP3,
                      path_holder=PathHolder(downloads_path=song_download_dir),
                        group='%artist%/%album%',
                          quiet=False,
                            skip_cover_art=False,
                              log_level=logging.INFO)
"""
# init sqlite
import sqlite3
global con
con = sqlite3.connect( song_db_dir+"/songs.db",check_same_thread=False)


def init_db():
    global con
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS songs(track,downloaded);")
    res = cur.execute("SELECT * FROM songs")
    print(len(res.fetchall()))

def add_track_to_db(track):
    global con
    cur = con.cursor()
    #print("adding track maybe "+track)

    query = 'SELECT EXISTS (SELECT track,downloaded FROM songs WHERE track="'+track+'")'
    res = cur.execute(query)
    # if the exists returned 0 then add it to the db
    if not res.fetchone()[0]:
        cur.execute("INSERT INTO songs VALUES (?,?)",(track,0))
        con.commit()
        print("added new track "+track)

def mark_as_downloaded(track,status):
    global con
    cur = con.cursor()
    query = 'UPDATE songs SET downloaded = '+str(status)+' WHERE track = "'+track+'"'
    cur.execute(query)
    con.commit()
    print("marked "+track+" as downloaded")




def get_next_track_to_download():
    global con
    cur = con.cursor()
    # downloaded = 0 is the default state
    query = 'SELECT track FROM songs WHERE downloaded=0 LIMIT 1;'
    res = cur.execute(query)
    # if the exists returned 0 then add it to the db
    track = res.fetchone()
    # if got any track that wasnt downloaded yet then change to its id
    # also check that track isnt NoneType
    if (type(track) is not type(None)) and len(track) > 0:
        track = track[0]
    else:
        # skip
        return ""
    return track

# start the DB
init_db()

def get_recents():
    # get recently played tracks
    global access_token
    headers = {
    'Authorization': "Bearer "+access_token,
    }
    try:
        response = requests.get('https://api.spotify.com/v1/me/player/recently-played', headers=headers)
    except:
        print("failed to get recently played, setting ttl to 0 and trying again")
        print(ttl)
        ttl = 0
        return {}
    # get recents
    recents = response.json()

    #print(recents)
    return recents



class BackgroundSongTracker(threading.Thread):
    def run(self,*args,**kwargs):
        while True:
            print('Getting recent songs')
            # only gets songs if authed
            if ttl != 0:
                # get recent songs
                recents = get_recents()
                for recent in recents["items"]:
                    try:
                        # get the spotify track from the url
                        track = recent["track"]["external_urls"]["spotify"].split('/')[-1]
                        # add it to the database as not downloaded
                        add_track_to_db(track)
                        
                    except Exception as e:
                        print(e)
    
            global song_tracker_interval
            time.sleep(song_tracker_interval)

class BackgroundSongDownloader(threading.Thread):
    def run(self,*args,**kwargs):
        while True:
            print('Getting songs to download')
            just_downloaded = False
            track_to_download = get_next_track_to_download()
            if track_to_download!="":
                print("downloading "+track_to_download)
                spotify_url = "https://open.spotify.com/track/"+track_to_download
                downloaded_status = 1
                try:
                    global Savifyer
                    Savifyer.download(spotify_url)
                except Exception as e:
                    print(e)
                    # if it fails, set downloaded to 2 aka failed downloads
                    downloaded_status = 2
                mark_as_downloaded(track_to_download,downloaded_status)
                just_downloaded = True
            if not just_downloaded:
                global song_download_interval
                time.sleep(song_download_interval)


def get_access_token(auth_code: str):
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
        },
        auth=(client_id, client_secret),
    )
    global access_token
    access_token = response.json()["access_token"]
    global ttl
    ttl = response.json()["expires_in"]
    return access_token




@app.get("/download")
def downloadtest():
    track_to_download = get_next_track_to_download()
    if track_to_download!="":
        print("get downloading "+track_to_download)
        # TODO rm this debug
        #track_to_download = "3MYWKl8ScgDu3sAvyneMCG"
        spotify_url = "https://open.spotify.com/track/"+track_to_download
        downloaded_status = 1
        try:
            global Savifyer
            Savifyer.download(spotify_url)
        except Exception as e:
            print(e)
            # if it fails, set downloaded to 2 aka failed downloads
            downloaded_status = 2
        mark_as_downloaded(track_to_download,downloaded_status)
       

    return track_to_download


@app.get("/auth")
async def auth():
    scope = ["user-read-recently-played"]
    auth_url = f"https://accounts.spotify.com/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={' '.join(scope)}"
    return HTMLResponse(content=f'<a href="{auth_url}">Authorize</a>')

@app.get("/")
async def index():
    # this is treated as main in the loop

    # if TTL is low, get a new one
    global ttl
    if ttl <= 60:
        scope = ["user-read-recently-played"]
        auth_url = f"https://accounts.spotify.com/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={' '.join(scope)}"
        return RedirectResponse(url=auth_url, status_code=303) 
    # same as main loop
    # get recents json
    recents = get_recents()
    for recent in recents["items"]:
        try:
            # get the spotify url
            #print(recent["track"]["external_urls"]["spotify"])
            track = recent["track"]["external_urls"]["spotify"].split('/')[-1]
            #print("track "+track)
            add_track_to_db(track)
            # TODO a method that uses savify to save the song
            # TODO   ^ also adds the track ID at the end of the url to the db for songs downloaded
            
        except Exception as e:
            print(e)
        
    if recents == {}:
        RedirectResponse(url="/", status_code=303) 
    
    return recents


@app.get("/callback")
async def callback(code):
    # redirect here from spotify
    global ttl
    if ttl <= 60:
        get_access_token(code)
    global access_token
    headers = {"Authorization": "Bearer " + access_token}

    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_id = response.json()["id"]

    # redirect to / to then do main part
    return RedirectResponse(url="/", status_code=303) 



if __name__ == "__main__":
    #uvicorn.run(app, debug=True)
    tracker = BackgroundSongTracker()
    tracker.start()
    downloader = BackgroundSongDownloader()
    downloader.start()
    try:
        uvicorn.run(app, host="0.0.0.0", port=8762)
    except KeyboardInterrupt:
        pass
        tracker.join()
        downloader.join()
        #t.join()
        

























# run main
#if __name__ == "__main__":
#    get_access_token()
#    uvicorn.run(app, host="0.0.0.0", port=8762)
