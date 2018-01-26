import sys
import spice_api as spice

mal_username = sys.argv[1]
mal_password = sys.argv[2]
show_title = sys.argv[3]
watch_count = sys.argv[4]

mal_credentials = spice.init_auth(mal_username, mal_password)

def get_mal_list():
  mal_list = spice.get_list(spice.get_medium('anime'), mal_username, mal_credentials).get_mediums()
  return mal_list

def send_watched_to_mal(mal_list, show_title, watch_count):
  show_is_listed = False;
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
        else:
          print('[PLEX -> MAL] Watch count for %s on Plex was equal or higher on MAL so skipping update' % (show_title))
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
          print('[PLEX -> MAL] Found match on MAL and setting state to watching with watch count: %s' % (watch_count))
          anime_new = spice.get_blank(spice.get_medium('anime'))
          anime_new.episodes = watch_count
          anime_new.status = spice.get_status('watching')
          spice.update(anime_new, mal_show.id, spice.get_medium('anime'), mal_credentials)

          break
    else:
      print('[PLEX -> MAL] %s not in MAL list but had 0 watched so gonna skip update', show)

# get MAL list
mal_list = get_mal_list()

# send watched state
send_watched_to_mal(mal_list, show_title, int(watch_count))