import configparser
import coloredlogs
import logging
import os
import sys
import spice_api as spice
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

## Logger

logger = logging.getLogger('PlexMALSync')

## Enable this if you want to also log all messages coming from imported libraries
#coloredlogs.install(level='DEBUG')

coloredlogs.install(fmt='%(asctime)s %(message)s', logger=logger)  

## Settings

settings_location = 'settings.ini'
if(not os.path.isfile(settings_location)):
  logger.critical('[CONFIG] Settings file file not found: %s' % (settings_location))
  sys.exit()

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
  logger.info('Attempting login')
  account = MyPlexAccount(plex_user, plex_password)
  plex = account.resource(plex_server).connect()
  logger.info('Login completed')

if(plex == None):
  logger.critical('[PLEX] Failed to authenticate due to invalid settings or authentication info, exiting...')
  sys.exit()

plex_anime_section = plex_section['anime_section']

# MyAnimeList
mal_username = mal_section['username']
mal_password = mal_section['password']
mal_credentials = spice.init_auth(mal_username, mal_password)

if(mal_credentials == None):
  logger.critical('[MAL] Failed to authenticate, exiting...')
  sys.exit()

def get_anime_shows():
  logger.info('[PLEX] Retrieving anime shows...')
  anime_shows = []
  show_count = 0
  shows = plex.library.section(plex_anime_section)
  for show in shows.search():
    anime_shows.append(show.title)
    show_count += 1

  logger.info('[PLEX] Retrieving of %s anime shows completed' % (show_count))
  return anime_shows

def get_plex_watched_shows(lookup_shows):
  watched_shows = dict()
  logger.info('[PLEX] Retrieving watch count for shows...')

  for show in lookup_shows:
    lookup_show = plex.library.section(plex_anime_section).get(show).episodes()
    # watched_episode_count = (episode count, season number)
    watched_episode_count = (0,1)
    for lookup_result in lookup_show:
        try:
          #if(lookup_result.isWatched and lookup_result.seasonNumber is 1):
          if (lookup_result.isWatched):
            #logger.debug("%sx%s - watched = %s" % (lookup_result.seasonNumber, lookup_result.index, lookup_result.isWatched))
            #watched_episode_count += 1
            if ((lookup_result.index > watched_episode_count[0] and lookup_result.seasonNumber == watched_episode_count[1]) or (lookup_result.seasonNumber > watched_episode_count[1])):
              watched_episode_count = (lookup_result.index,lookup_result.seasonNumber)
        except:
          logger.error(Back.RED +'Error during lookup_result processing')
          pass
    if(watched_episode_count[0] > 0):
        watched_shows[show] = watched_episode_count
        logger.info('Watched %s episodes of show: %s' % (str(watched_episode_count[0]), show))

  logger.info('[PLEX] Retrieving watch count for shows finished')
  return watched_shows

def get_mal_list():
  logger.info('[MAL] Retrieving list...')
  mal_list = spice.get_list(spice.get_medium('anime'), mal_username, mal_credentials).get_mediums()
  item_count = 0
  if(mal_list is not None):
    item_count = len(mal_list)
  logger.info('[MAL] Found %s shows on list' % (str(item_count)))
  return mal_list


#compare entries by their name to see if they're different seasons from the same show, then populate the mal_list with additional entries to mark the season.
#does not use splice.search, but is an N² search so very inefficient (since we don't know at first which is the original name)
#TODO: clean garbage (repeated entries) from list. isn't a problem since we just need to match with the plex name and season.
#for whatever reason, splice has problems populating list attributes so I needed to go back to raw_data
def match_seasons_on_mal_list(mal_list):
  logger.info('[MAL] Matching seasons inside MAL list...')
  mal_list_seasoned = list()

  for watched_show in mal_list:
    # type 1 indicates TV.
    if (watched_show.raw_data.contents[3].contents[0] != '1'):
      continue
    matched_list = list()
    mal_title = str(watched_show.raw_data.contents[1].contents[0]).lower()
    for matching_watched_show in mal_list:
      if (matching_watched_show.raw_data.contents[3].contents[0] == '1'):
        #Later seasons have longer names, e.g. "original_name 2/Final/Second Stage/!!"
        #Only the original season should have a list properly populated
        if mal_title in str(matching_watched_show.raw_data.contents[1].contents[0]).lower():
          match = (matching_watched_show,str(matching_watched_show.raw_data.contents[7].contents[0]) if str(matching_watched_show.raw_data.contents[7].contents[0]) != '0000-00-00' else '9999-99-99' )
          matched_list.append(match)
    matched_list.sort(key=lambda x: x[1])
    
    original_name = [x[0].title for x in matched_list if x[1] != '9999-99-99']
    #can't do miracles if it's all empty
    if (not original_name):
      original_name_treated = matched_list[0][0].title
    else:
      original_name_treated = original_name[0]
    for index,element in enumerate(matched_list):
      mal_list_seasoned.append((element[0],index+1,original_name_treated)) 
  logger.info('[MAL] Matching seasons inside MAL list finished')
  return mal_list_seasoned
  

  
#update_mal_list_with_seasons: complete list with all seasons for watched shows and later compare by season.
# these are seasons defined by MAL. 1 season MIGHT mean a continuous run of many AniDB/TVDB seasons, per MAL standards.
# plex_watched_shows only uses the original name.
def update_mal_list_with_seasons(mal_list_seasoned,plex_watched_shows):
  logger.info('[MAL] Retrieving updated list for season matching...')
  mal_list_seasoned_updated = [(x[0],x[1],x[2],'on_mal_list') for x in mal_list_seasoned]
  for watched_show in plex_watched_shows.keys():
    watched_show_season = plex_watched_shows[watched_show][1]
    matches_in_mal_list_seasoned = list()
    matches_in_mal_list_seasoned = [x for x in mal_list_seasoned if x[2].lower() == watched_show.lower() and x[1] == watched_show_season]
    #only search for shows not already in list
    if (bool(matches_in_mal_list_seasoned) or watched_show_season == 1):
      continue
    mal_shows = spice.search(watched_show,spice.get_medium('anime'),mal_credentials) 
    matched_list = list()
    for mal_show in mal_shows:
      if (mal_show.anime_type == 'TV'):
        match = (mal_show,mal_show.dates[1] if mal_show.dates[1] != '0000-00-00' else '9999-99-99' )
        matched_list.append(match)
    matched_list.sort(key=lambda x: x[1])
    
    original_name = [x[0].title for x in matched_list if x[1] != '9999-99-99']
    #can't do miracles if it's all empty
    if (not original_name):
      original_name_treated = matched_list[0][0].title
    else:
      original_name_treated = original_name[0]
    for index,element in enumerate(matched_list):
      mal_list_seasoned_updated.append((element[0],index+1,original_name_treated,'not_on_mal_list'))
  logger.info('[MAL] Retrieving updated list for season matching finished')
  return mal_list_seasoned_updated


#update an existing match
def update_mal_entry(list_item,plex_title,plex_watched_episode_count,force_update):  
  mal_watched_episode_count = int(list_item.episodes)
  mal_show_id = int(list_item.id)
  if(mal_show_id > 0):
    if(mal_watched_episode_count < plex_watched_episode_count or force_update):
      anime_new = spice.get_blank(spice.get_medium('anime'))
      anime_new.episodes = plex_watched_episode_count
      new_status = 'watching'

      # if full watched set status to completed, needs additional lookup as total episodes are not exposed in list (mal or spice limitation)
      lookup_show = spice.search_id(mal_show_id, spice.get_medium('anime'), mal_credentials)
      if(lookup_show):
        if(lookup_show.episodes is not None):
          mal_total_episodes = int(lookup_show.episodes)

          if(plex_watched_episode_count >= mal_total_episodes):
            new_status = 'completed'

      anime_new.status =  spice.get_status(new_status)

      logger.warn('[PLEX -> MAL] Watch count for %s on Plex is %s and MAL is %s, updating MAL watch count to %s and status to %s ]' % (plex_title, plex_watched_episode_count,
      mal_watched_episode_count, plex_watched_episode_count, new_status))
      spice.update(anime_new, mal_show_id, spice.get_medium('anime'), mal_credentials)
    else:
      logger.warning( '[PLEX -> MAL] Watch count for %s on Plex was equal or higher on MAL so skipping update' % (plex_title))
      pass

def add_mal_entry(list_item,on_mal_list):
  if (on_mal_list == 'not_on_mal_list'):
    logger.warn('[PLEX -> MAL] No MAL entry found for matching season of %s, adding to MAL with status Watching ]' % (list_item.title))

    anime_new = spice.get_blank(spice.get_medium('anime'))
    anime_new.episodes = 0
    new_status = 'watching'
    spice.add(anime_new, int(list_item.id), spice.get_medium('anime'), mal_credentials)


def send_watched_to_mal(plex_watched_shows, mal_list, mal_list_seasoned):
  for key, value in plex_watched_shows.items():
    plex_title = key
    plex_watched_episode_count = value[0]
    plex_watched_episode_season = value[1]
    show_in_mal_list = False
    force_update = False
    #logger.debug('%s => watch count = %s' % (plex_title, watched_episode_count))

    if(plex_watched_episode_count <= 0):
        continue

    mal_watched_episode_count = 0
    mal_show_id = 0

    # all shows with season > 1 were previously searched and are part of the mal_list_seasoned object
    if (plex_watched_episode_season > 1):
      force_update = True
      for anime,season,original_name,on_mal_list in mal_list_seasoned:
        if(original_name.lower() == plex_title.lower()):

          try:
            correct_item = [value[0] for index, value in enumerate(mal_list_seasoned) if value[1] == plex_watched_episode_season and value[2] == original_name][0]
          except:
            #search failed to properly match seasons, e.g. Card Captor Sakura Clear Card is s4 on TVDB and s2 here
            #assume most recent available season
            #TODO: search by ID of the correct season
            if force_update:
              correct_item = spice.search_id(int(mal_list_seasoned[-1][0].id), spice.get_medium('anime'), mal_credentials)
              on_mal_list = 'not_on_mal_list'
            else:
              break
          #trying to add before doens't really break anything and works for new series, since mal_list_seasoned includes things you haven't watched yet
          add_mal_entry(correct_item,on_mal_list)
          update_mal_entry(correct_item,plex_title,plex_watched_episode_count,force_update)
          break
      continue


    # check if show is already on MAL list
    for list_item in mal_list:
      #logger.debug('Comparing %s with %s' % (list_item.title, plex_title))
      mal_id = int(list_item.id)
      mal_title = list_item.title
      mal_title_english = ""
      if(list_item.english is not None):
        mal_title_english = list_item.english
        #logger.debug('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, plex_title))
      else:
        #logger.debug('Comparing original: %s with %s' % (mal_title, plex_title))
        pass

      if(mal_title.lower() == plex_title.lower() or mal_title_english.lower() == plex_title.lower()):
        logger.debug('%s [%s] was already in list => status = %s | watch count = %s' % (plex_title, list_item.id, spice.get_status(list_item.status), list_item.episodes))
        show_in_mal_list = True
        update_mal_entry(list_item,plex_title,plex_watched_episode_count,force_update)

    # if not listed in list lookup on MAL
    if(not show_in_mal_list):
      found_result = False
      update_list = True
      on_mal_list = False
      logger.info('[PLEX -> MAL] %s not in MAL list, searching for show on MAL' % (plex_title))

      mal_shows = spice.search(plex_title,spice.get_medium('anime'),mal_credentials)
      for mal_show in mal_shows:
        mal_title = mal_show.title.lower()
        mal_title_english = ''
        mal_show_id = int(mal_show.id)
        mal_total_episodes = int(mal_show.episodes)

        if(mal_show.english is not None):
          mal_title_english = mal_show.english.lower()
          #logger.debug('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, plex_title.lower()))
        else:
          #logger.debug('Comparing original: %s with %s' % (mal_title, plex_title.lower()))
          pass

        if(mal_title == plex_title.lower() or mal_title_english == plex_title.lower()):
          found_result = True

          # double check against MAL list using id to see if matches and update is required
          for list_item in mal_list:
            mal_list_id =int(list_item.id)
            mal_list_watched_episode_count = int(list_item.episodes)

            if(mal_list_id == mal_show_id):
              on_mal_list = True
              if(plex_watched_episode_count == mal_list_watched_episode_count):
                logger.warning('[PLEX -> MAL] show was found in current MAL list using id lookup however watch count was identical so skipping update')
                update_list = False
              break

          if(update_list):
            logger.warn('[PLEX -> MAL] Found match on MAL and setting state to watching with watch count: %s' % (plex_watched_episode_count))
            anime_new = spice.get_blank(spice.get_medium('anime'))
            anime_new.episodes = plex_watched_episode_count

            if(plex_watched_episode_count >= mal_total_episodes):
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
        logger.error('[PLEX -> MAL] Failed to find %s on MAL' % (plex_title))

def start():
  logger.info('Started Plex to MAL sync...')

  # get MAL list
  mal_list = get_mal_list()

  # get anime shows from Plex library
  plex_shows = get_anime_shows()

  # get watched info for anime shows from Plex library
  plex_watched_shows = get_plex_watched_shows(plex_shows)

  # add seasons to list
  seasoned_list = match_seasons_on_mal_list(mal_list)
  updated_mal_list = update_mal_list_with_seasons(seasoned_list,plex_watched_shows)

  # finally compare lists and update MAL where needed
  send_watched_to_mal(plex_watched_shows, mal_list, updated_mal_list)

  logger.info('Plex to MAL sync finished')

# start main process
start()