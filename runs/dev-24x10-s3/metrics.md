# Metrics (24 agents, 10 days)

## 1. Clothes spend before vs after cohabiting

Clothes spend per agent-day is 32.5263 before cohabiting and 53.3333 after (126 cohabiting agent-days).

```json
{
 "agent_days_not_cohabiting": 114,
 "agent_days_cohabiting": 126,
 "spend_per_agent_day_before": 32.5263,
 "spend_per_agent_day_after": 53.3333
}
```

## 2. Marker convergence

The most-worn Mid/High item on app pictures is Linen Shirt, first worn by Xander Zhang on day 1; most-matched agent Mia Nguyen, most-seen William Wright (prestige: False, conformity: False).

```json
{
 "share_by_day": {
  "1": {
   "item": "Linen Shirt",
   "share": 0.625
  },
  "2": {
   "item": "Linen Shirt",
   "share": 0.786
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
  "6": {
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
   "share": 1.0
  }
 },
 "most_matched": "Mia Nguyen",
 "most_seen": "William Wright",
 "marker": "Linen Shirt",
 "first_worn_by": "Xander Zhang",
 "first_worn_day": 1,
 "first_wearer_is_most_matched": false,
 "first_wearer_is_most_seen": false
}
```

## 3. Compensatory consumption

Pearson r between unmet hugs and clothes tier bought (singles, 38 agent-days) is -0.077.

```json
{
 "single_agent_days": 38,
 "correlation": -0.077,
 "mean_unmet_hugs": 0.9737,
 "mean_tier_bought": 0.7105
}
```

## 4. Profile text

Profiles average 84.8833 characters; the yes-rate received by profiles that mention schedule: 0.7786 vs 0.3999, work: None vs 0.463, money: None vs 0.463, looks: None vs 0.463.

```json
{
 "mean_length": 84.8833,
 "per_day": {
  "1": {
   "profiles": 24,
   "schedule": 5,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "2": {
   "profiles": 14,
   "schedule": 2,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "3": {
   "profiles": 6,
   "schedule": 2,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "4": {
   "profiles": 4,
   "schedule": 1,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "5": {
   "profiles": 2,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "6": {
   "profiles": 2,
   "schedule": 0,
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
   "profiles": 2,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  }
 },
 "yes_rate_by_mention": {
  "schedule": {
   "mention": 0.7786,
   "no_mention": 0.3999
  },
  "work": {
   "mention": null,
   "no_mention": 0.463
  },
  "money": {
   "mention": null,
   "no_mention": 0.463
  },
  "looks": {
   "mention": null,
   "no_mention": 0.463
  }
 }
}
```

## 5. Pairing by need distance

Mean L1 need-weight distance: matched pairs 0.6671 (n=11) vs all pairs 0.8391; couples that broke up None (n=0) vs stayed 0.6671 (n=11); pairs that reached cohabiting 0.6671 (n=11).

```json
{
 "random_pair_distance": 0.8391,
 "matched_pair_distance": 0.6671,
 "n_matches": 11,
 "breakup_pair_distance": null,
 "stayed_pair_distance": 0.6671,
 "n_broke": 0,
 "n_stayed": 11,
 "cohabiting_pair_distance": 0.6671,
 "n_cohabiting_pairs": 11
}
```

## 6. Gossip

10 invites, 2 visits, 2 gossip posts; 0 of 0 post-date declines cite gossip or a name on the board.

```json
{
 "invites": 10,
 "visits": 2,
 "posts": 2,
 "declines": 0,
 "declines_citing_gossip": 0,
 "examples": []
}
```

## 7. Couples' division of labour

11 cohabiting couples; work hours before/after per partner are listed. Cash transfers: none (v1 has no gifts or shared cash).

```json
{
 "couples": [
  {
   "pair": [
    "Avery Chen",
    "Isaac Jones"
   ],
   "cohabit_day": 3,
   "Avery Chen": {
    "work_before": 11.5,
    "work_after": 7.5
   },
   "Isaac Jones": {
    "work_before": 13.5,
    "work_after": 11.375
   }
  },
  {
   "pair": [
    "Wyatt Young",
    "Xander Zhang"
   ],
   "cohabit_day": 3,
   "Wyatt Young": {
    "work_before": 13.0,
    "work_after": 10.0
   },
   "Xander Zhang": {
    "work_before": 11.5,
    "work_after": 7.625
   }
  },
  {
   "pair": [
    "Brianna Cruz",
    "Jack Kim"
   ],
   "cohabit_day": 3,
   "Brianna Cruz": {
    "work_before": 13.5,
    "work_after": 8.75
   },
   "Jack Kim": {
    "work_before": 13.0,
    "work_after": 12.0
   }
  },
  {
   "pair": [
    "Xenia Young",
    "Zara Alvarez"
   ],
   "cohabit_day": 5,
   "Xenia Young": {
    "work_before": 10.5,
    "work_after": 7.6667
   },
   "Zara Alvarez": {
    "work_before": 9.25,
    "work_after": 6.1667
   }
  },
  {
   "pair": [
    "Blake Rodriguez",
    "Penelope Quinn"
   ],
   "cohabit_day": 5,
   "Blake Rodriguez": {
    "work_before": 11.0,
    "work_after": 8.0
   },
   "Penelope Quinn": {
    "work_before": 8.75,
    "work_after": 6.1667
   }
  },
  {
   "pair": [
    "Olivia Perez",
    "Quentin Ramirez"
   ],
   "cohabit_day": 5,
   "Olivia Perez": {
    "work_before": 10.0,
    "work_after": 6.8333
   },
   "Quentin Ramirez": {
    "work_before": 11.5,
    "work_after": 7.8333
   }
  },
  {
   "pair": [
    "Daniel Evans",
    "Felix Garcia"
   ],
   "cohabit_day": 5,
   "Daniel Evans": {
    "work_before": 13.5,
    "work_after": 12.0
   },
   "Felix Garcia": {
    "work_before": 7.5,
    "work_after": 5.5
   }
  },
  {
   "pair": [
    "Mia Nguyen",
    "Ulysses Vance"
   ],
   "cohabit_day": 6,
   "Mia Nguyen": {
    "work_before": 10.2,
    "work_after": 7.6
   },
   "Ulysses Vance": {
    "work_before": 10.6,
    "work_after": 8.4
   }
  },
  {
   "pair": [
    "Chloe Davis",
    "Mason Nguyen"
   ],
   "cohabit_day": 6,
   "Chloe Davis": {
    "work_before": 10.0,
    "work_after": 7.0
   },
   "Mason Nguyen": {
    "work_before": 11.6,
    "work_after": 7.6
   }
  },
  {
   "pair": [
    "Gavin Hernandez",
    "Owen Perez"
   ],
   "cohabit_day": 8,
   "Gavin Hernandez": {
    "work_before": 9.4286,
    "work_after": 10.0
   },
   "Owen Perez": {
    "work_before": 10.8571,
    "work_after": 8.6667
   }
  },
  {
   "pair": [
    "Diana Evans",
    "Jasmine Kim"
   ],
   "cohabit_day": 9,
   "Diana Evans": {
    "work_before": 12.25,
    "work_after": 12.0
   },
   "Jasmine Kim": {
    "work_before": 9.0,
    "work_after": 8.0
   }
  }
 ],
 "cash_transfers": 0
}
```

## 8. Fun and the gamer trap

Game hours by day: {1: 5, 2: 16, 3: 32, 4: 45, 5: 50, 6: 56, 7: 57, 8: 64, 9: 63, 10: 63}; 4 fun-dominant agents, 0 of them never went on a date.

```json
{
 "game_hours_by_day": {
  "1": 5,
  "2": 16,
  "3": 32,
  "4": 45,
  "5": 50,
  "6": 56,
  "7": 57,
  "8": 64,
  "9": 63,
  "10": 63
 },
 "fun_dominant": [
  "Blake Rodriguez",
  "Wyatt Young",
  "Xenia Young",
  "Ulysses Vance"
 ],
 "fun_dominant_never_dated": []
}
```

## 9. Self-knowledge

0 agents tried therapy and 19 meditation; per agent, the shadow need and whether they serve it under or over the population mean are listed (a positive shadow bias makes that need feel more met than it is).

```json
{
 "agents": {
  "Blake Rodriguez": {
   "shadow": "money",
   "shadow_bias": 1.163,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.9573,
   "serves_shadow": "over"
  },
  "William Wright": {
   "shadow": "money",
   "shadow_bias": 0.335,
   "first_therapy_day": null,
   "first_meditation_day": 4,
   "mean_m_shadow": 0.95,
   "population_mean_m_shadow": 0.9573,
   "serves_shadow": "under"
  },
  "Mia Nguyen": {
   "shadow": "food",
   "shadow_bias": -0.085,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.7979,
   "serves_shadow": "over"
  },
  "Xander Zhang": {
   "shadow": "fun",
   "shadow_bias": -0.99,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.1966,
   "population_mean_m_shadow": 0.1818,
   "serves_shadow": "over"
  },
  "Quentin Ramirez": {
   "shadow": "hugs",
   "shadow_bias": 0.492,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.525,
   "population_mean_m_shadow": 0.425,
   "serves_shadow": "over"
  },
  "Olivia Perez": {
   "shadow": "fun",
   "shadow_bias": -0.274,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.1164,
   "population_mean_m_shadow": 0.1818,
   "serves_shadow": "under"
  },
  "Kevin Lee": {
   "shadow": "hugs",
   "shadow_bias": -0.32,
   "first_therapy_day": null,
   "first_meditation_day": null,
   "mean_m_shadow": 0.0,
   "population_mean_m_shadow": 0.425,
   "serves_shadow": "under"
  },
  "Zara Alvarez": {
   "shadow": "food",
   "shadow_bias": 0.492,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.7979,
   "serves_shadow": "over"
  },
  "Chloe Davis": {
   "shadow": "fun",
   "shadow_bias": -0.28,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.1557,
   "population_mean_m_shadow": 0.1818,
   "serves_shadow": "under"
  },
  "Daniel Evans": {
   "shadow": "money",
   "shadow_bias": -0.606,
   "first_therapy_day": null,
   "first_meditation_day": null,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.9573,
   "serves_shadow": "over"
  },
  "Isaac Jones": {
   "shadow": "food",
   "shadow_bias": 0.047,
   "first_therapy_day": null,
   "first_meditation_day": 5,
   "mean_m_shadow": 0.55,
   "population_mean_m_shadow": 0.7979,
   "serves_shadow": "under"
  },
  "Jasmine Kim": {
   "shadow": "money",
   "shadow_bias": -0.213,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.9573,
   "serves_shadow": "over"
  },
  "Avery Chen": {
   "shadow": "money",
   "shadow_bias": 0.717,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.9375,
   "population_mean_m_shadow": 0.9573,
   "serves_shadow": "under"
  },
  "Wyatt Young": {
   "shadow": "hugs",
   "shadow_bias": -0.285,
   "first_therapy_day": null,
   "first_meditation_day": 3,
   "mean_m_shadow": 0.45,
   "population_mean_m_shadow": 0.425,
   "serves_shadow": "over"
  },
  "Penelope Quinn": {
   "shadow": "hugs",
   "shadow_bias": -0.086,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.55,
   "population_mean_m_shadow": 0.425,
   "serves_shadow": "over"
  },
  "Xenia Young": {
   "shadow": "food",
   "shadow_bias": 0.049,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.7979,
   "serves_shadow": "over"
  },
  "Owen Perez": {
   "shadow": "hugs",
   "shadow_bias": 0.285,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 0.3,
   "population_mean_m_shadow": 0.425,
   "serves_shadow": "under"
  },
  "Ulysses Vance": {
   "shadow": "food",
   "shadow_bias": 0.364,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.85,
   "population_mean_m_shadow
```

## 10. Love residual

Over 126 cohabiting agent-days, a better-fit willing single (lower need distance than the partner, swiped yes on the agent at some point) existed and the agent stayed on 16 agent-days.

```json
{
 "cohabiting_agent_days": 126,
 "days_stayed_with_better_fit_available": {
  "Jack Kim": 1,
  "Zara Alvarez": 6,
  "Felix Garcia": 6,
  "Owen Perez": 3
 },
 "examples": [
  {
   "name": "Jack Kim",
   "day": 3,
   "partner": "Brianna Cruz",
   "partner_distance": 0.749,
   "better_fit": [
    {
     "name": "Owen Perez",
     "distance": 0.281
    }
   ]
  },
  {
   "name": "Zara Alvarez",
   "day": 5,
   "partner": "Xenia Young",
   "partner_distance": 0.754,
   "better_fit": [
    {
     "name": "William Wright",
     "distance": 0.681
    }
   ]
  },
  {
   "name": "Felix Garcia",
   "day": 5,
   "partner": "Daniel Evans",
   "partner_distance": 0.947,
   "better_fit": [
    {
     "name": "Kevin Lee",
     "distance": 0.597
    }
   ]
  },
  {
   "name": "Zara Alvarez",
   "day": 6,
   "partner": "Xenia Young",
   "partner_distance": 0.754,
   "better_fit": [
    {
     "name": "William Wright",
     "distance": 0.681
    }
   ]
  },
  {
   "name": "Felix Garcia",
   "day": 6,
   "partner": "Daniel Evans",
   "partner_distance": 0.947,
   "better_fit": [
    {
     "name": "Kevin Lee",
     "distance": 0.597
    }
   ]
  }
 ]
}
```
