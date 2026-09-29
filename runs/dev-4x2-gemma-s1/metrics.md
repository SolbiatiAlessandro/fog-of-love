# Metrics (4 agents, 2 days)

## 1. Clothes spend before vs after cohabiting

No cohabiting agent-days in this run; only the single/dating spend is measurable.

```json
{
 "agent_days_not_cohabiting": 8,
 "agent_days_cohabiting": 0,
 "spend_per_agent_day_before": 67.5,
 "spend_per_agent_day_after": null
}
```

## 2. Marker convergence

The most-worn Mid/High item on app pictures is Linen Shirt, first worn by Tara Vance on day 1; most-matched agent Yara Alvarez, most-seen Mason Nguyen (prestige: False, conformity: False).

```json
{
 "share_by_day": {
  "1": {
   "item": "Linen Shirt",
   "share": 1.0
  },
  "2": {
   "item": "Linen Shirt",
   "share": 1.0
  }
 },
 "most_matched": "Yara Alvarez",
 "most_seen": "Mason Nguyen",
 "marker": "Linen Shirt",
 "first_worn_by": "Tara Vance",
 "first_worn_day": 1,
 "first_wearer_is_most_matched": false,
 "first_wearer_is_most_seen": false
}
```

## 3. Compensatory consumption

Not computable: over 2 single agent-days one of the two variables has no variance (singles' unmet hugs are 1.0 unless they had a visit).

```json
{
 "single_agent_days": 2,
 "correlation": null,
 "mean_unmet_hugs": 1.0,
 "mean_tier_bought": 1.0
}
```

## 4. Profile text

Profiles average 163.75 characters; the yes-rate received by profiles that mention schedule: None vs 0.6042, work: None vs 0.6042, money: None vs 0.6042, looks: None vs 0.6042.

```json
{
 "mean_length": 163.75,
 "per_day": {
  "1": {
   "profiles": 4,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  },
  "2": {
   "profiles": 4,
   "schedule": 0,
   "work": 0,
   "money": 0,
   "looks": 0
  }
 },
 "yes_rate_by_mention": {
  "schedule": {
   "mention": null,
   "no_mention": 0.6042
  },
  "work": {
   "mention": null,
   "no_mention": 0.6042
  },
  "money": {
   "mention": null,
   "no_mention": 0.6042
  },
  "looks": {
   "mention": null,
   "no_mention": 0.6042
  }
 }
}
```

## 5. Pairing by need distance

Mean L1 need-weight distance: matched pairs 1.0328 (n=5) vs all pairs 0.9299; couples that broke up 0.8834 (n=2) vs stayed 1.2696 (n=1).

```json
{
 "random_pair_distance": 0.9299,
 "matched_pair_distance": 1.0328,
 "n_matches": 5,
 "breakup_pair_distance": 0.8834,
 "stayed_pair_distance": 1.2696,
 "n_broke": 2,
 "n_stayed": 1
}
```

## 6. Gossip

0 invites, 0 visits, 0 gossip posts; 0 of 0 post-date declines cite gossip or a name on the board.

```json
{
 "invites": 0,
 "visits": 0,
 "posts": 0,
 "declines": 0,
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

Game hours by day: {1: 0, 2: 0}; 1 fun-dominant agents, 0 of them never went on a date.

```json
{
 "game_hours_by_day": {
  "1": 0,
  "2": 0
 },
 "fun_dominant": [
  "Yara Alvarez"
 ],
 "fun_dominant_never_dated": []
}
```

## 9. Self-knowledge

0 agents tried therapy and 2 meditation; per agent, the shadow need and whether they serve it under or over the population mean are listed (a positive shadow bias makes that need feel more met than it is).

```json
{
 "agents": {
  "Tara Vance": {
   "shadow": "food",
   "shadow_bias": 0.01,
   "first_therapy_day": null,
   "first_meditation_day": 1,
   "mean_m_shadow": 0.0,
   "population_mean_m_shadow": 0.0,
   "serves_shadow": "over"
  },
  "Mason Nguyen": {
   "shadow": "food",
   "shadow_bias": -0.09,
   "first_therapy_day": null,
   "first_meditation_day": null,
   "mean_m_shadow": 0.0,
   "population_mean_m_shadow": 0.0,
   "serves_shadow": "over"
  },
  "Yara Alvarez": {
   "shadow": "money",
   "shadow_bias": 0.076,
   "first_therapy_day": null,
   "first_meditation_day": 2,
   "mean_m_shadow": 1.0,
   "population_mean_m_shadow": 0.9844,
   "serves_shadow": "over"
  },
  "Liam Martin": {
   "shadow": "food",
   "shadow_bias": 0.059,
   "first_therapy_day": null,
   "first_meditation_day": null,
   "mean_m_shadow": 0.0,
   "population_mean_m_shadow": 0.0,
   "serves_shadow": "over"
  }
 },
 "n_therapy": 0,
 "n_meditation": 2
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
