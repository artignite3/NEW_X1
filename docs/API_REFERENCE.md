# NEW_X1 — REST API Reference

The backend API runs on **port 8000** (interactive documentation available at `http://localhost:8000/docs`).

---

## 1. Optimal Team Generator
**`POST /generate_best_team`**

Generates the optimal 11-player team from candidate squads for a given match date and format.

### Request Body:
```json
{
  "player_info": [
    "Virat Kohli",
    "Rohit Sharma",
    "Jasprit Bumrah",
    "Glenn Maxwell",
    "Travis Head"
  ],
  "date": "2025-10-15",
  "format": "T20",
  "use_ml": true
}
```

### Response:
```json
{
  "best_team": [
    "Virat Kohli",
    "Rohit Sharma",
    "Glenn Maxwell",
    "Jasprit Bumrah"
  ],
  "player_stats": "[{\"player\":\"Virat Kohli\",\"mean_points\":58.4,...}]",
  "cov_matrix": "[[...]]"
}
```

---

## 2. Team Evaluation
**`POST /team_evaluation`**

Evaluates the overall consistency, diversity, and form metrics of a proposed lineup.

### Request Body:
```json
{
  "best_team": ["Virat Kohli", "Rohit Sharma", "..."],
  "player_stats": "[...]",
  "cov_matrix": "[[...]]"
}
```

### Response:
```json
{
  "team_consistency_score": 54.2,
  "team_diversity_score": 0.85,
  "form_score": 0.90
}
```

---

## 3. Player Analysis (AI Explainer)
**`POST /analyze_player`**

Provides a 2-sentence expert analyst breakdown of why a player was selected or excluded.

### Request Body:
```json
{
  "Player": "Virat Kohli",
  "best_team": ["Virat Kohli", "Rohit Sharma"],
  "format": "T20"
}
```

### Response:
```json
{
  "analysis": "Virat Kohli was selected due to strong form and favorable venue conditions..."
}
```
