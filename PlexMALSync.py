from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from time import sleep
import spice_api as spice

#### Configuration ####

### Authentication (Plex / MyAnimeList) ##
## Plex (choose only one) ##

# Option 1 - MyPlex (~15s login time)
#plex_server = 'Sadala'
#plex_user = 'John'
#plex_password = 'Doe'
#print('Attempting login')
#account = MyPlexAccount(plex_user, plex_password)
#plex = account.resource(plex_server).connect()
#print('Login completed')

# Option 2 - Direct IP method (fastest)
baseurl = 'http://10.1.2.3:32400'
token = '1234abcde'
plex = PlexServer(baseurl, token)

## MyAnimeList ##
mal_username = 'John'
mal_password = 'Doe'
mal_credentials = spice.init_auth(mal_username, mal_password)

### Plex section - enter the library / section name used for Anime ###
plex_anime_section = 'Anime'

#### Configuration END ####

####
#### Do not edit anything below unless you know what you're doing ####
####


def get_mal_list():
  mal_list = spice.get_list(spice.get_medium('anime'), mal_username, mal_credentials).get_mediums()

  return mal_list

def get_anime_shows():
  print('[PLEX] Retrieving anime shows...')
  anime_shows = []
  show_count = 0
  shows = plex.library.section(plex_anime_section)
  for show in shows.search():
    anime_shows.append(show.title)
    show_count += 1
  print('[PLEX] Retrieving of %s anime shows completed' % (show_count))

  return anime_shows

def get_plex_watched_shows(lookup_shows):
  watched_shows = dict()
  print('[PLEX] Retrieving watch count for shows...')

  for show in lookup_shows:
    lookup_show = plex.library.section(plex_anime_section).get(show).episodes()
    watch_count = 0
    for lookup_result in lookup_show:
        try:
          if(lookup_result.isWatched and lookup_result.seasonNumber is 1):
            #print("%sx%s - watched = %s" % (lookup_result.seasonNumber, lookup_result.index, lookup_result.isWatched))
            watch_count += 1
        except:
          print('Error during lookup_result processing')
          pass
    if(watch_count > 0):
        watched_shows[show] = watch_count
        #print('Watched %s episodes for show: %s' % (str(watch_count), show))

  print('[PLEX] Retrieving watch count for shows finished')
  return watched_shows

def send_watched_to_mal(watched_shows, mal_list):
  for key, value in watched_shows.items():
    show_title = key
    watch_count = value
    show_is_listed = False;
    #print('%s => watch count = %s' % (show_title, watch_count))

    mal_watch_count = 0
    mal_show_id = 0

    # check if show is already on MAL list
    for list_item in mal_list:
      #print('Comparing %s with %s' % (list_item.title, show_title))
      mal_title = list_item.title.lower()
      mal_title_english = ''
      if(list_item.english is not None):
        mal_title_english = list_item.english.lower()
        #print('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, show_title.lower()))
      else:
        #print('Comparing original: %s with %s' % (mal_title, show_title.lower()))
        pass

      if(mal_title == show_title.lower() or mal_title_english == show_title.lower()):
        #print('%s [%s] was already in list => status = %s | watch count = %s' % (show_title, list_item.id, spice.get_status(list_item.status), list_item.episodes))
        mal_watch_count = int(list_item.episodes)
        mal_show_id = int(list_item.id)
        show_is_listed = True

        if(mal_watch_count > 0 and mal_show_id > 0):
          if(watch_count > mal_watch_count):
            print('[PLEX -> MAL] Watch count for %s on Plex is %s and MAL is %s, gonna update on MAL' % (show_title, watch_count, mal_watch_count))
            anime_new = spice.get_blank(spice.get_medium('anime'))
            anime_new.episodes = watch_count
            spice.update(anime_new, mal_show_id, spice.get_medium('anime'), mal_credentials)
          elif(watch_count == mal_watch_count):
            print('[PLEX -> MAL] Watch count for %s on Plex is %s and MAL is %s, gonna update on MAL' % (show_title, watch_count, mal_watch_count))
            anime_new = spice.get_blank(spice.get_medium('anime'))
            anime_new.episodes = watch_count
            anime_new.status = spice.get_status('completed')
            spice.update(anime_new, mal_show_id, spice.get_medium('anime'), mal_credentials)

          else:
            print('[PLEX -> MAL] Watch count for %s on Plex was equal on MAL so skipping update' % (show_title))
            pass

    # if not listed in list lookup on MAL
    if(not show_is_listed):
      if(watch_count > 0):
        print('[PLEX -> MAL] %s not in MAL list, gonna search for show on MAL' % (show_title))

        mal_shows = spice.search(show_title,spice.get_medium('anime'),mal_credentials)
        for mal_show in mal_shows:
          mal_title = mal_show.title.lower()
          mal_title_english = ''
          if(mal_show.english is not None):
            mal_title_english = mal_show.english.lower()
            #print('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, show_title.lower()))
          else:
            #print('Comparing original: %s with %s' % (mal_title, show_title.lower()))
            pass

          if(mal_title == show_title.lower() or mal_title_english == show_title.lower()):
            if(watch_count > mal_watch_count):
                print('[PLEX -> MAL] Found match on MAL and setting state to completed with watch count: %s' % (watch_count))
                anime_new = spice.get_blank(spice.get_medium('anime'))
                anime_new.episodes = watch_count
                anime_new.status = spice.get_status('watching')
                spice.add(anime_new, mal_show.id, spice.get_medium('anime'), mal_credentials)
            elif(watch_count == mal_watch_count):
                print('[PLEX -> MAL] Found match on MAL and setting state to watching with watch count: %s' % (watch_count))
                anime_new = spice.get_blank(spice.get_medium('anime'))
                anime_new.episodes = watch_count
                anime_new.status = spice.get_status('watching')
                spice.add(anime_new, mal_show.id, spice.get_medium('anime'), mal_credentials)


            break
      else:
        print('[PLEX -> MAL] %s not in MAL list but had 0 watched so gonna skip update', show)

def init():
  print('Started Plex to MAL sync...')

  # get MAL list
  mal_list = get_mal_list()

  # get anime shows from Plex library
  shows = get_anime_shows()

  # get watched info for anime shows from Plex library
  watched_shows = get_plex_watched_shows(shows)

  # finally compare lists and update MAL where needed
  send_watched_to_mal(watched_shows, mal_list)

  print('Plex to MAL sync finished')

# start main process
init()
