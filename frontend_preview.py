
import os
import psycopg2
from flask import Flask, render_template_string, redirect, url_for

# DB Connection
DB_CONNECTION_STRING = "postgresql://neondb_owner:npg_UoHEdMg7eAl5@ep-crimson-snow-a13t7sij-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SportsDB Live Preview</title>
    <meta http-equiv="refresh" content="5"> <!-- Auto refresh every 5s -->
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; padding: 20px; color: #1e293b; }
        
        .nav { margin-bottom: 25px; display: flex; gap: 15px; background: white; padding: 15px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .nav a { text-decoration: none; padding: 10px 25px; border-radius: 8px; font-weight: 600; color: #64748b; transition: all 0.2s; }
        .nav a:hover { background: #f1f5f9; color: #334155; }
        .nav a.active { background: #2563eb; color: white; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2); }
        .nav a.log-tab { color: #d97706; }
        .nav a.log-tab.active { background: #d97706; color: white; box-shadow: 0 4px 6px -1px rgba(217, 119, 6, 0.2); }
        
        h1 { font-size: 1.5rem; margin-bottom: 20px; color: #0f172a; display: flex; align-items: center; gap: 10px; }
        .badge { font-size: 0.75rem; background: #e2e8f0; color: #475569; padding: 4px 8px; border-radius: 99px; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; }
        
        .card { background: white; border-radius: 16px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
        
        .header { display: flex; justify-content: space-between; margin-bottom: 15px; align-items: center; }
        .status { font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
        .status.live { background: #ffe4e6; color: #e11d48; } /* Red */
        .status.finished { background: #f1f5f9; color: #64748b; } /* Gray */
        .status.upcoming { background: #eff6ff; color: #2563eb; } /* Blue */
        
        .match-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .team-name { font-weight: 600; font-size: 1.1rem; color: #0f172a; }
        .team-score { font-family: "JetBrains Mono", monospace; font-weight: 700; font-size: 1.25rem; color: #0f172a; }
        
        .batting-team { color: #2563eb; } 
        
        .footer { margin-top: 15px; padding-top: 15px; border-top: 1px solid #f1f5f9; font-size: 0.8rem; color: #94a3b8; display: flex; justify-content: space-between; }
        
        .empty { grid-column: 1/-1; text-align: center; padding: 40px; color: #64748b; background: white; border-radius: 12px; }

        /* Termimal Logs */
        .terminal { background: #1e1e1e; color: #10b981; padding: 20px; border-radius: 12px; font-family: "JetBrains Mono", monospace; font-size: 0.9rem; height: 80vh; overflow-y: auto; white-space: pre-wrap; line-height: 1.5; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2); }
        .log-line { border-bottom: 1px solid #333; padding: 2px 0; }
        .log-error { color: #ef4444; }
        .log-warn { color: #f59e0b; }
        .log-info { color: #3b82f6; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/cricket" class="{{ 'active' if sport == 'cricket' else '' }}">🏏 Cricket</a>
        <a href="/football" class="{{ 'active' if sport == 'football' else '' }}">⚽ Football</a>
        <a href="/tennis" class="{{ 'active' if sport == 'tennis' else '' }}">🎾 Tennis</a>
        <a href="/logs" class="log-tab {{ 'active' if sport == 'logs' else '' }}">🤖 AI Logs</a>
    </div>

    {% if sport == 'logs' %}
        <h1>🧠 Architect Agent Brain</h1>
        <div class="terminal" id="terminal">
            {% for line in logs %}
                <div class="log-line {% if 'Error' in line %}log-error{% elif 'Warn' in line %}log-warn{% elif 'Diagnosing' in line %}log-info{% endif %}">{{ line|safe }}</div>
            {% endfor %}
        </div>
        <script>
            // Scroll to bottom
            const t = document.getElementById('terminal');
            t.scrollTop = t.scrollHeight;
        </script>
    {% else %}
        <h1>
            {{ sport.capitalize() }} Live Feed 
            <span class="badge">{{ matches|length }} Matches</span>
        </h1>

        <div class="grid">
            {% for m in matches %}
            <div class="card">
                <div class="header">
                    <span class="id">#{{ m.match_id }}</span>
                    {% if m.is_live %}
                        <span class="status live">● LIVE</span>
                    {% elif 'ended' in m.status|lower or 'finished' in m.status|lower %}
                        <span class="status finished">Finished</span>
                    {% else %}
                        <span class="status upcoming">{{ m.status }}</span>
                    {% endif %}
                </div>
                
                <!-- Home Team -->
                <div class="match-row">
                    <span class="team-name {% if m.batting_team == m.home_team %}batting-team{% endif %}">
                        {{ m.home_team }}
                    </span>
                    <span class="team-score">{{ m.home_score if m.home_score != '0' else '-' }}</span>
                </div>
                
                <!-- Away Team -->
                <div class="match-row">
                    <span class="team-name {% if m.batting_team == m.away_team %}batting-team{% endif %}">
                        {{ m.away_team }}
                    </span>
                    <span class="team-score">{{ m.away_score if m.away_score != '0' else '-' }}</span>
                </div>
                
                <div class="footer">
                    <span>{{ m.status }}</span> 
                    <span>Updated: {{ m.last_updated.strftime('%H:%M:%S') }} UTC</span>
                </div>
            </div>
            {% else %}
            <div class="empty">No matches found for {{ sport }}. Scraper might be paused or no live games.</div>
            {% endfor %}
        </div>
    {% endif %}
</body>
</html>
"""

def get_matches(sport):
    table_map = {
        'cricket': 'live_cricket',
        'football': 'live_football',
        'tennis': 'live_tennis'
    }
    table = table_map.get(sport, 'live_cricket')
    
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        cur = conn.cursor()
        
        # Select key columns
        query = f"""
            SELECT match_id, home_team, away_team, home_score, away_score, 
                   status, is_live, batting_team, last_updated 
            FROM {table} 
            ORDER BY is_live DESC, last_updated DESC
        """
        cur.execute(query)
        rows = cur.fetchall()
        
        results = []
        for r in rows:
            results.append({
                'match_id': r[0],
                'home_team': r[1],
                'away_team': r[2],
                'home_score': r[3],
                'away_score': r[4],
                'status': r[5],
                'is_live': r[6],
                'batting_team': r[7],
                'last_updated': r[8]
            })
            
        conn.close()
        return results
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_architect_logs():
    try:
        # Read the last 100 lines of architect.log
        if os.path.exists('architect.log'):
            with open('architect.log', 'r') as f:
                lines = f.readlines()
                return [l.strip() for l in lines[-200:]] # Return last 200 lines
    except: pass
    return ["Log file not found or empty."]

@app.route('/')
def index():
    return redirect(url_for('show_sport', sport='cricket'))

@app.route('/logs')
def show_logs():
    logs = get_architect_logs()
    return render_template_string(HTML_TEMPLATE, sport='logs', logs=logs, matches=[])

@app.route('/<sport>')
def show_sport(sport):
    if sport not in ['cricket', 'football', 'tennis']:
        # Fallback
        return redirect(url_for('show_logs'))
    
    matches = get_matches(sport)
    return render_template_string(HTML_TEMPLATE, sport=sport, matches=matches)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
