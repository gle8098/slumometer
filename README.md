# Slumometer
Slumometer is a telegram bot that reminds you to change the linen. An instance of this bot
is running `@slumometerbot` and it is for 2ka MIPT campus dormitory.

The name is a combination of words "slum" and "meter". I called it that because the original
idea of the bot was to calculate calculate how poor the living conditions are based on the
temperature, humidity and carbon dioxide concentration in the dormitory room (or slum). 
 
## How to run
This bot is shipped with Docker. It is uploaded at `gle8098 / slumometer` on Docker Hub. You can
run bot as follow.

    docker run -d \
            --name=slumometer \
            --net=host \
            --restart=always \
            --mount type=volume,source=slumometer_data,target=/bot/data \
            <bot token> [admin key]
To update to a new version of the bot, simply remove `slumometer` container and run the command
again. 
