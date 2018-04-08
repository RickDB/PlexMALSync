import configparser
import coloredlogs
import logging
import os
import sys
import spice_api as spice
from guessit import guessit
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer


# Logger
logger = logging.getLogger('PlexMALSync')
coloredlogs.install(fmt='%(asctime)s %(message)s', logger=logger)

# Enable this if you want to also log all messages coming from imported libraries
# coloredlogs.install(level='DEBUG')


def read_settings(file):
    # File exists
    if not os.path.isfile(file):
        logger.critical(
            '[CONFIG] Settings file file not found: {}'.format(file))
        sys.exit()
    settings = configparser.ConfigParser()
    settings.read(file)
    return settings


def plex_authenticate():
    method = plex_settings['authentication_method'].lower()
    # Direct connection
    if method == 'direct':
        base_url = plex_settings['base_url']
        token = plex_settings['token']
        plex = PlexServer(base_url, token)
    # Myplex connection
    elif method == 'myplex':
        plex_server = plex_settings['server']
        plex_user = plex_settings['myplex_user']
        plex_password = plex_settings['myplex_password']
        account = MyPlexAccount(plex_user, plex_password)
        plex = account.resource(plex_server).connect()
    else:
        logger.critical(
            '[PLEX] Failed to authenticate due to invalid settings or authentication info, exiting...')
        sys.exit()
    return plex


def mal_authenticate():
    user = mal_settings['username']
    password = mal_settings['password']
    mal = spice.init_auth(user, password)
    # Failed
    if not mal:
        logger.critical('[MAL] Failed to authenticate, exiting...')
        sys.exit()
    return mal


settings_file = 'settings.ini'

# Settings
settings = read_settings(settings_file)
plex_settings = settings['PLEX']
mal_settings = settings['MAL']

# Authenticate
plex = plex_authenticate()
mal_credentials = mal_authenticate()


def get_anime_shows():
    logger.info('[PLEX] Retrieving anime shows...')
    section = plex_settings['anime_section']
    shows = plex.library.section(section).search()
    logger.info(
        '[PLEX] Retrieving of {} anime shows completed'.format(
            len(shows)))
    return shows


def get_plex_watched_shows(shows):
    logger.info('[PLEX] Retrieving watch count for shows...')
    watched = dict()
    for show in shows:
        season_watched = 1
        episodes_watched = 0
        for episode in show.episodes():
            try:
                # If not season defined, season 1
                season = 1 if not episode.seasonNumber else episode.seasonNumber
                n_episode = episode.index
                if episode.isWatched and n_episode:
                    if (n_episode > episodes_watched and season ==
                            season_watched) or (season > season_watched):
                        season_watched = season
                        episodes_watched = n_episode
                    else:
                        episodes_watched = 0
            except BaseException:
                logger.error('Error during lookup_result processing')
                pass
        if episodes_watched > 0:
            watched[show] = (episodes_watched, season_watched)
            logger.info(
                'Watched {} episodes of show: {}'.format(
                    episodes_watched, show.title))
    logger.info('[PLEX] Retrieving watch count for shows finished')
    return watched


def get_mal_list():
    logger.info('[MAL] Retrieving list...')
    user = mal_settings['username']
    mal_list = spice.get_list(
        spice.get_medium('anime'),
        user,
        mal_credentials).get_mediums()
    items = len(mal_list) if mal_list else 0
    logger.info('[MAL] Found {} shows on list'.format(items))
    return mal_list


def match_seasons_on_mal_list(mal_list):
    logger.info('[MAL] Matching seasons inside MAL list...')
    mal_list_seasoned = list()
    # type 1 indicates TV.

    def is_tv_show(show): return show.raw_data.contents[3].contents[0] == '1'

    def show_date(show): return show.raw_data.contents[7].contents[0] \
        if show.raw_data.contents[7].contents[0] != '0000-00-00' else '9999-99-99'
    # Filter tv shows
    tv_shows = list(filter(is_tv_show, mal_list))

    for show in tv_shows:
        matched_list = list()
        # Later seasons have longer names, e.g. "original_name 2/Final/Second Stage/!!"
        # Only the original season should have a list properly populated
        for matched_shows in tv_shows:
            if show.title.lower() in matched_shows.title.lower():
                match = (show, show_date(show))
                matched_list.append(match)
        matched_list.sort(key=lambda x: x[1])

        try:
            original_name = [
                x[0].title for x in matched_list if x[1] != '9999-99-99']
            # Can't do miracles if it's all empty
            original_name_treated = original_name[0] if original_name else matched_list[0][0].title
        except BaseException:
            logger.error(
                'Error during matching season retrieval for show: {}'.format(
                    show.title))
            original_name_treated = show.title

        for i, element in enumerate(matched_list):
            mal_list_seasoned.append(
                (element[0], i + 1, original_name_treated))
    logger.info('[MAL] Matching seasons inside MAL list finished')
    return mal_list_seasoned


def update_mal_list_with_seasons(mal_list_seasoned, plex_shows):
    """
    update_mal_list_with_seasons: complete list with all seasons for watched shows and later compare by season.
    these are seasons defined by MAL. 1 season MIGHT mean a continuous run of many AniDB/TVDB seasons, per MAL standards.
    plex_watched_shows only uses the original name.
    """
    logger.info('[MAL] Retrieving updated list for season matching...')
    mal_list_seasoned_updated = [
        (x[0], x[1], x[2], 'on_mal_list') for x in mal_list_seasoned]
    for show, (episodes, season) in plex_shows.items():
        matches_in_mal_list_seasoned = [x for x in mal_list_seasoned
                                        if x[2].lower() == show.title.lower()
                                        and x[1] == season]
        if bool(matches_in_mal_list_seasoned) or season == 1:
            continue
        mal_shows = spice.search(
            show, spice.get_medium('anime'), mal_credentials)
        matched_list = []
        for mal_show in mal_shows:
            try:
                if mal_show.anime_type == 'TV':
                    match = (
                        mal_show,
                        mal_show.dates[1] if mal_show.dates[1] != '0000-00-00' else '9999-99-99')
                    matched_list.append(match)
            except BaseException:
                logger.error(
                    'Error during season date lookup for show: {}'.format(mal_show))
        matched_list.sort(key=lambda x: x[1])

        try:
            original_name = [
                x[0].title for x in matched_list if x[1] != '9999-99-99']

            # can't do miracles if it's all empty
            original_name_treated = original_name[0] if original_name else matched_list[0][0].title
        except BaseException:
            logger.error(
                'Error during original name treatment for show: {}'.format(
                    show.title))
            original_name_treated = show.title

        for i, element in enumerate(matched_list):
            mal_list_seasoned_updated.append(
                (element[0], i + 1, original_name_treated, 'not_on_mal_list'))
    logger.info('[MAL] Retrieving updated list for season matching finished')
    return mal_list_seasoned_updated


# update an existing match
def update_mal_entry(
        list_item,
        plex_title,
        plex_watched_episode_count,
        force_update):
    mal_watched_episode_count = int(list_item.episodes)
    mal_show_id = int(list_item.id)
    print(mal_watched_episode_count, mal_show_id)
    if mal_show_id > 0:
        if mal_watched_episode_count < plex_watched_episode_count or force_update:
            anime_new = spice.get_blank(spice.get_medium('anime'))
            anime_new.episodes = plex_watched_episode_count
            new_status = 'watching'

            # If full watched set status to completed, needs additional lookup as total episodes
            # are not exposed in list (mal or spice limitation)
            lookup_show = spice.search_id(
                mal_show_id, spice.get_medium('anime'), mal_credentials)
            if lookup_show:
                if lookup_show.episodes:
                    mal_total_episodes = int(lookup_show.episodes)

                    if plex_watched_episode_count >= mal_total_episodes:
                        new_status = 'completed'

                anime_new.status = spice.get_status(new_status)

            logger.warning(
                '[PLEX -> MAL] Watch count for {} on Plex is {} and MAL is {}, updating MAL watch count to {} and status to {}' .format(
                    plex_title,
                    plex_watched_episode_count,
                    mal_watched_episode_count,
                    plex_watched_episode_count,
                    new_status))
            spice.update(
                anime_new,
                mal_show_id,
                spice.get_medium('anime'),
                mal_credentials)
        else:
            logger.warning(
                '[PLEX -> MAL] Watch count for {} on Plex was equal or higher on MAL so skipping update' .format(plex_title))
        pass


def add_mal_entry(list_item, on_mal_list):
    if on_mal_list == 'not_on_mal_list':
        logger.warning('[PLEX -> MAL] No MAL entry found for matching season of {}, adding to MAL with status Watching ]'
                       .format(list_item.title))

        anime_new = spice.get_blank(spice.get_medium('anime'))
        anime_new.episodes = 0
        spice.add(anime_new,
                  int(list_item.id),
                  spice.get_medium('anime'),
                  mal_credentials)


def send_watched_to_mal(plex_watched_shows, mal_list, mal_list_seasoned):
    for show, value in plex_watched_shows.items():
        plex_title = show.title
        plex_watched_episode_count, plex_watched_episode_season = value
        show_in_mal_list = False
        force_update = False
        #logger.debug('%s => watch count = %s' % (plex_title, watched_episode_count))

        if plex_watched_episode_count <= 0:
            continue

        # All shows with season > 1 were previously searched and are part of
        # the mal_list_seasoned object
        if plex_watched_episode_season > 1:
            force_update = True
            for anime, season, original_name, on_mal_list in mal_list_seasoned:
                if original_name.lower() == plex_title.lower():
                    try:
                        correct_item = [value[0] for index, value in enumerate(mal_list_seasoned)
                                        if value[1] == plex_watched_episode_season and value[2] == original_name][0]
                    except BaseException:
                        # Search failed to properly match seasons, e.g. Card Captor Sakura Clear Card is s4 on TVDB and s2 here
                        # assume most recent available season
                        # TODO: search by ID of the correct season
                        if force_update:
                            correct_item = spice.search_id(
                                int(mal_list_seasoned[-1][0].id), spice.get_medium('anime'), mal_credentials)
                            on_mal_list = 'not_on_mal_list'
                        else:
                            break
                    # Trying to add before doens't really break anything and
                    # works for new series, since mal_list_seasoned includes
                    # things you haven't watched yet
                    add_mal_entry(correct_item, on_mal_list)
                    update_mal_entry(
                        correct_item,
                        plex_title,
                        plex_watched_episode_count,
                        force_update)
                    break
            continue

        # check if show is already on MAL list
        for list_item in mal_list:
            #logger.debug('Comparing %s with %s' % (list_item.title, plex_title))
            mal_title = list_item.title
            mal_title_english = ""
            if list_item.english is not None:
                mal_title_english = list_item.english
                #logger.debug('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, plex_title))
            else:
                #logger.debug('Comparing original: %s with %s' % (mal_title, plex_title))
                pass

            if mal_title.lower() == plex_title.lower(
            ) or mal_title_english.lower() == plex_title.lower():
                show_status = spice.get_status(list_item.status)
                logger.debug(
                    '{} [{}] was already in list => status = {} | watch count = {}' .format(
                        plex_title, list_item.id, show_status, list_item.episodes))
                show_in_mal_list = True
                update_mal_entry(
                    list_item,
                    plex_title,
                    plex_watched_episode_count,
                    force_update)

        # If not listed in list lookup on MAL
        if not show_in_mal_list:
            found_result = False
            update_list = True
            on_mal_list = False
            logger.info('[PLEX -> MAL] {} not in MAL list, searching for show on MAL'
                        .format(plex_title))

            potential_titles = [
                plex_title.lower(),
                guessit(plex_title)['title'].lower()]
            for title in potential_titles:
                mal_shows = spice.search(
                    title, spice.get_medium('anime'), mal_credentials)
                if len(mal_shows) >= 1:
                    break

            for mal_show in mal_shows:
                mal_title = mal_show.title.lower()
                mal_title_english = ''
                mal_show_id = int(mal_show.id)
                mal_total_episodes = int(mal_show.episodes)

                if mal_show.english:
                    mal_title_english = mal_show.english.lower()
                    #logger.debug('Comparing original: %s | english: %s with %s' % (mal_title, mal_title_english, plex_title.lower()))
                else:
                    #logger.debug('Comparing original: %s with %s' % (mal_title, plex_title.lower()))
                    pass

                if mal_title in potential_titles or mal_title_english in potential_titles:
                    found_result = True

                    # double check against MAL list using id to see if matches
                    # and update is required
                    for list_item in mal_list:
                        mal_list_id = int(list_item.id)
                        mal_list_watched_episode_count = int(
                            list_item.episodes)

                        if mal_list_id == mal_show_id:
                            on_mal_list = True
                            if plex_watched_episode_count == mal_list_watched_episode_count:
                                logger.warning(
                                    '[PLEX -> MAL] show was found in current MAL list using id lookup however watch count was identical so skipping update')
                                update_list = False
                            break

                    if update_list:
                        logger.warning('[PLEX -> MAL] Found match on MAL and setting state to watching with watch count: {}'
                                       .format(plex_watched_episode_count))
                        anime_new = spice.get_blank(spice.get_medium('anime'))
                        anime_new.episodes = plex_watched_episode_count

                        if plex_watched_episode_count >= mal_total_episodes:
                            anime_new.status = spice.get_status('completed')
                            if on_mal_list:
                                spice.update(
                                    anime_new,
                                    mal_show.id,
                                    spice.get_medium('anime'),
                                    mal_credentials)
                            else:
                                spice.add(
                                    anime_new,
                                    mal_show.id,
                                    spice.get_medium('anime'),
                                    mal_credentials)
                        else:
                            anime_new.status = spice.get_status('watching')
                            if on_mal_list:
                                spice.update(
                                    anime_new,
                                    mal_show.id,
                                    spice.get_medium('anime'),
                                    mal_credentials)
                            else:
                                spice.add(
                                    anime_new,
                                    mal_show.id,
                                    spice.get_medium('anime'),
                                    mal_credentials)
                    break

            if not found_result:
                logger.error(
                    '[PLEX -> MAL] Failed to find {} on MAL'.format(plex_title))


def start():
    # Watched shows
    shows = get_anime_shows()
    watched_shows = get_plex_watched_shows(shows)

    mal_list = get_mal_list()

    # Add seasons to list
    mal_list_seasoned = match_seasons_on_mal_list(mal_list)
    updated_mal_list = update_mal_list_with_seasons(
        mal_list_seasoned, watched_shows)

    send_watched_to_mal(watched_shows, mal_list, updated_mal_list)
    logger.info('Plex to MAL sync finished')


if __name__ == '__main__':
    start()
