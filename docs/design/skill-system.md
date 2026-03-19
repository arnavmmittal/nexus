# Nexus Skill & Gamification System

## Overview

Every skill you develop - whether coding in Python or perfecting a recipe - gets tracked, leveled, and visualized. This creates a unified view of your growth as a person.

---

## Skill Categories

### Technical (Auto-tracked from Claude sessions)
```
Programming
├── Python          [████████░░] Lv.8
├── JavaScript      [██████░░░░] Lv.6
├── SQL             [████░░░░░░] Lv.4
└── Rust            [█░░░░░░░░░] Lv.1

AI & ML
├── Prompt Engineering  [███████░░░] Lv.7
├── LLM APIs           [████████░░] Lv.8
└── ML Fundamentals    [███░░░░░░░] Lv.3

DevOps & Tools
├── Git             [███████░░░] Lv.7
├── Docker          [████░░░░░░] Lv.4
└── AWS             [███░░░░░░░] Lv.3
```

### Fitness & Sports (Manual + Apple Health)
```
Strength
├── Bench Press     [██████░░░░] 185 lbs
├── Squat           [█████░░░░░] 225 lbs
├── Deadlift        [██████░░░░] 275 lbs
└── Pull-ups        [████░░░░░░] 12 reps

Cardio
├── Running         [████░░░░░░] 5K: 28min
├── Jump Rope       [███░░░░░░░] 5 min continuous
└── HIIT            [████░░░░░░] Lv.4

Sports
├── Basketball      [███░░░░░░░] Lv.3
└── Swimming        [██░░░░░░░░] Lv.2
```

### Social & Communication
```
Speaking
├── Public Speaking    [███░░░░░░░] Lv.3
├── Storytelling       [████░░░░░░] Lv.4
└── Debate             [██░░░░░░░░] Lv.2

Interpersonal
├── Networking         [████░░░░░░] Lv.4
├── Negotiation        [███░░░░░░░] Lv.3
├── Leadership         [███░░░░░░░] Lv.3
└── Active Listening   [█████░░░░░] Lv.5
```

### Business & Finance
```
Investing
├── Stock Analysis     [████░░░░░░] Lv.4
├── Options            [██░░░░░░░░] Lv.2
├── Crypto             [███░░░░░░░] Lv.3
└── Real Estate        [█░░░░░░░░░] Lv.1

Business
├── Sales              [███░░░░░░░] Lv.3
├── Marketing          [████░░░░░░] Lv.4
├── Content Creation   [█████░░░░░] Lv.5
└── Product Management [██░░░░░░░░] Lv.2
```

### Cooking
```
Techniques
├── Knife Skills       [████░░░░░░] Lv.4
├── Sautéing           [█████░░░░░] Lv.5
├── Baking             [██░░░░░░░░] Lv.2
└── Grilling           [████░░░░░░] Lv.4

Cuisines
├── Italian            [████░░░░░░] Lv.4
├── Mexican            [███░░░░░░░] Lv.3
├── Indian             [██░░░░░░░░] Lv.2
└── Japanese           [██░░░░░░░░] Lv.2
```

---

## XP & Leveling System

### XP Sources

| Source | XP Earned | Example |
|--------|-----------|---------|
| Claude Session | 10-100 XP | Working on Python project = +50 Python XP |
| Manual Log | 5-50 XP | "Practiced piano for 30 min" = +20 Music XP |
| Completed Project | 100-500 XP | Shipped YouTube automation = +200 Python XP |
| Integration | Auto | Gym check-in via Apple Health = +10 Strength XP |
| Achievement | Bonus | "First Pull Request" = +100 Git XP |

### Leveling Formula

```
XP required for level N = 100 * (N ^ 1.5)

Level 1:  100 XP
Level 2:  283 XP
Level 3:  520 XP
Level 5:  1,118 XP
Level 10: 3,162 XP
Level 20: 8,944 XP
Level 50: 35,355 XP
```

This creates a curve where early levels come fast (motivation) but mastery takes real commitment.

### Skill Tiers

| Tier | Levels | Title |
|------|--------|-------|
| Novice | 1-5 | Just starting out |
| Apprentice | 6-15 | Building foundations |
| Journeyman | 16-30 | Competent practitioner |
| Expert | 31-50 | Deep knowledge |
| Master | 51-75 | Top 1% |
| Grandmaster | 76-100 | World-class |

---

## Auto-Detection from Claude Sessions

When you work with Claude, Nexus analyzes the conversation:

```python
def analyze_claude_session(session: ClaudeSession) -> list[SkillXP]:
    xp_awards = []

    # Detect languages/frameworks used
    if "python" in session.code_blocks:
        xp_awards.append(SkillXP("Python", estimate_complexity(session)))

    # Detect learning (questions asked, concepts explored)
    concepts = extract_concepts(session)
    for concept in concepts:
        skill = map_concept_to_skill(concept)
        xp_awards.append(SkillXP(skill, 10))

    # Detect problem-solving (errors fixed, debugging)
    if session.had_errors_fixed:
        xp_awards.append(SkillXP("Debugging", 20))

    # Detect completion (working code at end)
    if session.produced_working_code:
        xp_awards.append(SkillXP(primary_skill, 50))

    return xp_awards
```

### Example Detection

```
Session: "Building YouTube automation with Python"
Duration: 45 minutes
Code written: 500 lines

Detected XP:
├── Python           +75 XP (primary language, significant code)
├── FFmpeg           +30 XP (learned video processing)
├── Async/Await      +20 XP (used asyncio)
├── API Integration  +25 XP (Claude API, edge-tts)
└── Project Delivery +100 XP (completed working system)

Total: +250 XP across 5 skills
```

---

## Achievements System

### Categories

**First Milestones**
- 🎯 First Blood - Complete your first skill session
- 💻 Hello World - Write your first program
- 🏋️ Day One - Log your first workout
- 📚 Scholar - Complete your first learning session

**Streaks**
- 🔥 On Fire - 7-day streak in any skill
- ⚡ Unstoppable - 30-day streak
- 💎 Diamond Hands - 100-day streak
- 🌟 Legendary - 365-day streak

**Mastery**
- 🥉 Bronze - Reach level 10 in any skill
- 🥈 Silver - Reach level 25 in any skill
- 🥇 Gold - Reach level 50 in any skill
- 💜 Grandmaster - Reach level 75 in any skill

**Polymathy**
- 🎨 Renaissance - Level 10+ in 5 different categories
- 🧠 Polymath - Level 25+ in 3 different categories
- 🦄 Unicorn - Level 50+ in both technical and physical skills

**Special**
- 🚀 Shipped It - Complete and deploy a project
- 💰 First Dollar - Earn money from a skill
- 🎓 Teacher - Help someone else learn (detected from Claude sessions)
- 🌙 Night Owl - Practice at 3am
- ☀️ Early Bird - Practice before 6am

---

## Visual Design

### Skill Card Component

```
┌─────────────────────────────────────────────────┐
│  ⚡ Python                           Lv. 8      │
│  ─────────────────────────────────────────────  │
│  [████████████████████░░░░░░░░░░] 2,450 / 3,162 │
│                                                 │
│  🔥 12-day streak    📈 +450 XP this week       │
│                                                 │
│  Recent: YouTube automation, TikTok automation  │
└─────────────────────────────────────────────────┘
```

### Radar Chart (Overall Profile)

```
              Technical
                  ▲
                 /│\
                / │ \
               /  │  \
              /   │   \
   Creative ◄─────┼─────► Business
              \   │   /
               \  │  /
                \ │ /
                 \│/
                  ▼
              Physical
```

### XP History Graph

```
XP Earned (Last 30 Days)
│
│    ╭─╮
│   ╭╯ ╰╮    ╭──╮
│  ╭╯   ╰╮  ╭╯  ╰─╮
│ ╭╯     ╰──╯     ╰─╮
│─╯                  ╰───
└────────────────────────────
  Week 1   Week 2   Week 3   Week 4
```

---

## Integration Points

### Apple Health (Fitness)
- Workouts → Strength/Cardio XP
- Steps → Activity XP
- Sleep → Recovery tracking (affects energy patterns)

### GitHub (Coding)
- Commits → Language XP
- PRs merged → Project delivery XP
- New repos → Initiative XP

### Claude Sessions (Learning)
- Auto-detected from local files
- Parsed for skills, concepts, completions

### Manual Logging
- Quick log: "Cooked pasta carbonara" → +15 Italian Cuisine XP
- Structured log: Gym session with sets/reps

---

*Last updated: 2026-03-19*
