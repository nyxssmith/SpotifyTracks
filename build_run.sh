#!/bin/bash

name="nyxssmith/spotify_tracks"
build_dir="."
dockerfile=$(pwd)/dockerfile

docker build -t $name -f $dockerfile $build_dir
python3 db.py
#docker run -it --rm -v $(pwd)/songs.db:/db/songs.db -v $(pwd)/downloads:/downloads:Z -p 8762:8762 $name

docker push $name:latest
