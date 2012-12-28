streamergw
==========

Gateway for network streams of Livestreamer and sopcast

Install
-------

You need Livestreamer (https://github.com/chrippa/livestreamer) and optionally Sopcast, only the cli client sp-sc, (http://www.sopcast.com/download/) (if you are in Ubuntu you can use this repo: https://launchpad.net/~venerix/+archive/blug, install only sp-auth). You also need twisted.

To install just run: (sudo) python setup.py install

Run
---

Once installed, run with the command: streamergw

To start a stream, open your player (f.e. VLC) and open the open stream dialog. The address of the stream you have to use is:

http://[ip-of-machine]:8080/[livestreamer/sopcast]?[options]

[ip-of-machine] is the ip of the machine that is running streamergw

[livestreamer/sopcast] you have to chose which one you want

[options] If sopcast is selected you have only one option url, the channel you want to open. If livestreamer is selected you have two options url, same, and stream, the quality you want to select. There are also options to get info (check the code).

For example, if you want to open the sopcast channel sop://broker.sopcast.com:3912/74841 and the ip of the machine running streamergw is 192.168.1.10, you have to insert into VLC (or whatever player you are using) stream network dialog:

http://192.168.1.10:8080/sopcast?url=sop://broker.sopcast.com:3912/74841

If you want to open a stream obtained via Livestreamer, for example some SC2 twitch.tv stream:

http://192.168.1.10:8080/livestreamer?stream=720p&url=http://ca.twitch.tv/esltv_sc2

Finally
-------

I just coded this in my free time during Christmas. The code is working fine in my home but its untested otherwise.

The next step is to create a basic HTML5+javascript client that allows to get the stream or sopcast channels without the need to introduce "ugly" url's into the player. After that, my idea is to add UPNP support, probably through Rygel. Btw, fuck DLNA. The sopcast part of the code will probably change once this is done.
