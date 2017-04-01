# Plex to MyAnimeList Sync

If you have manage your Anime library via Plex this will allow you to sync your library to MyAnimeList.net, recommend using Plex with the HAMA agent for best Anime name matches.

### Step 1 - Locate your unique Plex token:

https://support.plex.tv/hc/en-us/articles/204059436-Finding-an-authentication-token-X-Plex-Token

### Step 2 - Find the library ID

Easiest way is to open your Plex "Anime" section and look in the url for```sections=1``` or ```sections%2F1&``` both meaning section ID 1.

Now we have everything we need to sync Plex with MyAnimeList, by default new entries get added as "Planned to Watch" as that is the only state MyAnimeList list that would fit it as it lacks something like collected:

### Command line arguments

```PlexMALSync.exe <MAL_USERNAME> <MAL_PASSWORD> <PLEX_HOST:PORT OR PLEX_IP:PORT> <PLEX_TOKEN> <PLEX_SECTION_ID>```

### Example

```PlexMALSync.exe John Doe 127.0.0.1:32400 001000100FF 1```

If you have multiple Plex section IDs can separate them with a comma like so:

```PlexMALSync.exe John Doe 127.0.0.1:32400 001000100FF 1,2,3,4```
