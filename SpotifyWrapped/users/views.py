import urllib.parse, base64, json, os, requests, random

from .models import SpotifyWrapped

from copy import error
from collections import Counter
from django.shortcuts import redirect, render, get_object_or_404
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseRedirect
from django.utils.timezone import now
from rest_framework.decorators import api_view
from requests import post
import logging
logger = logging.getLogger(__name__)


def home(request):
    """
    Handles the user's entry point into the application by checking the validity of their Spotify access token.

    If the user has a valid access token, this function verifies it by making a request to the Spotify Web API.
    If the token is valid, the user is redirected to the welcome page. If the token is invalid or missing,
    the function clears the session's access token and renders the login page.

    Args:
        request (HttpRequest): The HTTP request object containing session and user data.

    Returns:
        HttpResponse:
            - A redirect to the welcome page if the token is valid.
            - A rendered login page if the token is missing or invalid.
    """

    access_token = request.session.get('access_token')
    if access_token:
        try:
            # Use Spotify Web API to verify token
            url = "https://api.spotify.com/v1/me"
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                # Token is valid, redirect to welcome page
                return redirect('users:welcome')
            else:
                # Token invalid, clear it
                del request.session['access_token']
        except Exception as e:
            print(f"Error verifying token: {e}")
            # Token invalid or error occurred, clear it
            del request.session['access_token']

    # If no valid token, render the login page
    return render(request, 'login.html')

def signout(request):
    """
    Logs the user out of the application by clearing session data and removing cached Spotify tokens.

    This function ensures that the user's session is completely cleared, including removing any cached
    Spotify authentication tokens stored for the session. After clearing, the user is redirected to the
    home page or login page.

    Args:
        request (HttpRequest): The HTTP request object containing session and user data.

    Returns:
        HttpResponse: A redirect to the home or login page.
    """

    # Remove the spotify_token from the session to log the user out
    cache_path = f".spotify_caches/{request.session.session_key}"
    if os.path.exists(cache_path):
        os.remove(cache_path)
    request.session.flush()
    # Redirect to the login page or another page as needed
    return redirect('/')

def delete_wrap(request, wrap_id):
    """
    Deletes a user's wrap if they own it.

    Args:
        request (HttpRequest): The HTTP request object.
        wrap_id (int): The ID of the wrap to delete.

    Returns:
        HttpResponse: Redirects to the profile page after deletion.
    """
    def get_spotify_user_id(access_token):
        """Fetch the Spotify user ID using the access token."""
        headers = {'Authorization': f'Bearer {access_token}'}
        user_profile_url = "https://api.spotify.com/v1/me"
        response = requests.get(user_profile_url, headers=headers)
        if response.status_code != 200:
            raise ValueError("Failed to fetch user profile")
        return response.json().get('id')

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('users:spotify_login')

    try:
        # Get Spotify user ID
        spotify_user_id = get_spotify_user_id(access_token)

        # Get the wrap and verify ownership
        wrap = get_object_or_404(SpotifyWrapped, id=wrap_id)
        if wrap.spotify_user_id != spotify_user_id:
            return HttpResponseForbidden("You don't have permission to delete this wrap")

        # Delete the wrap
        wrap.delete()
        logger.info(f"Wrap {wrap_id} successfully deleted for user {spotify_user_id}")

    except ValueError as ve:
        logger.error(f"Error fetching user profile: {ve}")
    except Exception as e:
        logger.error(f"Error deleting wrap {wrap_id}: {e}")

    return redirect('users:profile')

def spotify_login(request):
    """
    Redirects user to Spotify's authorization page to log in.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Redirects to Spotify's authorization URL with the necessary scopes.
    """

    auth_url = "https://accounts.spotify.com/authorize"

    auth_params = {
        'response_type': 'code',
        'client_id': settings.SPOTIFY_CLIENT_ID,
        'redirect_uri': settings.SPOTIFY_REDIRECT_URI,
        'scope': settings.SPOTIFY_SCOPE,
        'show_dialog': 'true',
    }

    auth_url_with_params = f"{auth_url}?{urllib.parse.urlencode(auth_params)}"
    return redirect(auth_url_with_params)

def spotify_callback(request):
    """
    Handles the Spotify authentication callback, exchanges the authorization code for an access token,
    and stores the token in the session. Redirects to the welcome page upon successful authentication.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Redirects to the appropriate page based on success or failure.
    """

    # Check for error parameter in the callback
    if 'error' in request.GET:
        error_reason = request.GET.get('error')
        print(f"Authorization error: {error_reason}")
        return redirect('/')  # Redirect to login if authorization fails

    # Get the authorization code from the callback
    code = request.GET.get('code')
    if not code:
        print("Authorization code missing in callback")
        return redirect('/')

    # Exchange the authorization code for an access token
    token_url = "https://accounts.spotify.com/api/token"
    redirect_uri = settings.SPOTIFY_REDIRECT_URI
    client_id = settings.SPOTIFY_CLIENT_ID
    client_secret = settings.SPOTIFY_CLIENT_SECRET

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret,
    }

    try:
        token_response = requests.post(token_url, data=data)
        if token_response.status_code != 200:
            print(f"Token exchange failed: {token_response.json()}")
            return redirect('users:home')  # Redirect to home if token exchange fails

        token_info = token_response.json()
        access_token = token_info.get('access_token')

        if not access_token:
            print("Access token missing in token response")
            return redirect('users:home')

        # Store the access token in the session
        request.session['access_token'] = access_token

    except Exception as e:
        print(f"Error during token exchange: {str(e)}")
        return redirect('users:home')  # Redirect to home if error occurs

    # Redirect to the welcome page after successful authentication
    return redirect('users:welcome')

@api_view(['GET'])
def top_artists(request):
    """
    Retrieves and displays the user's top artists from Spotify using the Web API.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders the top artists page with the list of top artists.
    """

    access_token = request.session.get('access_token')

    if not access_token:
        print("Access token is missing. Redirecting to login.")
        return redirect('users:spotify_login')  # Redirect to the login page

    try:
        # Spotify API endpoint for top artists
        url = "https://api.spotify.com/v1/me/top/artists"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        params = {
            'limit': 20,  # Number of top artists to retrieve
            'time_range': 'long_term',  # "long_term" for lifetime, "medium_term" for 6 months, "short_term" for 4 weeks
        }

        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error fetching top artists: {response.json()}")
            return redirect('users:spotify_login')  # Redirect to the login page if the request fails

        # Parse the API response
        user_top_artists = response.json().get('items', [])

        # Structure the artists' data
        artists = [
            {
                "name": artist.get("name"),
                "id": artist.get("id"),
                "image_url": artist.get("images", [{}])[0].get("url"),
            }
            for artist in user_top_artists
        ]

        return render(request, 'top_artists.html', {'artists': artists})

    except Exception as e:
        # Log the error in the terminal
        print(f"Unexpected error in top_artists view: {str(e)}")
        return redirect('users:spotify_login')  # Redirect to the login page if an exception occurs

# Renders the welcome page
def welcome(request):
    """
    Displays the welcome page after successful Spotify authentication.

    Retrieves the user's Spotify profile data using the access token stored
    in the session and renders the home page with the user's details.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders the home page with user profile details,
        or redirects to the login page if an error occurs.
    """

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('users:spotify_login')

    try:
        # Define the endpoint for the user's profile
        user_profile_url = "https://api.spotify.com/v1/me"

        # Make the API request
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(user_profile_url, headers=headers)

        # Handle API errors
        if response.status_code != 200:
            print(f"Error fetching user profile: {response.status_code}, {response.text}")
            return redirect('users:spotify_login')

        user_profile = response.json()
        user_name = user_profile.get('display_name', 'Spotify User')

        # Pass the data to the context for rendering the home page
        context = {
            'user_name': user_name,
            'profile_data': user_profile,
            'is_authenticated': True
        }
        return render(request, 'home.html', context)

    except Exception as e:
        print(f"Error in welcome view: {str(e)}")
        return redirect('users:spotify_login')

@api_view(['GET'])
def top_tracks(request):
    """
    Retrieves and displays the user's top tracks from Spotify.

    Fetches the user's top tracks using the Spotify API and returns
    the rendered template with the track details.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders a template displaying the user's top tracks,
        or redirects to the login page if an error occurs.
    """

    if request.method == 'GET':
        access_token = request.session.get('access_token')
        language = request.session.get('language', 'en')

        if not access_token:
            print("No access token found. Redirecting to login.")
            return redirect('users:spotify_login')

        # Updated market mapping with proper Bengali market code
        markets = {
            'en': 'US',
            'es': 'ES',
            'bn': 'BD',  # Changed to Bangladesh for Bengali
            'zh': 'CN'
        }
        market = markets.get(language, 'US')

        # API endpoint for top tracks
        top_tracks_url = "https://api.spotify.com/v1/me/top/tracks"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            # Fetch top tracks
            response = requests.get(
                top_tracks_url,
                headers=headers,
                params={"limit": 20, "offset": 0, "time_range": "long_term"}
            )

            if response.status_code != 200:
                print(f"Error fetching top tracks: {response.status_code}, {response.text}")
                return redirect('users:spotify_login')

            top_tracks_data = response.json().get("items", [])

            tracks = []
            for track in top_tracks_data:
                track_info = {
                    "name": track["name"],
                    "id": track["id"],
                    "artist": track["artists"][0]["name"],
                    "artists": ", ".join([artist["name"] for artist in track["artists"]]),
                    "album": track["album"]["name"],
                    "image_url": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                    "preview_url": track["preview_url"],
                    "spotify_url": track["external_urls"]["spotify"]
                }
                tracks.append(track_info)

            return render(request, 'top_tracks.html', {
                'tracks': tracks,
                'language': language
            })

        except Exception as e:
            print(f"Error in top_tracks view: {str(e)}")
            return redirect('users:spotify_login')

    return redirect('users:spotify_login')

# Update your toggle_language view
@require_http_methods(["POST"])
def update_language(request):
    """
    Updates the user's preferred language in the session.

    The language preference is sent in the request body as JSON. The function updates
    the session with the selected language and returns a success response. If an error occurs,
    it returns a JSON error response with the appropriate status code.

    Args:
        request (HttpRequest): The HTTP request object containing the language data.

    Returns:
        JsonResponse: A JSON response indicating success or error.
    """
    try:
        data = json.loads(request.body)
        language = data.get('language', 'en')
        request.session['language'] = language
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@api_view(['GET'])
def top_genres(request):
    """
    Retrieves and displays the user's top genres based on their top artists.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders the top genres page with the most common genres.
    """

    if request.method == 'GET':
        access_token = request.session.get('access_token')
        if not access_token:
            print("Access token missing. Redirecting to login.")
            return redirect('users:spotify_login')

        # Spotify API endpoint for user's top artists
        top_artists_url = "https://api.spotify.com/v1/me/top/artists"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            # Fetch top artists
            response = requests.get(
                top_artists_url,
                headers=headers,
                params={"limit": 20, "offset": 0, "time_range": "long_term"}
            )

            if response.status_code != 200:
                print(f"Error fetching top artists: {response.status_code}, {response.text}")
                return redirect('users:spotify_login')

            top_artists_data = response.json().get("items", [])

            # Collect genres from top artists
            genres = []
            for artist in top_artists_data:
                genres.extend(artist.get('genres', []))

            # Count occurrences of each genre
            genre_count = Counter(genres)
            most_common_genres = genre_count.most_common(5)

            return render(request, 'top_genres.html', {'genres': most_common_genres})

        except Exception as e:
            print(f"Error in top_genres view: {str(e)}")
            return redirect('users:spotify_login')

    return redirect('users:spotify_login')

def wrapped_slides(request):
    """
    Displays the user's Spotify Wrapped slides, including top artists, top tracks, matching genre artists,
    and a grid of top track images.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered wrapped slides page or redirect on error.
    """

    access_token = request.session.get('access_token')
    language = request.session.get('language', 'en')

    if not access_token:
        return redirect('spotify_login')

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        # Get subscription type
        subscription_type = "https://api.spotify.com/v1/me/product"

        # Get top artists
        top_artist_url = "https://api.spotify.com/v1/me/top/artists"
        top_artist_response = requests.get(
            top_artist_url, headers=headers, params={"limit": 5, "time_range": "long_term"}
        )

        if top_artist_response.status_code != 200:
            print(f"Error fetching top artists: {top_artist_response.status_code}, {top_artist_response.text}")
            return redirect('spotify_login')

        top_artists = top_artist_response.json().get('items', [])

        # Get top tracks
        top_track_url = "https://api.spotify.com/v1/me/top/tracks"
        top_track_response = requests.get(
            top_track_url, headers=headers, params={"limit": 5, "time_range": "long_term"}
        )

        if top_track_response.status_code != 200:
            print(f"Error fetching top tracks: {top_track_response.status_code}, {top_track_response.text}")
            return redirect('spotify_login')

        top_tracks = top_track_response.json().get('items', [])

        # Determine top genre
        top_genre = top_artists[0].get("genres", ["Unknown"])[0] if top_artists else "Unknown"

        # Find all artists whose genre matches the top genre
        matching_artists = []
        for artist in top_artists:
            artist_genres = artist.get("genres", [])
            if top_genre in artist_genres:
                matching_artists.append({
                    "name": artist["name"],
                    "image_url": artist["images"][0]["url"] if artist.get("images") else None
                })

        # Prepare top 4 track images for the grid
        top_tracks_images = []
        for track in top_tracks[:4]:
            album_images = track.get("album", {}).get("images", [])
            if album_images:
                top_tracks_images.append({
                    "name": track["name"],
                    "image_url": album_images[0]["url"],
                })

        # Get top 20 tracks for "Guess the Song" game
        guess_track_url = "https://api.spotify.com/v1/me/top/tracks"
        guess_track_response = requests.get(
            guess_track_url, headers=headers, params={"limit": 3, "time_range": "long_term"}
        )

        if guess_track_response.status_code != 200:
            print(
                f"Error fetching tracks for 'Guess the Song': {guess_track_response.status_code}, {guess_track_response.text}")
            return redirect('spotify_login')

        top_3_tracks = guess_track_response.json().get('items', [])

        # Select a random track for the game
        random_track = random.choice(top_3_tracks) if top_3_tracks else None
        track_snippet = {
            "name": random_track["name"] if random_track else None,
            "artist": random_track["artists"][0]["name"] if random_track else None,
            "preview_url": random_track.get("preview_url") if random_track else None,
            "uri": random_track["uri"],
            "duration" : random_track["duration_ms"],
            "choices": [random_track["name"]] if random_track else []
        }

        user_data = {
            "top_artist": {
                "name": top_artists[0]["name"],
                "image_url": top_artists[0]["images"][0]["url"] if top_artists[0]["images"] else None,
                "genres": top_artists[0]["genres"],
            } if top_artists else None,
            "top_track": {
                "name": top_tracks[0]["name"],
                "uri": top_tracks[0]["uri"],
                "image_url": top_tracks[0]["album"]["images"][0]["url"] if top_tracks[0]["album"]["images"] else None,
            } if top_tracks else None,
            "top_genre": top_genre,
            "top_artists": top_artists,
            "top_tracks": top_tracks,
            "matching_artists": matching_artists,
            "top_tracks_images": top_tracks_images,
            "guess_song_game": track_snippet,
            "top_3_tracks" : top_3_tracks,
            "top_3_artists" : top_artists[:3],
            "subscription_type" : subscription_type,
        }

        context = {
            'user_data': user_data,
            'language': language,
            'request': request  # Add request to context
        }

        return render(request, 'wrapped_slides.html', context)

    except Exception as e:
        print(f"Error in wrapped_slides: {str(e)}")
        return redirect('users:spotify_login')

def view_public_wraps(request):
    """
    Displays all public Spotify Wrapped posts from users.
    Allows authenticated and non-authenticated users to view public wraps.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered public wraps page.
    """

    # Get all public wraps ordered by most recent
    public_wraps = SpotifyWrapped.objects.filter(public=True).order_by('-created_at')

    # Get current user's info if they're logged in
    current_user = None
    access_token = request.session.get('access_token')

    if access_token:
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            user_profile_response = requests.get("https://api.spotify.com/v1/me", headers=headers)

            if user_profile_response.status_code == 200:
                current_user = user_profile_response.json()
            else:
                print(f"Error fetching current user: {user_profile_response.status_code}, {user_profile_response.text}")
        except Exception as e:
            print(f"Error fetching current user details: {str(e)}")

    context = {
        'public_wraps': public_wraps,
        'current_user': current_user,
        'is_authenticated': bool(access_token)
    }

    return render(request, 'publicwraps.html', context)

def create_top_tracks_playlist(request):
    """
    Creates a playlist with the user's top 50 tracks and redirects to the playlist.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Redirect to the playlist URL or None on error.
    """

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('users:spotify_login')

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    try:
        # Step 1: Get user's top 50 tracks
        top_tracks_response = requests.get(
            'https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=long_term',
            headers=headers
        )
        if top_tracks_response.status_code != 200:
            print(f"Error fetching top tracks: {top_tracks_response.status_code}, {top_tracks_response.text}")
            return redirect('users:spotify_login')

        top_tracks_data = top_tracks_response.json()
        track_uris = [track['uri'] for track in top_tracks_data.get('items', [])]

        # Step 2: Get user's Spotify ID
        user_profile_response = requests.get(
            'https://api.spotify.com/v1/me',
            headers=headers
        )
        if user_profile_response.status_code != 200:
            print(f"Error fetching user profile: {user_profile_response.status_code}, {user_profile_response.text}")
            return redirect('users:spotify_login')

        user_id = user_profile_response.json()['id']

        # Step 3: Create a playlist
        playlist_data = {
            "name": "Your Top 50 Tracks of the Year",
            "description": "A playlist of your most-listened-to tracks from the past year, created by your Spotify Wrapped app.",
            "public": True
        }

        playlist_response = requests.post(
            f'https://api.spotify.com/v1/users/{user_id}/playlists',
            headers=headers,
            json=playlist_data
        )
        if playlist_response.status_code != 201:
            print(f"Error creating playlist: {playlist_response.status_code}, {playlist_response.text}")
            return redirect('users:spotify_login')

        playlist = playlist_response.json()
        playlist_id = playlist['id']

        # Step 4: Add tracks to the playlist
        add_tracks_response = requests.post(
            f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
            headers=headers,
            json={"uris": track_uris}
        )
        if add_tracks_response.status_code != 201:
            print(f"Error adding tracks to playlist: {add_tracks_response.status_code}, {add_tracks_response.text}")
            return redirect('users:spotify_login')

        # Redirect to the playlist URL
        return redirect(playlist['external_urls']['spotify'])

    except Exception as e:
        print(f"Error creating top tracks playlist: {str(e)}")
        return redirect('users:spotify_login')

def profile(request):
    """
    Renders the profile page for the logged-in user, displaying their Spotify Wrapped data.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered profile page or a redirect to the home page.
    """

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('users:home')

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    try:
        # Get subscription type
        subscription_type = "https://api.spotify.com/v1/me/product"
         # Get top 20 tracks for "Guess the Song" game
        guess_track_url = "https://api.spotify.com/v1/me/top/tracks"
        guess_track_response = requests.get(
            guess_track_url, headers=headers, params={"limit": 3, "time_range": "long_term"}
        )

        if guess_track_response.status_code != 200:
            print(
                f"Error fetching tracks for 'Guess the Song': {guess_track_response.status_code}, {guess_track_response.text}")
            return redirect('spotify_login')

        top_3_tracks = guess_track_response.json().get('items', [])

        # Select a random track for the game
        random_track = random.choice(top_3_tracks) if top_3_tracks else None
        track_snippet = {
            "name": random_track["name"] if random_track else None,
            "artist": random_track["artists"][0]["name"] if random_track else None,
            "preview_url": random_track.get("preview_url") if random_track else None,
            "uri": random_track["uri"],
            "duration" : random_track["duration_ms"],
            "choices": [random_track["name"]] if random_track else []
        }
        # Get top tracks
        top_track_url = "https://api.spotify.com/v1/me/top/tracks"
        top_track_response = requests.get(
            top_track_url, headers=headers, params={"limit": 5, "time_range": "long_term"}
        )

        if top_track_response.status_code != 200:
            print(f"Error fetching top tracks: {top_track_response.status_code}, {top_track_response.text}")
            return redirect('spotify_login')

        top_tracks = top_track_response.json().get('items', [])
        # Get user's Spotify profile details
        user_profile_response = requests.get(
            'https://api.spotify.com/v1/me',
            headers=headers
        )
        if user_profile_response.status_code != 200:
            print(f"Error fetching user profile: {user_profile_response.status_code}, {user_profile_response.text}")
            request.session.flush()
            return redirect('users:home')

        user_profile = user_profile_response.json()
        spotify_user_id = user_profile['id']


        # Get user's wraps from the database
        user_wraps = SpotifyWrapped.objects.filter(
            spotify_user_id=spotify_user_id
        ).order_by('-created_at')
        user_data = {
            "top_track": {
                "name": top_tracks[0]["name"],
                "uri": top_tracks[0]["uri"],
                "image_url": top_tracks[0]["album"]["images"][0]["url"] if top_tracks[0]["album"]["images"] else None,
            } if top_tracks else None,
            "subscription_type" : subscription_type,
            "guess_song_game": track_snippet,
            "top_3_tracks" : top_3_tracks,
        }

        # Prepare context for the template
        context = {
            'user_name': user_profile.get('display_name', spotify_user_id),
            'user_data' : user_data,
            'user_wraps': user_wraps,
            'profile_data': user_profile,
            'is_authenticated': True
        }

        return render(request, 'profile.html', context)

    except Exception as e:
        print(f"Error in profile view: {str(e)}")
        request.session.flush()  # Clear session on error
        return redirect('users:home')

def contact_us(request):
    """
    Renders the contact page where users can reach out to the developers.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered contact page.
    """

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('/')  # Redirect if not authenticated
    return render(request, "contact.html")

def view_public_wrapped(request):
    """
   Displays all Spotify Wrapped posts that users have made public.

   Args:
       request (HttpRequest): The HTTP request object.

   Returns:
       HttpResponse: The rendered public Spotify Wrapped page.
   """

    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('/')

    """View all public Spotify Wrapped posts"""
    public_wraps = SpotifyWrapped.objects.filter(public=True).order_by('-created_at')
    return render(request, 'public_wrapped.html', {'public_wraps': public_wraps})


@require_http_methods(["POST"])
def toggle_wrap_visibility(request, wrap_id):
    """
    Toggles the visibility of a wrap between public and private.
    Only the owner can toggle visibility.

    Args:
        request (HttpRequest): The HTTP request object
        wrap_id (int): The ID of the wrap to toggle

    Returns:
        HttpResponse: Redirects to profile page after toggling
    """

    # Verify user is authenticated
    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('users:spotify_login')

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    try:
        # Fetch the current user's Spotify profile directly via API
        user_profile_response = requests.get(
            'https://api.spotify.com/v1/me',
            headers=headers
        )
        if user_profile_response.status_code != 200:
            print(f"Error fetching user profile: {user_profile_response.status_code}, {user_profile_response.text}")
            return redirect('users:spotify_login')

        user_profile = user_profile_response.json()
        spotify_user_id = user_profile['id']

        # Get the wrap from the database
        wrap = get_object_or_404(SpotifyWrapped, id=wrap_id)

        # Verify ownership
        if wrap.spotify_user_id != spotify_user_id:
            return HttpResponseForbidden("You don't have permission to modify this wrap")

        # Toggle visibility
        wrap.public = not wrap.public
        wrap.save()

        # Return JSON response for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'public': wrap.public,
                'message': 'Wrap is now public' if wrap.public else 'Wrap is now private'
            })

    except Exception as e:
        print(f"Error toggling wrap visibility: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    # Redirect to profile page for non-AJAX requests
    return redirect('users:profile')

@require_http_methods(["POST"])
def save_wrap(request):
    """
    Saves the user's Spotify Wrapped data including top artist, track, and genre,
    along with related images and additional metadata.

    This function retrieves user data using the Spotify API and stores it in the database.
    It includes top artists, top tracks, the most common genre, and matching artists
    associated with that genre. The data is saved in the SpotifyWrapped model.

    Args:
        request (HttpRequest): The HTTP request object containing the session data.

    Returns:
        JsonResponse: A JSON response indicating the success or failure of the operation.
    """

    access_token = request.session.get('access_token')
    if not access_token:
        return JsonResponse({'error': 'No access token found'}, status=401)

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    try:
        # Get user's Spotify profile
        user_profile_response = requests.get('https://api.spotify.com/v1/me', headers=headers)
        if user_profile_response.status_code != 200:
            raise Exception(f"Error fetching user profile: {user_profile_response.json()}")

        user_profile = user_profile_response.json()
        spotify_user_id = user_profile['id']
        spotify_display_name = user_profile.get('display_name', spotify_user_id)

        # Get top artists
        top_artist_response = requests.get(
            'https://api.spotify.com/v1/me/top/artists?limit=5&time_range=long_term',
            headers=headers
        )
        if top_artist_response.status_code != 200:
            raise Exception(f"Error fetching top artists: {top_artist_response.json()}")

        top_artists = top_artist_response.json().get('items', [])
        if not top_artists:
            return JsonResponse({'error': 'No top artists found'}, status=404)

        top_artist = top_artists[0].get("name", "Unknown Artist")
        top_artist_images = top_artists[0].get("images", [])
        top_artist_image_url = top_artist_images[0]["url"] if top_artist_images else None

        # Get top tracks
        top_track_response = requests.get(
            'https://api.spotify.com/v1/me/top/tracks?limit=5&time_range=long_term',
            headers=headers
        )
        if top_track_response.status_code != 200:
            raise Exception(f"Error fetching top tracks: {top_track_response.json()}")

        top_tracks = top_track_response.json().get('items', [])
        if not top_tracks:
            return JsonResponse({'error': 'No top tracks found'}, status=404)

        top_track = top_tracks[0].get("name", "Unknown Track")
        top_track_uri = top_tracks[0].get('uri', '')
        top_track_images = top_tracks[0].get("album", {}).get("images", [])
        top_track_image_url = top_track_images[0]["url"] if top_track_images else None

        # Get top genre
        top_genre = top_artists[0].get("genres", ["Unknown"])[0] if top_artists else "Unknown"

        # Get all artists from the top 5 that match the top genre
        matching_artists = []
        for artist in top_artists:
            if top_genre in artist.get('genres', []):
                matching_artists.append({
                    'name': artist.get('name', 'Unknown Artist'),
                    'image_url': artist.get('images', [{}])[0].get('url', None)
                })

        # Prepare top 4 track images for the grid
        top_tracks_images = []
        for track in top_tracks[:4]:
            album_images = track.get("album", {}).get("images", [])
            if album_images:
                top_tracks_images.append({
                    "name": track["name"],
                    "image_url": album_images[0]["url"],
                })

        # Get top 20 tracks for "Guess the Song" game
        guess_track_url = "https://api.spotify.com/v1/me/top/tracks"
        guess_track_response = requests.get(
            guess_track_url, headers=headers, params={"limit": 3, "time_range": "long_term"}
        )

        if guess_track_response.status_code != 200:
            raise Exception(f"Error fetching tracks for 'Guess the Song': {guess_track_response.json()}")

        top_3_tracks = guess_track_response.json().get('items', [])

        # Select a random track for the game
        random_track = random.choice(top_3_tracks) if top_3_tracks else None
        track_snippet = {
            "name": random_track["name"] if random_track else None,
            "artist": random_track["artists"][0]["name"] if random_track else None,
            "preview_url": random_track.get("preview_url") if random_track else None,
            "uri": random_track["uri"] if random_track else None,
            "choices": [random_track["name"]] if random_track else []
        }
        guess_uri = random_track["uri"]

        # Get subscription type
        subscription_type = "https://api.spotify.com/v1/me/product"

        # Save the wrap with all data
        wrap = SpotifyWrapped(
            spotify_user_id=spotify_user_id,
            spotify_display_name=spotify_display_name,
            created_at=now(),
            top_artist=top_artist,
            top_artist_image_url=top_artist_image_url,
            top_track=top_track,
            top_track_image_url=top_track_image_url,
            top_genre=top_genre,
            top_track_uri=top_track_uri,
            top_artists=top_artists,
            top_tracks=top_tracks,
            top_tracks_images=top_tracks_images,
            matching_artists=matching_artists,
            guess_song_uri=guess_uri,
            guess_song_game=track_snippet,
            top_3_tracks=top_3_tracks,
            top_3_artists=top_artists[:3],
            subscription_type=subscription_type,
            public=True
        )
        wrap.save()

        return JsonResponse({
            'success': True,
            'message': 'Wrap saved successfully!',
            'redirect_url': '/profile/',
        })

    except Exception as e:
        print(f"Error saving wrap: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def delete_user(request):
    """
    Deletes the current user from the system along with all their wraps,
    and logs them out.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Redirects to the home page after deletion.
    """
    access_token = request.session.get('access_token')
    if not access_token:
        return redirect('users:spotify_login')

    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        # Get current user's Spotify profile
        user_profile_url = "https://api.spotify.com/v1/me"
        user_profile_response = requests.get(user_profile_url, headers=headers)

        if user_profile_response.status_code != 200:
            raise Exception("Failed to fetch user profile")

        user_profile = user_profile_response.json()
        spotify_user_id = user_profile['id']

        # Get all wraps associated with the user
        user_wraps = SpotifyWrapped.objects.filter(spotify_user_id=spotify_user_id)

        # Delete all wraps
        for wrap in user_wraps:
            wrap.delete()

        # Log the user out
        return redirect('users:signout')

    except Exception as e:
        print(f"Error deleting user: {str(e)}")
        return JsonResponse({'error': 'Failed to delete user account. Please try again.'}, status=500)