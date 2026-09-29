# Metrics (12 agents, 7 days)

## 1. Clothes spend before vs after cohabiting

No cohabiting agent-days in this run; only the single/dating spend is measurable.

```json
{
 "agent_days_not_cohabiting": 84,
 "agent_days_cohabiting": 0,
 "spend_per_agent_day_before": 16.1429,
 "spend_per_agent_day_after": null
}
```

## 2. Marker convergence

The most-worn Mid/High item on app pictures is Linen Shirt, first worn by Avery Chen on day 1; most-matched agent Katherine Lee, most-seen Tara Vance (prestige: False, conformity: False).

```json
{
 "share_by_day": {
  "1": {
   "item": "Linen Shirt",
   "share": 0.75
  },
  "2": {
   "item": "Linen Shirt",
   "share": 0.917
  },
  "3": {
   "item": "Linen Shirt",
   "share": 1.0
  },
  "4": {
   "item": "Linen Shirt",
   "share": 1.0
  },
  "5": {
   "item": "Linen Shirt",
   "share": 0.917
  },
  "6": {
   "item": "Linen Shirt",
   "share": 0.917
  },
  "7": {
   "item": "Linen Shirt",
   "share": 0.833
  }
 },
 "most_matched": "Katherine Lee",
 "most_seen": "Tara Vance",
 "marker": "Linen Shirt",
 "first_worn_by": "Avery Chen",
 "first_worn_day": 1,
 "first_wearer_is_most_matched": false,
 "first_wearer_is_most_seen": false
}
```

## 3. Compensatory consumption

Not computable: over 42 single agent-days one of the two variables has no variance (singles' unmet hugs are 1.0 unless they had a visit).

```json
{
 "single_agent_days": 42,
 "correlation": null,
 "mean_unmet_hugs": 1.0,
 "mean_tier_bought": 0.4048
}
```

## 4. Profile text

Profiles average 144.9048 characters; the yes-rate received by profiles that mention schedule: 0.5167 vs 0.5299, work: None vs 0.5281, money: None vs 0.5281, looks: 0.2508 vs 0.5699.

```json
{
 "mean_length": 144.9048,
 "per_day": {
  "1": {
   "profiles": 12,
   "schedule": 2,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "2": {
   "profiles": 12,
   "schedule": 2,
   "work": 0,
   "money": 0,
   "looks": 1
  },
  "3": {
   "profiles": 12,
   "schedule": 2,
   "work": 0,
   "money": 0,
   "looks": 2
  },
  "4": {
   "profiles": 12,
   "schedule": 2,
   "work": 0,
   "money": 0,
   "looks": 2
  },
  "5": {
   "profiles": 12,
   "schedule": 1,
   "work": 0,
   "money": 0,
   "looks": 2
  },
  "6": {
   "profiles": 12,
   "schedule": 1,
   "work": 0,
   "money": 0,
   "looks": 2
  },
  "7": {
   "profiles": 12,
   "schedule": 1,
   "work": 0,
   "money": 0,
   "looks": 2
  }
 },
 "yes_rate_by_mention": {
  "schedule": {
   "mention": 0.5167,
   "no_mention": 0.5299
  },
  "work": {
   "mention": null,
   "no_mention": 0.5281
  },
  "money": {
   "mention": null,
   "no_mention": 0.5281
  },
  "looks": {
   "mention": 0.2508,
   "no_mention": 0.5699
  }
 }
}
```

## 5. Pairing by need distance

Mean L1 need-weight distance: matched pairs 0.8413 (n=33) vs all pairs 0.9402; couples that broke up 0.8816 (n=10) vs stayed 0.6891 (n=3).

```json
{
 "random_pair_distance": 0.9402,
 "matched_pair_distance": 0.8413,
 "n_matches": 33,
 "breakup_pair_distance": 0.8816,
 "stayed_pair_distance": 0.6891,
 "n_broke": 10,
 "n_stayed": 3
}
```

## 6. Gossip

4 invites, 0 visits, 0 gossip posts; 0 of 8 post-date declines cite gossip or a name on the board.

```json
{
 "invites": 4,
 "visits": 0,
 "posts": 0,
 "declines": 8,
 "declines_citing_gossip": 0,
 "examples": []
}
```

## 7. Couples' division of labour

No cohabiting couples in this run; the division-of-labour comparison is not computable.

```json
{
 "couples": [],
 "cash_transfers": 0
}
```

## 8. Fun and the gamer trap

Game hours by day: {1: 4, 2: 10, 3: 14, 4: 19, 5: 21, 6: 27, 7: 23}; 3 fun-dominant agents, 0 of them never went on a date.

```json
{
 "game_hours_by_day": {
  "1": 4,
  "2": 10,
  "3": 14,
  "4": 19,
  "5": 21,
  "6": 27,
  "7": 23
 },
 "fun_dominant": [
  "Victoria Walker",
  "Kevin Lee",
  "Penelope Quinn"
 ],
 "fun_dominant_never_dated": []
}
```

## 9. Self-knowledge

0 agents tried therapy and 10 meditation; per agent, the shadow need and whether they serve it under or over the population mean are listed (a positive shadow bias makes that need feel more met than it is).

```json
{
 "agents": {
  "Avery Chen": {
   "shadow": "food",
   "shadow_bias": 0.01,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.9286,
   "population_mean_m_shadow": 0.6488,
   "serves_shadow": "over"
  },
  "Katherine Lee": {
   "shadow": "food",
   "shadow_bias": -0.09,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.7857,
   "population_mean_m_shadow": 0.6488,
   "serves_shadow": "over"
  },
  "Victoria Walker": {
   "shadow": "money",
   "shadow_bias": 0.076,
   "first_therapy_day": null,
   "first_meditation_day": 3,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.9464,
   "serves_shadow": "over"
  },
  "Tara Vance": {
   "shadow": "food",
   "shadow_bias": 0.059,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.7143,
   "population_mean_m_shadow": 0.6488,
   "serves_shadow": "over"
  },
  "William Wright": {
   "shadow": "food",
   "shadow_bias": 0.208,
   "first_therapy_day": null,
   "first_meditation_day": 3,
   "mean_m_shadow": 0.7143,
   "population_mean_m_shadow": 0.6488,
   "serves_shadow": "over"
  },
  "Jack Kim": {
   "shadow": "food",
   "shadow_bias": -0.007,
   "first_therapy_day": null,
   "first_meditation_day": 3,
   "mean_m_shadow": 0.6429,
   "population_mean_m_shadow": 0.6488,
   "serves_shadow": "under"
  },
  "Fiona Garcia": {
   "shadow": "money",
   "shadow_bias": 0.266,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 0.9821,
   "population_mean_m_shadow": 0.9464,
   "serves_shadow": "over"
  },
  "Daniel Evans": {
   "shadow": "money",
   "shadow_bias": -0.519,
   "first_therapy_day": null,
   "first_meditation_day": null,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.9464,
   "serves_shadow": "over"
  },
  "Kevin Lee": {
   "shadow": "hugs",
   "shadow_bias": -0.0,
   "first_therapy_day": null,
   "first_meditation_day": null,
   "mean_m_shadow": 0.0,
   "population_mean_m_shadow": 0.0,
   "serves_shadow": "over"
  },
  "Penelope Quinn": {
   "shadow": "food",
   "shadow_bias": -0.049,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.5714,
   "population_mean_m_shadow": 0.6488,
   "serves_shadow": "under"
  },
  "Hannah Ito": {
   "shadow": "fun",
   "shadow_bias": -0.307,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.1054,
   "population_mean_m_shadow": 0.13,
   "serves_shadow": "under"
  },
  "Ulysses Vance": {
   "shadow": "money",
   "shadow_bias": -0.25,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.8929,
   "population_mean_m_shadow": 0.9464,
   "serves_shadow": "under"
  }
 },
 "n_therapy": 0,
 "n_meditation": 10
}
```

## 10. Love residual

No cohabiting agent-days; the love residual is not computable.

```json
{
 "cohabiting_agent_days": 0,
 "days_stayed_with_better_fit_available": {}
}
```
