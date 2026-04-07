---
name: Smart Greeting
description: Greets the user based on time of day and learned preferences
version: 0.1.0
tags: [core, grows-with-you]
trigger: user_interaction_start
author: AisthOS Project
license: MIT
---

# Smart Greeting

A skill that demonstrates the "grows with you" principle. Starts with simple time-based greetings, then adapts based on User Wisdom.

## Behavior

### Infant Stage (Day 0-3)
- Morning (6-12): "Good morning!"
- Afternoon (12-18): "Hello!"
- Evening (18-23): "Good evening!"
- Night (23-6): "Can't sleep?"

### Child Stage (Week 1-2)
- Learns preferred greeting style (formal/informal)
- Tracks mood patterns by time of day
- Suggests: "I noticed you're usually in a good mood in the morning. Want me to be more energetic then?"

### Teen Stage (Month 1-2)
- Creates personalized greetings based on accumulated Sparks
- References previous conversations: "Welcome back! Last time we were working on..."
- Adapts tone to detected emotion

## Templates Used
```yaml
template: greeting_context
fields:
  - time_of_day: enum [morning, afternoon, evening, night]
  - user_mood: enum [happy, neutral, tired, stressed]
  - last_interaction_gap: float  # hours since last interaction
```

## Filters
```yaml
filter: greeting_trigger
start: new_session OR interaction_gap > 2_hours
```

## Sparks Generated
```yaml
spark: greeting_reaction
fields:
  - greeting_style_used: string
  - user_response_sentiment: enum [positive, neutral, negative]
  - timestamp: datetime
```

## Learning Loop
1. Greet user with current best style
2. Observe reaction (Spark: greeting_reaction)
3. Track A (bandit): adjust greeting style weight
4. Track B (nightly): if pattern found → update greeting preferences in UW
