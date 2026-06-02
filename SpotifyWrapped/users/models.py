# models.py
from django.db import models

class SpotifyWrapped(models.Model):
    # Basic info
    spotify_user_id = models.CharField(max_length=255, null=True, blank=True)
    spotify_display_name = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    public = models.BooleanField(default=True)
    
    # Top items
    top_artist = models.CharField(max_length=255, null=True, blank=True)
    top_artist_image_url = models.URLField(null=True, blank=True)
    top_track = models.CharField(max_length=255, null=True, blank=True)
    top_track_image_url = models.URLField(null=True, blank=True)
    top_genre = models.CharField(max_length=255, null=True, blank=True)

    top_tracks_images = models.JSONField(null=True, blank=True)
    matching_artists = models.JSONField(null=True, blank=True)
    top_3_artists = models.JSONField(null=True, blank=True)
    top_3_tracks = models.JSONField(null=True, blank=True)
    guess_song_game = models.JSONField(null=True, blank=True)
    subscription_type = models.CharField(max_length=255, null=True, blank=True)

    # Lists stored as JSON
    top_artists = models.JSONField(null=True, blank=True)  # Store list of top artists
    top_tracks = models.JSONField(null=True, blank=True)   # Store list of top tracks
    
    # URLs
    top_track_uri = models.CharField(max_length=255, null=True, blank=True)
    guess_song_uri = models.CharField(max_length=255, null=True, blank=True)
    

    def __str__(self):
        """
        Returns a human-readable string representation of the SpotifyWrapped instance.

        The method prioritizes the display of the Spotify user's display name if available,
        followed by their Spotify user ID, and falls back to the creation date of the wrap.
        """
        if self.spotify_display_name:
            return f"{self.spotify_display_name}'s Wrapped"
        elif self.spotify_user_id:
            return f"{self.spotify_user_id}'s Wrapped"
        return f"Spotify Wrapped {self.created_at}"
