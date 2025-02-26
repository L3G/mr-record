from flask import Flask
import requests
from datetime import datetime, timedelta
import pytz
import time

app = Flask(__name__)

# Marvel Rivals API configuration
API_KEY = "107702406c06c403bec91048d3ea4a7923b68d627bb14ad538d955ab9f8fa3d3"
BASE_URL = "https://marvelrivalsapi.com/api/v1"

# Cache for update calls to prevent rate limiting
UPDATE_CACHE = {}
UPDATE_CACHE_DURATION = 30 * 60  # 30 minutes in seconds

# Rank mapping based on level
RANKS = {
    1: "Bronze 3",
    2: "Bronze 2",
    3: "Bronze 1",
    4: "Silver 3",
    5: "Silver 2",
    6: "Silver 1",
    7: "Gold 3",
    8: "Gold 2",
    9: "Gold 1",
    10: "Platinum 3",
    11: "Platinum 2",
    12: "Platinum 1",
    13: "Diamond 3",
    14: "Diamond 2",
    15: "Diamond 1",
    16: "Grandmaster 3",
    17: "Grandmaster 2",
    18: "Grandmaster 1",
    19: "Celestial 3",
    20: "Celestial 2",
    21: "Celestial 1",
    22: "Eternity",
    23: "One Above All",
}

def convert_timestamp_to_date(timestamp):
    """Convert Unix timestamp to date in UTC"""
    try:
        dt = datetime.fromtimestamp(timestamp, pytz.UTC).date()
        return dt
    except Exception as e:
        # Return a far-future date to avoid matches
        return datetime(2099, 1, 1).date()

def should_update_player(player_id):
    """Check if we should update the player based on cache"""
    current_time = time.time()
    last_update = UPDATE_CACHE.get(player_id, 0)
    
    if current_time - last_update >= UPDATE_CACHE_DURATION:
        UPDATE_CACHE[player_id] = current_time
        return True
    return False

def get_rank_from_level(level):
    """Get rank name from level"""
    return RANKS.get(level, "Unknown Rank")

@app.route('/marvel-rivals/player/<player_id>/stats/today', methods=['GET'])
def get_player_stats_today(player_id):
    """
    Get the win/loss stats and RR change for a player for yesterday
    
    Args:
        player_id: The unique player identifier (either UID or username)
        
    Returns:
        Plaintext response with rank, wins, losses, and RR change
    """
    # Use current date for stats
    today = datetime.now(pytz.UTC).date()
    target_date = today
    
    # Headers for API requests
    headers = {
        "accept": "application/json",
        "x-api-key": API_KEY
    }
    
    # Headers specifically for the update endpoint
    update_headers = {
        "accept": "application/json",
        "X-API-Key": API_KEY
    }
    
    # Try to update player data if not recently updated
    if should_update_player(player_id):
        update_url = f"{BASE_URL}/player/{player_id}/update"
        
        try:
            requests.get(update_url, headers=update_headers)
        except requests.exceptions.RequestException:
            # Continue even if update fails
            pass
    
    # Initialize variables
    wins = 0
    losses = 0
    total_rr_change = 0
    current_level = None
    most_recent_timestamp = 0
    player_name = player_id  # Default to player ID if name not found
    
    # Fetch all matches with pagination
    skip = 0
    season = 2  # Current season
    
    try:
        while True:
            # Get match history
            history_url = f"{BASE_URL}/player/{player_id}/match-history?season={season}&skip={skip}&game_mode=0"
            
            history_response = requests.get(history_url, headers=headers)
            history_response.raise_for_status()
            
            match_data = history_response.json()
            
            # If no matches or empty response, break the loop
            if not match_data or "match_history" not in match_data or not match_data["match_history"]:
                break
            
            matches = match_data["match_history"]
            
            # Process each match
            for match in matches:
                match_timestamp = match.get("match_time_stamp")
                
                if match_timestamp:
                    # Track most recent match for rank determination
                    if match_timestamp > most_recent_timestamp:
                        most_recent_timestamp = match_timestamp
                        # Get player's match details for most recent match
                        match_player = match.get("match_player", {})
                        score_info = match_player.get("score_info", {})
                        if score_info and "new_level" in score_info:
                            current_level = score_info["new_level"]
                    
                    match_date = convert_timestamp_to_date(match_timestamp)
                    
                    # Check if match was played on the target date
                    if match_date == target_date:
                        # Get player's match details
                        match_player = match.get("match_player", {})
                        
                        # Add RR change
                        score_info = match_player.get("score_info", {})
                        if score_info and "add_score" in score_info:
                            total_rr_change += score_info["add_score"]
                        
                        # Check the is_win field
                        is_win_data = match_player.get("is_win", {})
                        
                        # Handle the case where is_win is an object with a property called is_win
                        if isinstance(is_win_data, dict) and "is_win" in is_win_data:
                            if is_win_data["is_win"]:
                                wins += 1
                            else:
                                losses += 1
                        # Handle the case where is_win might be a direct boolean
                        elif isinstance(is_win_data, bool):
                            if is_win_data:
                                wins += 1
                            else:
                                losses += 1
            
            # Update skip for pagination
            skip += len(matches)
            
            # If fewer matches than the default page size, we've reached the end
            if len(matches) < 20:
                break
                
    except requests.exceptions.RequestException as e:
        return f"Error fetching match history: {str(e)}", 500
    
    # Get the player's rank based on level
    rank = get_rank_from_level(current_level) if current_level else "Unknown Rank"
    
    # Format RR change
    rr_change_str = f"+{round(total_rr_change)}" if total_rr_change >= 0 else f"{round(total_rr_change)}"
    
    # Return the formatted plaintext response
    today_str = today.strftime("%B %d, %Y")
    response_text = f"Rank {rank}. They've won {wins}, lost {losses}, and have {rr_change_str} RR today."
    
    return response_text

@app.route('/marvel-rivals/player/<player_id>/clear-cache', methods=['GET'])
def clear_player_cache(player_id):
    """Clear the update cache for a player"""
    if player_id in UPDATE_CACHE:
        del UPDATE_CACHE[player_id]
        return f"Cache cleared for player {player_id}"
    else:
        return f"No cache entry found for player {player_id}"

if __name__ == '__main__':
    app.run(debug=True, port=8080)