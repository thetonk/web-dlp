#!/bin/bash

chown -R www-data:www-data web/outputs/*.mp3
mv web/outputs/*.mp3 Library
eval echo 'sudo -u www-data php $OCC_PATH files:scan --path "$NC_USER/files/$NC_MUSIC_DIRECTORY" '>/config/mypipe
eval echo 'sudo -u www-data php $OCC_PATH music:scan $NC_USER' > /config/mypipe &
wait