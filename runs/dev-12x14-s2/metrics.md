# Metrics (12 agents, 14 days)

## 1. Clothes spend before vs after cohabiting

Clothes spend per agent-day is 26.875 before cohabiting and 25.8333 after (72 cohabiting agent-days).

```json
{
 "agent_days_not_cohabiting": 96,
 "agent_days_cohabiting": 72,
 "spend_per_agent_day_before": 26.875,
 "spend_per_agent_day_after": 25.8333
}
```

## 2. Marker convergence

The most-worn Mid/High item on app pictures is Linen Shirt, first worn by Ulysses Vance on day 1; most-matched agent Henry Ito, most-seen Henry Ito (prestige: False, conformity: False).

```json
{
 "share_by_day": {
  "1": {
   "item": "Linen Shirt",
   "share": 0.75
  },
  "2": {
   "item": "Linen Shirt",
   "share": 0.9
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
   "share": 1.0
  },
  "7": {
   "item": "Linen Shirt",
   "share": 1.0
  },
  "8": {
   "item": "Linen Shirt",
   "share": 1.0
  },
  "9": {
   "item": "Linen Shirt",
   "share": 1.0
  },
  "10": {
   "item": "Linen Shirt",
   "share": 0.75
  },
  "11": {
   "item": "Linen Shirt",
   "share": 1.0
  },
  "14": {
   "item": "Linen Shirt",
   "share": 0.5
  }
 },
 "most_matched": "Henry Ito",
 "most_seen": "Henry Ito",
 "marker": "Linen Shirt",
 "first_worn_by": "Ulysses Vance",
 "first_worn_day": 1,
 "first_wearer_is_most_matched": false,
 "first_wearer_is_most_seen": false
}
```

## 3. Compensatory consumption

Not computable: over 38 single agent-days one of the two variables has no variance (singles' unmet hugs are 1.0 unless they had a visit).

```json
{
 "single_agent_days": 38,
 "correlation": null,
 "mean_unmet_hugs": 1.0,
 "mean_tier_bought": 0.5263
}
```

## 4. Profile text

Profiles average 102.8542 characters; the yes-rate received by profiles that mention schedule: 0.7914 vs 0.5074, work: None vs 0.5412, money: None vs 0.5412, looks: None vs 0.5412.

```json
{
 "mean_length": 102.8542,
 "per_day": {
  "1": {
   "profiles": 12,
   "schedule": 2,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "2": {
   "profiles": 10,
   "schedule": 1,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "3": {
   "profiles": 6,
   "schedule": 1,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "4": {
   "profiles": 4,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "5": {
   "profiles": 2,
   "schedule": 1,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "7": {
   "profiles": 2,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "8": {
   "profiles": 2,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "9": {
   "profiles": 2,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "10": {
   "profiles": 4,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "11": {
   "profiles": 2,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "14": {
   "profiles": 2,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  }
 },
 "yes_rate_by_mention": {
  "schedule": {
   "mention": 0.7914,
   "no_mention": 0.5074
  },
  "work": {
   "mention": null,
   "no_mention": 0.5412
  },
  "money": {
   "mention": null,
   "no_mention": 0.5412
  },
  "looks": {
   "mention": null,
   "no_mention": 0.5412
  }
 }
}
```

## 5. Pairing by need distance

Mean L1 need-weight distance: matched pairs 0.7549 (n=15) vs all pairs 0.8834; couples that broke up 0.9903 (n=3) vs stayed 0.8412 (n=5); pairs that reached cohabiting 0.8412 (n=5).

```json
{
 "random_pair_distance": 0.8834,
 "matched_pair_distance": 0.7549,
 "n_matches": 15,
 "breakup_pair_distance": 0.9903,
 "stayed_pair_distance": 0.8412,
 "n_broke": 3,
 "n_stayed": 5,
 "cohabiting_pair_distance": 0.8412,
 "n_cohabiting_pairs": 5
}
```

## 6. Gossip

8 invites, 0 visits, 0 gossip posts; 0 of 5 post-date declines cite gossip or a name on the board.

```json
{
 "invites": 8,
 "visits": 0,
 "posts": 0,
 "declines": 5,
 "declines_citing_gossip": 0,
 "examples": []
}
```

## 7. Couples' division of labour

5 cohabiting couples; work hours before/after per partner are listed. Cash transfers: none (v1 has no gifts or shared cash).

```json
{
 "couples": [
  {
   "pair": [
    "Cameron Diaz",
    "Isabelle Jones"
   ],
   "cohabit_day": 4,
   "Cameron Diaz": {
    "work_before": 11.3333,
    "work_after": 5.4545
   },
   "Isabelle Jones": {
    "work_before": 8.0,
    "work_after": 6.5455
   }
  },
  {
   "pair": [
    "Felix Garcia",
    "Katherine Lee"
   ],
   "cohabit_day": 5,
   "Felix Garcia": {
    "work_before": 8.75,
    "work_after": 5.5
   },
   "Katherine Lee": {
    "work_before": 8.5,
    "work_after": 5.3
   }
  },
  {
   "pair": [
    "Olivia Perez",
    "Samuel Smith"
   ],
   "cohabit_day": 7,
   "Olivia Perez": {
    "work_before": 9.3333,
    "work_after": 7.0
   },
   "Samuel Smith": {
    "work_before": 9.6667,
    "work_after": 7.25
   }
  },
  {
   "pair": [
    "Quentin Ramirez",
    "Sebastian Thompson"
   ],
   "cohabit_day": 10,
   "Quentin Ramirez": {
    "work_before": 8.7778,
    "work_after": 4.8
   },
   "Sebastian Thompson": {
    "work_before": 10.4444,
    "work_after": 8.0
   }
  },
  {
   "pair": [
    "Henry Ito",
    "Xander Zhang"
   ],
   "cohabit_day": 13,
   "Henry Ito": {
    "work_before": 7.25,
    "work_after": 6.0
   },
   "Xander Zhang": {
    "work_before": 7.3333,
    "work_after": 6.0
   }
  }
 ],
 "cash_transfers": 0
}
```

## 8. Fun and the gamer trap

Game hours by day: {1: 10, 2: 13, 3: 34, 4: 37, 5: 38, 6: 37, 7: 38, 8: 37, 9: 36, 10: 36, 11: 33, 12: 34, 13: 33, 14: 34}; 5 fun-dominant agents, 0 of them never went on a date.

```json
{
 "game_hours_by_day": {
  "1": 10,
  "2": 13,
  "3": 34,
  "4": 37,
  "5": 38,
  "6": 37,
  "7": 38,
  "8": 37,
  "9": 36,
  "10": 36,
  "11": 33,
  "12": 34,
  "13": 33,
  "14": 34
 },
 "fun_dominant": [
  "Ulysses Vance",
  "Xander Zhang",
  "Samuel Smith",
  "Henry Ito",
  "Sebastian Thompson"
 ],
 "fun_dominant_never_dated": []
}
```

## 9. Self-knowledge

1 agents tried therapy and 11 meditation; per agent, the shadow need and whether they serve it under or over the population mean are listed (a positive shadow bias makes that need feel more met than it is).

```json
{
 "agents": {
  "Ulysses Vance": {
   "shadow": "money",
   "shadow_bias": -0.194,
   "first_therapy_day": 7,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.7768,
   "population_mean_m_shadow": 0.8519,
   "serves_shadow": "under"
  },
  "Olivia Perez": {
   "shadow": "hugs",
   "shadow_bias": 0.044,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.5179,
   "population_mean_m_shadow": 0.4881,
   "serves_shadow": "over"
  },
  "Xander Zhang": {
   "shadow": "money",
   "shadow_bias": -0.605,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.8304,
   "population_mean_m_shadow": 0.8519,
   "serves_shadow": "under"
  },
  "Samuel Smith": {
   "shadow": "money",
   "shadow_bias": 0.304,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 0.9286,
   "population_mean_m_shadow": 0.8519,
   "serves_shadow": "over"
  },
  "Gavin Hernandez": {
   "shadow": "fun",
   "shadow_bias": 0.464,
   "first_therapy_day": null,
   "first_meditation_day": null,
   "mean_m_shadow": 0.1782,
   "population_mean_m_shadow": 0.1461,
   "serves_shadow": "over"
  },
  "Katherine Lee": {
   "shadow": "money",
   "shadow_bias": 0.831,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.7321,
   "population_mean_m_shadow": 0.8519,
   "serves_shadow": "under"
  },
  "Felix Garcia": {
   "shadow": "hugs",
   "shadow_bias": -0.535,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.7857,
   "population_mean_m_shadow": 0.4881,
   "serves_shadow": "over"
  },
  "Isabelle Jones": {
   "shadow": "food",
   "shadow_bias": -0.439,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.9107,
   "serves_shadow": "over"
  },
  "Quentin Ramirez": {
   "shadow": "food",
   "shadow_bias": -0.047,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 0.9286,
   "population_mean_m_shadow": 0.9107,
   "serves_shadow": "over"
  },
  "Henry Ito": {
   "shadow": "hugs",
   "shadow_bias": -0.293,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 0.2321,
   "population_mean_m_shadow": 0.4881,
   "serves_shadow": "under"
  },
  "Cameron Diaz": {
   "shadow": "money",
   "shadow_bias": 0.318,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.75,
   "population_mean_m_shadow": 0.8519,
   "serves_shadow": "under"
  },
  "Sebastian Thompson": {
   "shadow": "fun",
   "shadow_bias": 0.124,
   "first_therapy_day": null,
   "first_meditation_day": 10,
   "mean_m_shadow": 0.1056,
   "population_mean_m_shadow": 0.1461,
   "serves_shadow": "under"
  }
 },
 "n_therapy": 1,
 "n_meditation": 11
}
```

## 10. Love residual

Over 72 cohabiting agent-days, a better-fit willing single (lower need distance than the partner, swiped yes on the agent at some point) existed and the agent stayed on 9 agent-days.

```json
{
 "cohabiting_agent_days": 72,
 "days_stayed_with_better_fit_available": {
  "Olivia Perez": 3,
  "Katherine Lee": 2,
  "Felix Garcia": 3,
  "Sebastian Thompson": 1
 },
 "examples": [
  {
   "name": "Olivia Perez",
   "day": 9,
   "partner": "Samuel Smith",
   "partner_distance": 0.613,
   "better_fit": [
    {
     "name": "Gavin Hernandez",
     "distance": 0.49
    }
   ]
  },
  {
   "name": "Katherine Lee",
   "day": 9,
   "partner": "Felix Garcia",
   "partner_distance": 1.031,
   "better_fit": [
    {
     "name": "Henry Ito",
     "distance": 0.788
    }
   ]
  },
  {
   "name": "Felix Garcia",
   "day": 9,
   "partner": "Katherine Lee",
   "partner_distance": 1.031,
   "better_fit": [
    {
     "name": "Gavin Hernandez",
     "distance": 0.152
    }
   ]
  },
  {
   "name": "Katherine Lee",
   "day": 10,
   "partner": "Felix Garcia",
   "partner_distance": 1.031,
   "better_fit": [
    {
     "name": "Henry Ito",
     "distance": 0.788
    }
   ]
  },
  {
   "name": "Sebastian Thompson",
   "day": 10,
   "partner": "Quentin Ramirez",
   "partner_distance": 1.859,
   "better_fit": [
    {
     "name": "Henry Ito",
     "distance": 0.411
    }
   ]
  }
 ]
}
```
