import certifi
import requests
from time import sleep

VERSION = '1.8'
API_URL = 'https://api.tadata.me/omdb/v1/?{}={}'
HTTP_HEADERS = {
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12.4) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.1 Safari/603.1.30",
  "Referer": "http://www.imdb.com/"
}

def Start():
  pass

def ValidatePrefs():
  pass

####################################################################################################
class OmdbApi(Agent.Movies):

  name = 'Open Movie Database'
  languages = [Locale.Language.English]
  primary_provider = False
  contributes_to = [
    'com.plexapp.agents.imdb',
    'com.plexapp.agents.themoviedb'
  ]

  def search(self, results, media, lang):

    if media.primary_agent == 'com.plexapp.agents.imdb':

      imdb_id = media.primary_metadata.id

    elif media.primary_agent == 'com.plexapp.agents.themoviedb':

      # Get the IMDb id from the Movie Database Agent
      imdb_id = Core.messaging.call_external_function(
        'com.plexapp.agents.themoviedb',
        'MessageKit:GetImdbId',
        kwargs = dict(
          tmdb_id = media.primary_metadata.id
        )
      )

      if not imdb_id:
        Log("*** Could not find IMDb id for movie with The Movie Database id: {} ***".format(media.primary_metadata.id))
        return None

    results.Append(MetadataSearchResult(
      id = imdb_id,
      score = 100
    ))

  def update(self, metadata, media, lang):

    GetMetadata(metadata, media, API_URL.format('imdb_id', metadata.id), type='movie')

####################################################################################################
class OmdbApi(Agent.TV_Shows):

  name = 'Open Movie Database'
  languages = [Locale.Language.English]
  primary_provider = False
  contributes_to = [
    'com.plexapp.agents.thetvdb'
  ]

  def search(self, results, media, lang):

    results.Append(MetadataSearchResult(
      id = media.primary_metadata.id,
      score = 100
    ))

  def update(self, metadata, media, lang):

    GetMetadata(metadata, media, API_URL.format('tvdb_id', metadata.id), type='tv')

    for season in media.seasons:
      for episode in media.seasons[season].episodes:
        GetMetadata(metadata.seasons[season].episodes[episode], None, API_URL.format('tvdb_id', '{}&season={}&episode={}'.format(metadata.id, season, episode)), type='episode')

####################################################################################################
def GetMetadata(metadata, media, url, type):

  sleep(1.5) # Prevent 429
  r = requests.get(url, headers=HTTP_HEADERS, verify=certifi.where())

  try:
    omdb = r.json()
  except ValueError:
    Log("*** Did not receive valid JSON data from URL: {} (HTTP status code: {}) ***".format(url, r.status_code))
    return None

  if r.status_code != 200:
    if type in ['movie', 'tv']:
      requests.put('https://api.tadata.me/omdb/v1/feedback', data='{{"id": "{}", "title": "{}", "http_code": "{}", "error": "{}"}}'.format(metadata.id, media.title, r.status_code, omdb['error']), verify=certifi.where())

    Log("*** Did not receive data from URL: {} (HTTP status code: {}) ***".format(url, r.status_code))
    Log("*** Reason: {} ***".format(omdb['error']))

    return None

  # Title
  if Prefs['use_title'] and omdb['title']:
    metadata.title = omdb['title']
  else:
    metadata.title = None

  # Plot
  if Prefs['use_plot'] and omdb['plot']:
    metadata.summary = omdb['plot']
  else:
    metadata.summary = None

  # Release date
  if Prefs['use_release_date'] and omdb['released']:
    metadata.originally_available_at = Datetime.ParseDate(omdb['released']).date()
  else:
    metadata.originally_available_at = None

  # Runtime
  if Prefs['use_runtime'] and omdb['runtime']:
     metadata.duration = omdb['runtime'] * 1000
  else:
    metadata.duration = None

  # Ratings
  rating_imdb = None
  rating_rt = None
  rating_metacritic = None

  if omdb['ratings'] and 'imdb' in omdb['ratings']:
    rating_imdb = float(omdb['ratings']['imdb'])

  if omdb['ratings'] and 'rt' in omdb['ratings']:
    rating_rt = omdb['ratings']['rt']

  if omdb['ratings'] and 'metacritic' in omdb['ratings']:
    rating_metacritic = omdb['ratings']['metacritic']

  if ((type == 'movie' and Prefs['rating_movies'] == 'IMDb') or (type in ['tv', 'episode'] and Prefs['rating_tv'] == 'IMDb')) and rating_imdb:
    metadata.rating = rating_imdb

    try: metadata.rating_image = 'imdb://image.rating'
    except: pass

  elif ((type == 'movie' and Prefs['rating_movies'] == 'Rotten Tomatoes') or (type == 'tv' and Prefs['rating_tv'] == 'Rotten Tomatoes')) and rating_rt:
    metadata.rating = float(rating_rt)/10

    try:
      if rating_rt >= 60:
        metadata.rating_image = 'rottentomatoes://image.rating.ripe'
      else:
        metadata.rating_image = 'rottentomatoes://image.rating.rotten'
    except:
      pass

  elif type == 'movie' and Prefs['rating_movies'] == 'Metacritic' and rating_metacritic:
    metadata.rating = float(rating_metacritic)/10

    try: metadata.rating_image = None
    except: pass
  else:
    metadata.rating = None

    try: metadata.rating_image = None
    except: pass

  # Add rating(s) to summary
  if metadata.summary:
    summary = [metadata.summary]
  else:
    summary = []

  if Prefs['add_rating_metacritic'] and rating_metacritic:
    summary.append('Metacritic: {}'.format(rating_metacritic))

  if Prefs['add_rating_rt'] and rating_rt:
    summary.append('Rotten Tomatoes: {}%'.format(rating_rt))

  if Prefs['add_rating_imdb'] and rating_imdb:
    summary.append('IMDb: {}'.format(rating_imdb))

  if len(summary) > 0:
    summary.reverse()
    metadata.summary = '  ★  '.join(summary)

  # Add movie or TV specific metadata
  if type in ['movie', 'tv']:

    # Content rating
    if Prefs['use_content_rating'] and omdb['rated']:
      metadata.content_rating = omdb['rated']
    else:
      metadata.content_rating = None

    # Genres
    metadata.genres.clear()

    if Prefs['use_genres'] and omdb['genres']:
      for genre in omdb['genres']:
        metadata.genres.add(genre.strip())

    # Production company
    if Prefs['use_production'] and omdb['studio']:
      metadata.studio = omdb['studio']
    else:
      metadata.studio = None

    # Actors
    metadata.roles.clear()

    if Prefs['use_actors'] and omdb['actors']:

      for actor in omdb['actors']:
        role = metadata.roles.new()
        try:
          role.name = actor
        except:
          try:
            role.actor = actor
          except:
            pass

    # Poster
    valid_names = list()

    if Prefs['use_poster'] and omdb['poster']:

      fullsize_url = '{}.jpg'.format(omdb['poster'].rsplit('_', 1)[0])
      thumb_url = '{}_SX300.jpg'.format(omdb['poster'].rsplit('_', 1)[0])

      if fullsize_url not in metadata.posters:

        r = requests.get(thumb_url, headers=HTTP_HEADERS, verify=certifi.where())

        if r.status_code == 200:

          valid_names.append(fullsize_url)
          metadata.posters[fullsize_url] = Proxy.Preview(r.content)

    metadata.posters.validate_keys(valid_names)

  # Add movie or episode specific metadata
  if type in ['movie', 'episode']:

    # Directors
    metadata.directors.clear()

    if Prefs['use_directors'] and omdb['directors']:

      for director in omdb['directors']:
        try:
          meta_director = metadata.directors.new()
          meta_director.name = director
        except:
          try:
            metadata.directors.add(director)
          except:
            pass

    # Writers
    metadata.writers.clear()

    if Prefs['use_writers'] and omdb['writers']:

      for writer in omdb['writers']:
        try:
          meta_writer = metadata.writers.new()
          meta_writer.name = writer
        except:
          try:
            metadata.writers.add(writer)
          except:
            pass

  # Add movie specific metadata
  if type == 'movie':

    # Year
    if Prefs['use_year'] and omdb['year']:
      metadata.year = omdb['year']
    else:
      metadata.year = None

  # Add episode specific metadata
  if type == 'episode':

    # Thumb
    valid_names = list()

    if Prefs['use_thumb'] and omdb['poster']:

      fullsize_url = '{}.jpg'.format(omdb['poster'].rsplit('_', 1)[0])
      thumb_url = '{}_SX300.jpg'.format(omdb['poster'].rsplit('_', 1)[0])

      if fullsize_url not in metadata.thumbs:

        r = requests.get(thumb_url, headers=HTTP_HEADERS, verify=certifi.where())

        if r.status_code == 200:

          valid_names.append(fullsize_url)
          metadata.thumbs[fullsize_url] = Proxy.Preview(r.content)

    metadata.thumbs.validate_keys(valid_names)
