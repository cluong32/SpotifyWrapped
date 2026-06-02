from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.welcome, name='welcome'),
    path('spotify/callback/', views.spotify_callback, name='callback'),
    path('spotify/login/', views.spotify_login, name='spotify_login'),  # URL name without hyphen
    path('top-artists/', views.top_artists, name='top_artists'),
    path('top-tracks/', views.top_tracks, name='top_tracks'),
    path('top-genres/', views.top_genres, name='top_albums'),
    path('spotify_wrapped/', views.wrapped_slides, name='spotify_wrapped'),
    path('contact_us/', views.contact_us, name='contact_us'),
    path('profile/', views.profile, name='profile'),
    path('create_top_tracks_playlist/', views.create_top_tracks_playlist, name='create_top_tracks_playlist'),
    path('public-wraps/', views.view_public_wraps, name='public_wraps'),
    path('toggle_wrap_visibility/<int:wrap_id>/', views.toggle_wrap_visibility, name='toggle_wrap_visibility'),
    path('save-wrap/', views.save_wrap, name='save_wrap'),
    path('signout/', views.signout, name='signout'),
    path('delete-wrap/<int:wrap_id>/', views.delete_wrap, name='delete_wrap'),
    path('toggle-wrap-visibility/<int:wrap_id>/', views.toggle_wrap_visibility, name='toggle_wrap_visibility'),
    path('logout/', views.signout, name='signout'),  # Main logout view
    path('logout/complete/', views.signout, name='logout_complete'),  # Optional: for post-Spotify-logout redirect
    path('update-language/', views.update_language, name='update_language'),
    path('delete_user/', views.delete_user, name='delete_user'),
]