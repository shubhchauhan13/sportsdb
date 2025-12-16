import os
import psycopg2
from flask import Flask, render_template_string

# DB Connection
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SportsDB Preview</title>
    <meta http-equiv="refresh" content="5"> <!-- Auto refresh every 5s -->
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; padding: 20px; }
        .nav { margin-bottom: 20px; display: flex; gap: 10px; }
        .nav a { text-decoration: none; padding: 10px 20px; border-radius: 8px; font-weight: 600; background: white; color: #333; }
        .nav a.active { background: #2563eb; color: white; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }
        .card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .league { font-size: 0.8rem; color: #666; font-weight: 600; text-transform: uppercase; }
        .status { padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
        .status.Live { background: #ffe4e6; color: #e11d48; }
        .status.Upcoming { background: #dbeafe; color: #2563eb; }
        .status.Finished { background: #e5e7eb; color: #374151; }
        .status.Break { background: #fef3c7; color: #d97706; }
        
        .teams { margin-bottom: 15px; }
        .team { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 1.1rem; }
        .team.batting { font-weight: 700; }
        .team.batting::after { content: " 🏏"; }
        
        .score { font-size: 1.5rem; font-weight: 800; color: #1f2937; margin-bottom: 5px; }
        .subtext { font-size: 0.9rem; color: #6b7280; }
        .meta { margin-top: 15px; padding-top: 10px; border-top: 1px solid #eee; font-size: 0.85rem; color: #888; display: flex; justify-content: space-between;}
        
        /* Table Styles */
        table { width: 100%; background: white; border-radius: 12px; border-collapse: collapse; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8fafc; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; color: #64748b; }
        tr:last-child td { border-bottom: none; }
        tr:hover { background: #f8fafc; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/" class="{{ 'active' if page == 'live' else '' }}">Live JSON View</a>
        <a href="/clean" class="{{ 'active' if page == 'clean' else '' }}">Clean Data Table</a>
    </div>

    {% if page == 'live' %}
        <h1>Live Matches (JSON Blob)</h1>
        <div class="grid">
            {% for match in matches %}
            <div class="card">
                <div class="header">
                    <span class="league">{{ match.league_name or match.format or 'Unknown League' }}</span>
                    <span class="status {{ match.event_state }}">{{ match.event_state }}</span>
                </div>
                
                <div class="teams">
                    <div class="team {% if match.batting_team == match.team_a %}batting{% endif %}">
                        {{ match.team_a_name }}
                    </div>
                    <div class="team {% if match.batting_team == match.team_b %}batting{% endif %}">
                        {{ match.team_b_name }}
                    </div>
                </div>
                
                <div class="score">{{ match.score or '--/--' }}</div>
                <div class="subtext">{{ match.status_text }}</div>
                
                <div class="meta">
                    <span>{{ match.current_innings }}</span>
                    <span>{{ match.start_time_iso }}</span>
                </div>
            </div>
            {% endfor %}
        </div>
    {% else %}
        <h1>Clean State Table</h1>
        <table>
            <thead>
                <tr>
                    <th>Match ID</th>
                    <th>Status</th>
                    <th>Match Status</th>
                    <th>League</th>
                    <th>Home Team</th>
                    <th>Away Team</th>
                    <th>Score</th>
                    <th>Innings</th>
                    <th>Updated At</th>
                </tr>
            </thead>
            <tbody>
                {% for match in matches %}
                <tr>
                    <td>{{ match.match_id }}</td>
                    <td><span class="status {{ match.status }}">{{ match.status }}</span></td>
                    <td>{{ match.match_status or '-' }}</td>
                    <td>{{ match.league }}</td>
                    <td>{{ match.team_a }}</td>
                    <td>{{ match.team_b }}</td>
                    <td>{{ match.score }}</td>
                    <td>{{ match.innings }}</td>
                    <td>{{ match.updated_at }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    {% endif %}
</body>
</html>
"""

def get_matches():
    try:

        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Fetch from new live_cricket table
        cur.execute("SELECT match_id, score, status, home_team, away_team, last_updated FROM live_cricket ORDER BY last_updated DESC")
        matches = cur.fetchall()
        conn.close()

        
        # Convert to list of dicts
        matches_list = []
        for m in matches:
            matches_list.append({
                "match_id": m[0],
                "score": m[1],
                "status": m[2],
                "team_a": m[3],
                "team_b": m[4],
                "updated_at": m[5]
            })
        return matches_list
    except Exception as e:
        print(f"Error fetching matches: {e}")
        return []

def get_clean_matches():
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        # Fetch directly from cleanstate table
        cur.execute("SELECT * FROM cleanstate ORDER BY updated_at DESC;")
        # Need to know column names to map to dict
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))
            
        conn.close()
        return results
    except Exception as e:
        print(f"Error fetching cleanstate: {e}")
        return []

@app.route('/')
def index():
    matches = get_matches()
    return render_template_string(HTML_TEMPLATE, matches=matches, page='live')

@app.route('/clean')
def clean():
    matches = get_clean_matches()
    return render_template_string(HTML_TEMPLATE, matches=matches, page="clean")

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
