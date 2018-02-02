import sys
import spice_api as spice

mal_username = sys.argv[1]
mal_password = sys.argv[2]
show_title = sys.argv[3]
watched_episode_count = sys.argv[4]

mal_credentials = spice.init_auth(mal_username, mal_password)

def get_mal_list():
  mal_list = spice.get_list(spice.get_medium('anime'), mal_username, mal_credentials).get_mediums()
  return mal_list

def send_watched_to_mal(mal_list, show_title, watched_episode_count):
  show_in_mal_list = False;
  mal_watched_episode_count = 0
  mal_show_id = 0

  # check if show is already on MAL list
  for list_item in mal_list:
    #print('Comparing %s with %s' % (list_item.title, show_title))
    mal_id =int(list_item.id)
    mal_title = list_item.title
    mal_title_english = ""
    
    if(list_item.english is not None):
      mal_title_english = list_item.english
      #print('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, show_title))
    else:
      #print('Comparing original: %s with %s' % (mal_title, show_title))
      pass

    if(mal_title.lower() == show_title.lower() or mal_title_english.lower() == show_title.lower()):
      #print('%s [%s] was already in list => status = %s | watch count = %s' % (show_title, list_item.id, spice.get_status(list_item.status), list_item.episodes))
      mal_watched_episode_count = int(list_item.episodes)
      mal_show_id = int(list_item.id)
      show_in_mal_list = True

      if(mal_watched_episode_count > 0 and mal_show_id > 0):
        if(watched_episode_count != mal_watched_episode_count):
          anime_new = spice.get_blank(spice.get_medium('anime'))
          anime_new.episodes = watched_episode_count
          new_status = 'watching'

          # if full watched set status to completed, needs additional lookup as total episodes are not exposed in list (mal or spice limitation)
          lookup_show = spice.search_id(mal_id, spice.get_medium('anime'), mal_credentials)
          if(lookup_show):     
            if(lookup_show.episodes is not None):
              total_episodes = int(lookup_show.episodes)

              if(watched_episode_count >= total_episodes):
                new_status = 'completed'         

          anime_new.status =  spice.get_status(new_status)

          print('[PLEX -> MAL] Watch count for %s on Plex is %s and MAL is %s, gonna update  MAL watch count to %s and status to %s ]' % (show_title, watched_episode_count,
          mal_watched_episode_count, mal_watched_episode_count, new_status))
          spice.update(anime_new, mal_show_id, spice.get_medium('anime'), mal_credentials)
        else:
          print('[PLEX -> MAL] Watch count for %s on Plex was equal on MAL so skipping update' % (show_title))
          pass

  # if not listed in list lookup on MAL
  if(not show_in_mal_list):
    found_result = False
    update_list = True
    print('[PLEX -> MAL] %s not in MAL list, gonna search for show on MAL' % (show_title))

    mal_shows = spice.search(show_title,spice.get_medium('anime'),mal_credentials)
    for mal_show in mal_shows:
      mal_title = mal_show.title.lower()
      mal_title_english = ''
      mal_show_id = int(mal_show.id)

      if(mal_show.english is not None):
        mal_title_english = mal_show.english.lower()
        #print('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, show_title.lower()))
      else:
        #print('Comparing original: %s with %s' % (mal_title, show_title.lower()))
        pass

      if(mal_title == show_title.lower() or mal_title_english == show_title.lower()):
        # double check against MAL list using id to see if matches and update is required
        for list_item in mal_list:
          mal_list_id =int(list_item.id)
          mal_list_watched_episode_count = int(list_item.episodes)

          if(mal_list_id == mal_show_id and watched_episode_count == mal_list_watched_episode_count):
            print('[PLEX -> MAL] show was found in current MAL list using id lookup however watch count was identical so skipping update')
            update_list = False
        
        if(update_list):
          print('[PLEX -> MAL] Found match on MAL and setting state to watching with watch count: %s' % (watched_episode_count))
          anime_new = spice.get_blank(spice.get_medium('anime'))
          anime_new.episodes = watched_episode_count
          anime_new.status = spice.get_status('watching')
          spice.update(anime_new, mal_show.id, spice.get_medium('anime'), mal_credentials)
        break

    if(not found_result):
      print('[PLEX -> MAL] Failed to find %s on MAL' % (show_title))

# get MAL list
mal_list = get_mal_list()

# send watched state
send_watched_to_mal(mal_list, show_title, int(watched_episode_count))