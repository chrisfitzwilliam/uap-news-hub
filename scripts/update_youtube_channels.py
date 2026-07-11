import json
import os
import sys
import urllib.request
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent
    registry_path = root / "content" / "registry" / "youtube_channels.json"
    
    if not registry_path.exists():
        print(f"Error: Registry file not found at {registry_path}")
        sys.exit(1)
        
    try:
        import yt_dlp
    except ImportError:
        print("Error: yt_dlp is required for fetching channel info. Run: pip install yt-dlp")
        sys.exit(1)

    img_dir = root / "templates" / "assets" / "img" / "channels"
    img_dir.mkdir(parents=True, exist_ok=True)
    
    with open(registry_path, "r", encoding="utf-8") as f:
        channels = json.load(f)
        
    opts = {
        'extract_flat': 'in_playlist',
        'playlist_items': '0',
        'quiet': True,
        'no_warnings': True,
    }
    
    updated = False
    with yt_dlp.YoutubeDL(opts) as ydl:
        for channel in channels:
            if not channel.get("active", True):
                continue
                
            url = channel.get("url")
            if not url:
                continue
                
            print(f"Fetching info for {channel.get('name', url)}...")
            try:
                info = ydl.extract_info(url, download=False)
                
                channel["subscriber_count"] = info.get("channel_follower_count")
                channel["video_count"] = info.get("playlist_count")
                channel["channel_description"] = info.get("description")
                
                # Fetch recent videos to get average views
                videos_url = url.rstrip('/') + '/videos'
                try:
                    v_opts = {'extract_flat': 'in_playlist', 'playlist_items': '1,2,3,4,5,6,7,8,9,10', 'quiet': True}
                    with yt_dlp.YoutubeDL(v_opts) as v_ydl:
                        v_info = v_ydl.extract_info(videos_url, download=False)
                        views = [e.get('view_count') for e in v_info.get('entries', []) if e.get('view_count') is not None]
                        if views:
                            channel["average_views"] = sum(views) // len(views)
                        else:
                            channel["average_views"] = None
                except Exception as ve:
                    print(f"  Could not fetch average views for {url}: {ve}")
                
                thumbnails = info.get("thumbnails", [])
                avatar_url = None
                
                for t in thumbnails:
                    w = t.get("width")
                    h = t.get("height")
                    if w and h and w == h and w >= 88:
                        avatar_url = t.get("url")
                        
                if avatar_url:
                    channel["avatar_url"] = avatar_url
                    img_path = img_dir / f"{channel['id']}.jpg"
                    if not img_path.exists():
                        print(f"  Downloading avatar from {avatar_url}")
                        urllib.request.urlretrieve(avatar_url, img_path)
                
                updated = True
            except Exception as e:
                print(f"  Failed to fetch info for {url}: {e}")
                
    if updated:
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(channels, f, indent=2)
            f.write("\n")
        print("Finished updating youtube_channels.json and downloading avatars.")

if __name__ == "__main__":
    main()
