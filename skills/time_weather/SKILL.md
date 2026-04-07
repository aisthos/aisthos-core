---
name: Time & Weather
description: Tells time, date, weather and suggests activities based on conditions
version: 0.1.0
tags: [productivity, grows-with-you]
trigger: user_asks_time_or_weather
author: AisthOS Project
license: MIT
---

# Time & Weather

A skill that provides time/date/weather information and learns user preferences over time.

## Behavior

### Infant Stage (Day 0-3)
- "What time is it?" → Simple time response
- "What's the weather?" → Current conditions (requires internet or cached data)
- "What day is it?" → Date and day of week

### Child Stage (Week 1-2)
- Learns when user typically asks about weather (morning routine?)
- Tracks preferred temperature units (C/F)
- Notices patterns: "You usually check weather before leaving. It's 15°C and cloudy today."

### Teen Stage (Month 1-2)
- Proactively suggests: "Good morning! It's going to rain this afternoon, you might want an umbrella."
- Connects weather to user habits: "It's a nice evening — last time weather was like this, you went for a walk."

## Templates Used
```yaml
template: weather_check
fields:
  - time_of_day: enum [morning, afternoon, evening, night]
  - temperature: float
  - conditions: enum [sunny, cloudy, rainy, snowy, windy]
  - user_activity_after: string  # What user did after checking weather
```

## Filters
```yaml
filter: weather_routine
start: user_asks about weather OR time
  OR morning_greeting AND weather_skill_enabled
```

## Sparks Generated
```yaml
spark: weather_preference
fields:
  - check_time: datetime
  - conditions_at_check: string
  - user_action_after: string  # walked, stayed home, took umbrella
  - satisfaction: enum [positive, neutral, negative]
```

## System Prompt Addition
```
You can tell the user the current time and date.
Current time: {current_time}
Current date: {current_date}
If the user asks about weather, provide information based on their location.
Over time, learn when and why they ask about weather to provide proactive suggestions.
```

## Learning Loop
1. User asks about time/weather
2. Provide information
3. Track what user does next (Spark: weather_preference)
4. Track A (bandit): adjust detail level of weather responses
5. Track B (nightly): if pattern found → create proactive weather notification skill
