# Plex to MyAnimeList Sync
![Logo](logo.png)

If you manage your Anime with Plex this will allow you to sync your libraries to MyAnimeList.net, recommend using Plex with the [HAMA agent](https://github.com/ZeroQI/Hama.bundle) for best Anime name matches.

Unwatched Anime in Plex will not be synced so only those that have at least one watched episode, updates to MAL are only send with changes so need to worry about messing up watch history.

Currently planned for future releases:

- [x] CLI improvements (colors / status)
- [ ] Improve error handling
- [ ] Improve matching by using more MAL info, year comparision is an option but was hit and miss during testing before
- [ ] Multiple season support, right now sync is limited to season 1 and not sure if feasible with the way MAL lists them 

Previous version was written in C# (.NET) but due to library issues switched to Python where there are some great ones to work with, this is the first version and rough around the edges so bugs may occur.

## Installation

### Step 1 - Configuration

From the project directory copy the example settings file `settings.ini.example` to `settings.ini`, open `settings.ini` with your favorite editor and edit where needed.

For the Direct IP authentication method you need to find your token manually:

https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/

### Step 2 - Install requirements

Install requirements from using this python command in the project folder:

`pipenv install`

**Note:** This requires [pipenv](https://docs.pipenv.org/) to be installed.

### Step 3 - Start syncing

Now that configuration is finished and requirements have been installed we can finally start the sync script:

`pipenv run python PlexMALSync.py`

Or for development purposes activate the pipenv shell first:

```shell
pipenv shell
python PlexMALSync.py
```

Depending on library size and server can take a few minutes to finish, logging is verbose at the moment but will show the progress per show and when finished.

### Updating

Besides the usual git clone / pull it it's recommended to update the requirements afterwards as well, you can do using this python command in the project folder:

`pipenv update`

## Requirements

[Python 3 (tested with 3.6.4)](https://www.python.org/)

## Support

Support thread is located on Plex Forums:

https://forums.plex.tv/discussion/305261/plexmalsync-sync-your-plex-library-to-myanimelist

## Additional scripts

In the scripts directory you will find additional scripts  for use in third party software.

#### Scrobble.py
Scrobble single show. 

Parameters:

`scrobble.py <mal_username> <mal_password> <show_title> <watched_episode#>`

Example usage:

`scrobble.py John Doe "Darling in the FranXX" 2`

## Credits

[Python-PlexAPI](https://github.com/pkkid/python-plexapi)

[Spice](https://github.com/Utagai/spice)
