import configparser
import os
import sys
import spice_api as spice
from colorama import init, Fore, Back, Style
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

## Colorrama
init()

## Settings

settings_location = 'settings.ini'
if(not os.path.isfile(settings_location)):
  sys.exit('[CONFIG] Settings file file not found: %s' % (settings_location))

settings = configparser.ConfigParser()
settings.read(settings_location)
plex_section = settings['PLEX']
mal_section = settings['MAL']

# Plex
plex = None
plex_authentication_method = plex_section['authentication_method']

if(plex_authentication_method.lower() == 'direct'):
  baseurl = plex_section['base_url']
  token = plex_section['token']
  plex = PlexServer(baseurl, token)
elif(plex_authentication_method.lower() == 'myplex'):
  plex_server = plex_section['server']
  plex_user = plex_section['myplex_user']
  plex_password = plex_section['myplex_password']
  print('Attempting login')
  account = MyPlexAccount(plex_user, plex_password)
  plex = account.resource(plex_server).connect()
  print('Login completed')

if(plex == None):
  sys.exit(Back.RED + '[PLEX] Failed to authenticate due to invalid settings or authentication info, exiting...')

plex_anime_section = plex_section['anime_section']

# MyAnimeList
mal_username = mal_section['username']
mal_password = mal_section['password']
mal_credentials = spice.init_auth(mal_username, mal_password)

if(mal_credentials == None):
  sys.exit(Back.RED + '[MAL] Failed to authenticate, exiting...')

def get_anime_shows():
  print('[PLEX] Retrieving anime shows...')
  anime_shows = []
  show_count = 0
  shows = plex.library.section(plex_anime_section)
  for show in shows.search():
    anime_shows.append(show.title)
    show_count += 1

  print(Back.BLUE + '[PLEX] Retrieving of %s anime shows completed' % (show_count))
  return anime_shows

def get_plex_watched_shows(lookup_shows):
  watched_shows = dict()
  print(Back.BLUE +'[PLEX] Retrieving watch count for shows...')

  for show in lookup_shows:
    lookup_show = plex.library.section(plex_anime_section).get(show).episodes()
    watched_episode_count = 0
    for lookup_result in lookup_show:
        try:
          if(lookup_result.isWatched and lookup_result.seasonNumber is 1):
            #print("%sx%s - watched = %s" % (lookup_result.seasonNumber, lookup_result.index, lookup_result.isWatched))
            watched_episode_count += 1
        except:
          print(Back.RED +'Error during lookup_result processing')
          pass
    if(watched_episode_count > 0):
        watched_shows[show] = watched_episode_count
        #print('Watched %s episodes for show: %s' % (str(watched_episode_count), show))

  print(Back.BLUE +'[PLEX] Retrieving watch count for shows finished')
  return watched_shows

def get_mal_list():
  mal_list = spice.get_list(spice.get_medium('anime'), mal_username, mal_credentials).get_mediums()

  return mal_list

def send_watched_to_mal(watched_shows, mal_list):
  for key, value in watched_shows.items():
    plex_title = key
    watched_episode_count = value
    show_in_mal_list = False;
    #print('%s => watch count = %s' % (plex_title, watched_episode_count))

    if(watched_episode_count <= 0 ):
        continue

    mal_watched_episode_count = 0
    mal_show_id = 0

    # check if show is already on MAL list
    for list_item in mal_list:
      #print('Comparing %s with %s' % (list_item.title, plex_title))
      mal_id =int(list_item.id)
      mal_title = list_item.title
      mal_title_english = ""

      if(list_item.english is not None):
        mal_title_english = list_item.english
        #print('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, plex_title))
      else:
        #print('Comparing original: %s with %s' % (mal_title, plex_title))
        pass

      if(mal_title.lower() == plex_title.lower() or mal_title_english.lower() == plex_title.lower()):
        #print('%s [%s] was already in list => status = %s | watch count = %s' % (plex_title, list_item.id, spice.get_status(list_item.status), list_item.episodes))
        mal_watched_episode_count = int(list_item.episodes)
        mal_show_id = int(list_item.id)
        show_in_mal_list = True
         
        if(mal_watched_episode_count > 0 and mal_show_id > 0):
          if(mal_watched_episode_count < watched_episode_count):
            anime_new = spice.get_blank(spice.get_medium('anime'))
            anime_new.episodes = watched_episode_count
            new_status = 'watching'

            # if full watched set status to completed, needs additional lookup as total episodes are not exposed in list (mal or spice limitation)
            lookup_show = spice.search_id(mal_id, spice.get_medium('anime'), mal_credentials)
            if(lookup_show):
              if(lookup_show.episodes is not None):
                mal_total_episodes = int(lookup_show.episodes)

                if(watched_episode_count >= mal_total_episodes):
                  new_status = 'completed'

            anime_new.status =  spice.get_status(new_status)

            print(Back.MAGENTA +'[PLEX -> MAL] Watch count for %s on Plex is %s and MAL is %s, gonna update MAL watch count to %s and status to %s ]' % (plex_title, watched_episode_count,
            mal_watched_episode_count, watched_episode_count, new_status))
            spice.update(anime_new, mal_show_id, spice.get_medium('anime'), mal_credentials)
          else:
            print(Back.GREEN + '[PLEX -> MAL] Watch count for %s on Plex was equal or higher on MAL so skipping update' % (plex_title))
            pass

    # if not listed in list lookup on MAL
    if(not show_in_mal_list):
      found_result = False
      update_list = True
      on_mal_list = False
      print(Back.CYAN + '[PLEX -> MAL] %s not in MAL list, gonna search for show on MAL' % (plex_title))

      mal_shows = spice.search(plex_title,spice.get_medium('anime'),mal_credentials)
      for mal_show in mal_shows:
        mal_title = mal_show.title.lower()
        mal_title_english = ''
        mal_show_id = int(mal_show.id)
        mal_total_episodes = int(mal_show.episodes)

        if(mal_show.english is not None):
          mal_title_english = mal_show.english.lower()
          #print('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, plex_title.lower()))
        else:
          #print('Comparing original: %s with %s' % (mal_title, plex_title.lower()))
          pass

        if(mal_title == plex_title.lower() or mal_title_english == plex_title.lower()):
          found_result = True

          # double check against MAL list using id to see if matches and update is required
          for list_item in mal_list:
            mal_list_id =int(list_item.id)
            mal_list_watched_episode_count = int(list_item.episodes)

            if(mal_list_id == mal_show_id):
              on_mal_list = True;
              if(watched_episode_count == mal_list_watched_episode_count):
                print(Back.GREEN +'[PLEX -> MAL] show was found in current MAL list using id lookup however watch count was identical so skipping update')
                update_list = False
              break

          if(update_list):
            print(Back.MAGENTA +'[PLEX -> MAL] Found match on MAL and setting state to watching with watch count: %s' % (watched_episode_count))
            anime_new = spice.get_blank(spice.get_medium('anime'))
            anime_new.episodes = watched_episode_count

            if(watched_episode_count >= mal_total_episodes):
                anime_new.status = spice.get_status('completed')
                if(on_mal_list):
                  spice.update(anime_new, mal_show.id, spice.get_medium('anime'), mal_credentials)
                else:
                  spice.add(anime_new, mal_show.id, spice.get_medium('anime'), mal_credentials)
            else:
                anime_new.status = spice.get_status('watching')
                if(on_mal_list):
                  spice.update(anime_new, mal_show.id, spice.get_medium('anime'), mal_credentials)
                else:
                  spice.add(anime_new, mal_show.id, spice.get_medium('anime'), mal_credentials)
          break

      if(not found_result):
        print(Back.LIGHTRED_EX + '[PLEX -> MAL] Failed to find %s on MAL' % (plex_title))

def start():
  print(Back.BLUE + 'Started Plex to MAL sync...')

  # get MAL list
  mal_list = get_mal_list()

  # get anime shows from Plex library
  shows = get_anime_shows()

  # get watched info for anime shows from Plex library
  watched_shows = get_plex_watched_shows(shows)

  # finally compare lists and update MAL where needed
  send_watched_to_mal(watched_shows, mal_list)

  print(Back.BLUE + 'Plex to MAL sync finished')

# start main process
start()
