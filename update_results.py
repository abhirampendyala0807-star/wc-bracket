import json
import urllib.request
import ssl
import sys

# 32 team names matching the simulator
SIM_TEAMS = [
    "Argentina", "Spain", "France", "England", "Portugal", "Brazil", "Morocco", "Netherlands",
    "Belgium", "Germany", "Croatia", "Colombia", "Mexico", "Senegal", "USA", "Japan",
    "Switzerland", "Ecuador", "Austria", "Australia", "Algeria", "Egypt", "Canada", "Norway",
    "Côte d'Ivoire", "Sweden", "Paraguay", "DR Congo", "South Africa", "Bosnia & Herz.", "Cape Verde", "Ghana"
]

ORIGINAL_R32 = [
    ["Sweden","France"],       # 0
    ["Paraguay","Germany"],    # 1
    ["Brazil","Japan"],        # 2
    ["Côte d'Ivoire","Norway"],# 3
    ["Mexico","Ecuador"],      # 4
    ["England","DR Congo"],    # 5
    ["Argentina","Cape Verde"],# 6
    ["Australia","Egypt"],     # 7
    ["Switzerland","Algeria"], # 8
    ["Colombia","Ghana"],      # 9
    ["Senegal","Belgium"],     # 10
    ["Bosnia & Herz.","USA"],  # 11
    ["Austria","Spain"],       # 12
    ["Croatia","Portugal"],    # 13
    ["Morocco","Netherlands"], # 14
    ["South Africa","Canada"], # 15
]

def map_team_name(api_name):
    if not api_name:
        return None
    mapping = {
        "United States": "USA",
        "Ivory Coast": "Côte d'Ivoire",
        "Cote d'Ivoire": "Côte d'Ivoire",
        "Congo DR": "DR Congo",
        "Democratic Republic of the Congo": "DR Congo",
        "Bosnia and Herzegovina": "Bosnia & Herz.",
        "Bosnia-Herzegovina": "Bosnia & Herz.",
        "Bosnia": "Bosnia & Herz."
    }
    name = mapping.get(api_name, api_name)
    if name in SIM_TEAMS:
        return name
    return None

def get_subtree_teams(r, s):
    if r == 0:
        return [ORIGINAL_R32[s // 2][s % 2]]
    return get_subtree_teams(r - 1, s * 2) + get_subtree_teams(r - 1, s * 2 + 1)

def find_bracket_match(team_a, team_b):
    for r in range(5):
        num_matches = 16 // (2**r)
        for m in range(num_matches):
            left_teams = get_subtree_teams(r, m * 2)
            right_teams = get_subtree_teams(r, m * 2 + 1)
            
            if (team_a in left_teams and team_b in right_teams) or (team_b in left_teams and team_a in right_teams):
                return r, m
    return None, None

def main():
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request('https://worldcup26.ir/get/games', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        with urllib.request.urlopen(req, context=ctx) as res:
            data = json.loads(res.read().decode('utf-8'))
        
        games = data.get('games', [])
        
        # Load current results.json or start empty
        try:
            with open('results.json', 'r') as f:
                results = json.load(f)
        except Exception:
            results = {}
            
        updated = False
        
        for game in games:
            # Only process completed knockout games
            finished = str(game.get('finished', '')).upper() == 'TRUE'
            if not finished:
                continue
                
            game_type = game.get('type', '')
            if game_type not in ['r32', 'r16', 'qf', 'sf', 'final']:
                continue
                
            home_raw = game.get('home_team_name_en')
            away_raw = game.get('away_team_name_en')
            
            home_team = map_team_name(home_raw)
            away_team = map_team_name(away_raw)
            
            if not home_team or not away_team:
                continue
                
            # Parse scores
            home_score_str = str(game.get('home_score', '0'))
            away_score_str = str(game.get('away_score', '0'))
            
            try:
                hs = int(home_score_str)
                as_score = int(away_score_str)
            except ValueError:
                # Clean prefix score in case of brackets like "1(4)"
                hs = int(home_score_str.split('(')[0].strip())
                as_score = int(away_score_str.split('(')[0].strip())
                
            winner = None
            if hs > as_score:
                winner = home_team
            elif as_score > hs:
                winner = away_team
            else:
                h_pen_raw = game.get('home_penalty_score')
                a_pen_raw = game.get('away_penalty_score')
                if h_pen_raw is not None and a_pen_raw is not None and str(h_pen_raw).upper() != 'NULL' and str(a_pen_raw).upper() != 'NULL':
                    try:
                        h_pen = int(h_pen_raw)
                        a_pen = int(a_pen_raw)
                        if h_pen > a_pen:
                            winner = home_team
                        elif a_pen > h_pen:
                            winner = away_team
                    except Exception:
                        pass
                
                if not winner and '(' in home_score_str and '(' in away_score_str:
                    try:
                        h_pen = int(home_score_str.split('(')[1].replace(')', '').strip())
                        a_pen = int(away_score_str.split('(')[1].replace(')', '').strip())
                        if h_pen > a_pen:
                            winner = home_team
                        elif a_pen > h_pen:
                            winner = away_team
                    except Exception:
                        pass
                
                if not winner:
                    continue
            
            # Map this match to our bracket
            r, m = find_bracket_match(home_team, away_team)
            if r is not None and m is not None:
                r_str = str(r)
                m_str = str(m)
                
                match_data = {
                    "winner": winner,
                    "home": home_team,
                    "away": away_team,
                    "homeScore": hs,
                    "awayScore": as_score,
                    "homeScoreRaw": home_score_str,
                    "awayScoreRaw": away_score_str
                }
                
                if r_str not in results:
                    results[r_str] = {}
                existing = results[r_str].get(m_str)
                is_different = True
                if isinstance(existing, dict):
                    if (existing.get("winner") == winner and 
                        existing.get("homeScore") == hs and 
                        existing.get("awayScore") == as_score and
                        existing.get("homeScoreRaw") == home_score_str and
                        existing.get("awayScoreRaw") == away_score_str):
                        is_different = False
                
                if is_different:
                    results[r_str][m_str] = match_data
                    updated = True
                    print(f"Updated Round {r} Match {m}: {home_team} vs {away_team} -> Winner: {winner} (Score: {home_score_str}-{away_score_str})")
                    
        if updated:
            with open('results.json', 'w') as f:
                json.dump(results, f, indent=2)
            print("results.json updated successfully!")
        else:
            print("No new updates found.")
            
    except Exception as e:
        print("Error running updater:", e)
        sys.exit(1)

if __name__ == '__main__':
    main()
