"""
NEW_X1 — UI Component: Cricket Field Visualization
Generates an SVG or HTML visual diagram of a cricket pitch with 11 players positioned
based on their roles (Wicketkeeper, Batters, All-Rounders, Bowlers).
"""

def render_cricket_pitch(players: list[dict]) -> str:
    """
    Renders an SVG cricket field layout with player pins.
    players: list of dicts with keys: name, role, predicted_score, team, is_captain, is_vc, injury_status
    """
    # Coordinates for standard positions (viewbox 800 x 600)
    # Pitch center ~ (400, 300)
    # Stumps at (400, 240) and (400, 360)

    # Separate by role
    wks = [p for p in players if p.get("role", "").upper() in ("WK", "WICKETKEEPER")]
    bats = [p for p in players if p.get("role", "").upper() in ("BAT", "BATTER")]
    ars = [p for p in players if p.get("role", "").upper() in ("AR", "ALLROUNDER", "ALL-ROUNDER")]
    bowls = [p for p in players if p.get("role", "").upper() in ("BOWL", "BOWLER")]

    # Position definitions
    positions = []

    # WK: behind stumps
    if wks:
        positions.append((wks[0], 400, 180, "WK"))

    # Batters: in infield & boundary covers
    bat_coords = [(310, 280), (490, 280), (250, 220), (550, 220), (330, 420), (470, 420)]
    for i, b in enumerate(bats):
        if i < len(bat_coords):
            positions.append((b, bat_coords[i][0], bat_coords[i][1], "BAT"))

    # All-rounders: mid-wicket / covers
    ar_coords = [(220, 360), (580, 360), (400, 450)]
    for i, a in enumerate(ars):
        if i < len(ar_coords):
            positions.append((a, ar_coords[i][0], ar_coords[i][1], "AR"))

    # Bowlers: deep boundary / attack spots
    bowl_coords = [(400, 100), (180, 170), (620, 170), (180, 450), (620, 450)]
    for i, bw in enumerate(bowls):
        if i < len(bowl_coords):
            positions.append((bw, bowl_coords[i][0], bowl_coords[i][1], "BOWL"))

    # Fill any remaining players into open slots
    assigned = {p["name"] for p, _, _, _ in positions}
    unassigned = [p for p in players if p["name"] not in assigned]
    backup_coords = [(300, 140), (500, 140), (280, 500), (520, 500)]
    for i, p in enumerate(unassigned):
        if i < len(backup_coords):
            positions.append((p, backup_coords[i][0], backup_coords[i][1], p.get("role", "PLY")))

    # Generate SVG Nodes
    player_nodes = []
    for p, x, y, role_badge in positions:
        name = p.get("name", "Player")
        pts = p.get("predicted_score", 0.0)
        is_c = p.get("is_captain", False)
        is_vc = p.get("is_vc", False)
        badge_text = role_badge
        if is_c:
            badge_text = "C"
        elif is_vc:
            badge_text = "VC"

        badge_color = "#f59e0b" if is_c else ("#3b82f6" if is_vc else "#10b981")
        card_bg = "#1e293b"

        node = f"""
        <g transform="translate({x}, {y})">
            <!-- Card shadow & box -->
            <rect x="-65" y="-22" width="130" height="44" rx="8" fill="{card_bg}" stroke="#334155" stroke-width="1.5"/>
            <!-- Role Badge -->
            <circle cx="-45" cy="0" r="14" fill="{badge_color}"/>
            <text x="-45" y="4" font-size="10" font-weight="bold" fill="#ffffff" text-anchor="middle">{badge_text}</text>
            <!-- Player Name -->
            <text x="-25" y="-4" font-size="11" font-weight="600" fill="#f8fafc">{name[:13]}</text>
            <!-- Score -->
            <text x="-25" y="12" font-size="10" fill="#94a3b8">{pts} pts</text>
        </g>
        """
        player_nodes.append(node)

    svg = f"""
    <div style="display: flex; justify-content: center; background: #0f172a; border-radius: 12px; padding: 15px; border: 1px solid #1e293b;">
        <svg viewBox="0 0 800 600" style="max-width: 100%; height: auto; border-radius: 10px;">
            <!-- Outer Grass Field -->
            <ellipse cx="400" cy="300" rx="380" ry="280" fill="#14532d" stroke="#166534" stroke-width="6"/>
            <!-- 30-Yard Circle Inner Ring -->
            <ellipse cx="400" cy="300" rx="260" ry="190" fill="none" stroke="#22c55e" stroke-dasharray="8,6" stroke-width="2.5" opacity="0.65"/>
            <!-- Pitch Strip -->
            <rect x="375" y="220" width="50" height="160" rx="4" fill="#ca8a04" stroke="#a16207" stroke-width="2"/>
            <!-- Crease lines -->
            <line x1="375" y1="240" x2="425" y2="240" stroke="#ffffff" stroke-width="2"/>
            <line x1="375" y1="360" x2="425" y2="360" stroke="#ffffff" stroke-width="2"/>
            <!-- Wickets -->
            <circle cx="400" cy="238" r="3" fill="#ffffff"/>
            <circle cx="400" cy="362" r="3" fill="#ffffff"/>
            
            <!-- Player Nodes -->
            {''.join(player_nodes)}
        </svg>
    </div>
    """
    return svg
