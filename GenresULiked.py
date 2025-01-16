import spotipy
from spotipy.oauth2 import SpotifyOAuth
from phi.agent import Agent
from phi.model.groq import Groq
from dotenv import load_dotenv
import os
import io
from contextlib import redirect_stdout
import re

load_dotenv()

# Spotify API credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# Spotify Authentication
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="user-library-read playlist-modify-public playlist-modify-private"
))

# Initialize the Agent
agent = Agent(
    model=Groq(id='llama-3.3-70b-versatile'),
    instructions=["Ensure the genres are outputted as one or more of the following alone: Afrobeats, Pop, Rock, Hip-Hop/Rap, R&B/Soul, Country, Electronic/Dance (EDM), Classical, Jazz, Blues, Reggae, Latin, Folk, Metal, Punk, Indie/Alternative",
                  "Only output the genre names decided upon and NONE of the reasoning"]
)

def get_liked_songs(offset=0, limit=20):
    """
    Fetches songs from the user's liked playlist.a
    :param offset: Offset for pagination.
    :param limit: Number of songs to fetch in one batch.
    :return: List of (song_name, artist_name) tuples.
    """
    results = sp.current_user_saved_tracks(limit=limit, offset=offset)
    songs = []
    for item in results['items']:
        track = item['track']
        song_name = track['name']
        artist_name = track['artists'][0]['name']
        songs.append((song_name, artist_name))
    return songs


def get_genres_for_songs(songs):
    """
    Sends song name and artist name to the agent to retrieve their genres.
    :param songs: List of (song_name, artist_name) tuples.
    """
    for song_name, artist_name in songs:
        query = f"What is the genre of the song '{song_name}' by {artist_name}?"
        print(f"\nFetching genre for: {song_name} by {artist_name}")
        f = io.StringIO()
        with redirect_stdout(f):
            agent.print_response(query)
        response = f.getvalue().strip()  # Capture the printed output as a string

        # Remove ANSI escape sequences (screw ANSI esacape sequences)
        cleaned_string = re.sub(r'\x1b\[[0-9;]*m', '', response)

        # Regex to match the genres!!!
        regex = r"\b(Afrobeats|Pop|Rock|Hip-Hop\/Rap|R&B\/Soul|Country|Electronic\/Dance \(EDM\)|Classical|Jazz|Blues|Reggae|Latin|Folk|Metal|Punk|Indie\/Alternative)\b"

        final = re.findall(regex,cleaned_string)
        genres.append(final)


def get_or_create_genre_playlist(genre, user_id):
    """
    Checks if playlist for the genre exist. If it doesn't exist, create it.
    :param genre: Genre name
    :param user_id: Spotify user ID
    :return: Playlist ID for the specified genre
    """

    playlists = sp.current_user_playlists()
    for playlist in playlists['items']:
        if playlist['name'].lower() == genre.lower():
            return playlist['id']
        
    new_playlist = sp.user_playlist_create(user_id, name=genre, public=True)
    return new_playlist['id']

def add_songs_to_genre_playlist(songs, genres):
    """
    Add songs to their respective genre playlist
    :param songs: List of (song_name, artist_name) tuples
    :param genres: List of genre lists corresponding to the songs
    """

    user_id = sp.current_user()['id']

    for i, (song_name, artist_name) in enumerate(songs):
        track_search = sp.search(q = f"track:{song_name} artist:{artist_name}", type='track', limit=1)
        if not track_search['tracks']['items']:
            print(f"Track could not be found. {song_name} by {artist_name} couldn't be added. Skipping...")
            continue

        track_uri = track_search['tracks']['items'][0]['uri']
        song_genres = genres[i]

        for genre in song_genres:
            playlist_id = get_or_create_genre_playlist(genre, user_id)

            playlist_tracks = sp.playlist_items(playlist_id, fields="items.track.uri")
            playlist_uris = [item['track']['uri'] for item in playlist_tracks['items']]

            if track_uri in playlist_uris:
                print(f"{song_name} by {artist_name} already exists in the playlist: {genre}. Skipping!")
            else:
                sp.playlist_add_items(playlist_id, [track_uri])
                print(f"Added {song_name} by {artist_name} into the playlist : {genre}!")

# Main stuff
offset = 0
limit = 5
genres=[]


while True:
    # Fetching songs from liked playlist
    songs = get_liked_songs(offset=offset, limit=limit)
    if not songs:
        print("No more songs to process.")
        break

    # Passing songs to agent for genre classification
    get_genres_for_songs(songs)

    add_songs_to_genre_playlist(songs, genres)

    # Used to ask if they want to continue with next batch
    more = input("\nDo you want to fetch the next 5 songs? (yes/no): ").strip().lower()
    if more != 'yes':
        print(genres)
        break
    offset += limit



