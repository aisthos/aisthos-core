# Open-Source Project Launch Tactics Research (2024-2026)

Research date: 2026-04-03

---

## TOPIC 1: Successful Open-Source Project Launches — Case Studies

### 1.1 Ollama

**Timeline:**
- Founded 2021 by Jeffrey Morgan & Michael Chiang (YC W21, Toronto)
- First public release: **July 2023** on GitHub
- Show HN post: **July 25, 2023** — title: "Show HN: Ollama -- Run LLMs on your Mac" (https://news.ycombinator.com/item?id=36802582)
- The hook: Docker-like UX for LLMs. Jeffrey Morgan came from the Docker project; the pitch was "something similar needed to exist for large language models"

**Growth numbers (ROSS Index / Runa Capital data):**
- Q1 2024: 28,900 stars, 3.6x growth
- Full year 2024: added +76,100 new stars (261% growth), reaching 105,100 total
- #1 on Runa Capital ROSS Index for 2024
- By March 2026: ~135,000+ stars
- Monthly downloads: 100K (Q1 2023) -> 52 million (Q1 2026) = **520x growth in 3 years**
- Raised only $0.5M from Essence, Rogue, Sunflower, Y Combinator

**What worked:**
- Docker analogy was immediately understood by devs
- "Run LLMs on your Mac" — simple, clear value prop in the title
- Timing: rode the post-Llama 2 wave (Meta released Llama 2 in July 2023)
- One-line install (`curl -fsSL https://ollama.com/install.sh | sh`)
- r/LocalLLaMA became a natural amplifier

**Sources:** [Runa Capital ROSS Index 2024](https://runacap.com/ross-index/annual-2024/), [Ollama Blog](https://ollama.com/blog/launch), [Show HN post](https://news.ycombinator.com/item?id=36802582), [YC page](https://www.ycombinator.com/companies/ollama)

---

### 1.2 Open-Sora (HPC-AI Tech / Colossal-AI)

**Timeline:**
- March 4, 2024: First announcement — "Sora Replication with 46% cost reduction"
- March 18, 2024: Open-Sora 1.0 full release — complete video generation pipeline
- April 25, 2024: v1.1 with Gradio demo on HuggingFace Spaces (2s-15s video, 144p-720p)
- June 17, 2024: v1.2 (3D-VAE, rectified flow)
- Current: 22,000+ stars

**What made it viral:**
- Name hijacking: "Open-Sora" directly referenced OpenAI's Sora (announced Feb 2024, not yet released)
- Timing: launched 6 weeks after OpenAI's Sora demo created massive demand
- Open-source alternative to a hyped closed product = instant attention
- Cost story: "2s 512x512 videos with only 3 days of training on 200 H800 GPU-days"
- Full pipeline: not just weights, but preprocessing + training + inference

**Sources:** [Open-Sora GitHub](https://github.com/hpcaitech/Open-Sora), [HPC-AI Tech Blog](https://company.hpc-ai.com/blog/open-sora-v1.0)

---

### 1.3 LocalAI

**Timeline:**
- Created by Ettore Di Giacinto, first released 2023
- May 2023: v1.8.0 (bert.cpp, transcriptions)
- December 2023: v2.0.0 (major backend overhaul)
- 2024 key features: Reranker API (Apr), Distributed P2P llama.cpp (May), P2P Dashboard (Jul/Aug), FLUX-1 + VAD (Nov)
- Current: ~30,000+ stars

**What worked:**
- OpenAI API-compatible interface = drop-in replacement
- "No GPU required" messaging
- Community-driven from the start
- Consistent feature shipping built trust

**Sources:** [LocalAI GitHub](https://github.com/mudler/LocalAI), [LocalAI docs](https://localai.io/basics/news/index.html)

---

### 1.4 Wire-Pod (Vector Robot)

**Timeline:**
- First released: **May 2022** by kercre123
- Grew steadily through 2023-2024
- Community members like fforchino (VectorX) and Zark75 contributed significantly
- Commercial services appeared (TechShop82 selling pre-configured servers)

**What worked:**
- Rescue narrative: "save your bricked robot from dead cloud servers"
- Pre-existing passionate community (Anki Vector owners)
- Practical urgency: Digital Dream Labs' cloud service was unreliable/shutting down
- Low barrier: worked on Raspberry Pi
- ChatGPT integration brought new users in 2023

**Community building:**
- Blog ecosystem (thedroidyouarelookingfor.info)
- YouTube tutorials
- Commercial ecosystem emerged (pre-configured servers for sale)
- LearnWithARobot newsletter covered it

**Sources:** [wire-pod GitHub](https://github.com/kercre123/wire-pod), [About wire-pod](https://www.learnwitharobot.com/p/about-wire-pod)

---

### 1.5 OpenMoxie

**Timeline:**
- December 30, 2024: Posted on GitHub by Beghtol (Embodied employee)
- Setup instructions sent to all Moxie robot owners
- Context: Embodied (the $800 children's robot company) was shutting down

**Growth pattern:**
- Initially VERY FEW people switched — low technical barrier was still too high for parents
- Breakthrough: A TikTok influencer's viral "goodbye to my robot" video was noticed by a community member, who convinced her to create a migration tutorial
- Community members like Adero Harrison (Florida mom) became evangelists
- Users turned robots into "whatever they want" — voice assistants, doorbells, custom companions

**What worked:**
- Emotional narrative: "save children's companion robot from corporate death"
- Influencer-driven tutorials (TikTok)
- Mom-to-mom support network

**What didn't work initially:**
- Pure GitHub release without tutorials was insufficient for non-technical parent audience

**Sources:** [Techdirt coverage](https://www.techdirt.com/2024/12/30/embodied-is-actually-trying-to-release-moxie-robots-to-the-open-source-community/), [PIRG article](https://pirg.org/articles/moxie-robot-open-source/)

---

### 1.6 PocketBase

**Timeline:**
- July 2022: "Show HN: PocketBase -- Open Source realtime backend in one file" (https://news.ycombinator.com/item?id=32013330)
- September 2022: Fireship YouTube video amplified reach dramatically
- November 2022: Creator went full-time on PocketBase for ~5 months
- December 2023: v0.20.0
- Current: 43,000+ stars

**What worked:**
- "Backend in 1 file" — irresistible simplicity hook
- Single Go binary = instant deployment
- Fireship video = massive YouTube amplifier
- Firebase/Supabase alternative positioning
- Creator went full-time = signal of commitment

**Sources:** [Show HN post](https://news.ycombinator.com/item?id=32013330), [PocketBase](https://pocketbase.io/)

---

### 1.7 Hono

**Timeline:**
- December 2021: Created by Yusuke Wada (Japan)
- 2023: Wada hired by Cloudflare (part of work time on Hono)
- Reached 25,000 stars (announced on X)
- Current: 20K+ stars, 400K+ weekly npm downloads

**What worked:**
- "Web framework built on Web Standards" = universal runtime story
- Edge-first positioning (Cloudflare Workers, Deno, Bun, Node.js)
- Cloudflare hiring the creator = legitimacy signal
- Ultrafast benchmarks = shareable content

**Sources:** [Hono GitHub](https://github.com/honojs/hono), [Hono.dev](https://hono.dev/)

---

### 1.8 Bun

**Timeline:**
- September 8-9, 2023: Bun 1.0 launch
- Multiple HN posts in the same week (v1.0, v1.0.0, announcement video)

**First week adoption:**
- Vercel added Bun install support
- Replit added Bun support
- Ruby on Rails added Bun support
- Laravel began installing Bun by default
- ~400 bugs filed in first week (showing massive adoption)

**What worked:**
- Speed benchmarks = instantly shareable
- Drop-in Node.js replacement positioning
- Major framework integrations in week 1 = credibility cascade

**Sources:** [Bun v1 HN](https://news.ycombinator.com/item?id=37424724), [Bun Blog](https://bun.com/blog)

---

### 1.9 AFFiNE (Notion + Miro alternative)

**Timeline:**
- August 2022: First launch on GitHub
- **43 days: 0 -> 10,000 stars** (claimed fastest GitHub growth record at that time)
- **18 months: 0 -> 33,000 stars**
- October 2023: $8M Series Pre-A, ~$40M valuation

**Strategy:**
- Product Hunt: achieved #1 **thirty times**
- Dedicated growth team (Iris, former COO, documented the entire playbook)
- Systematic platform-by-platform strategy: V2EX, HN, Reddit, Product Hunt
- First 100 stars from personal network
- Cross 1,000 star threshold as fast as possible

**Sources:** [AFFiNE funding PR](https://www.prnewswire.com/news-releases/all-in-one-collaboration-tool-affine-fastest-growth-ever-in-github-history-raises-8m-funding-round-301957261.html), [33K Stars Case Study on DEV](https://dev.to/iris1031/how-to-get-more-github-stars-the-definitive-guide-33k-stars-case-study-2kjo)

---

### 1.10 Signal

**Adoption numbers:**
- ~70 million active users
- 220+ million total downloads
- Protocol adopted by WhatsApp, Facebook Messenger, Skype, Google Messages (1 billion+ conversations encrypted)
- Non-profit model (Signal Foundation, co-founded 2018 by Moxie Marlinspike + Brian Acton)

**What worked:**
- Protocol-first strategy: licensed protocol to WhatsApp/Facebook = massive reach
- Privacy as primary value prop
- Non-profit = trust signal
- Major download spikes during privacy scandals (WhatsApp policy changes, political events)

**Sources:** [Signal docs](https://signal.org/docs/), [Signal Wikipedia](https://en.wikipedia.org/wiki/Signal_(software))

---

## TOPIC 2: Reddit Communities — Launch Tactics

### 2.1 r/LocalLLaMA (671K members)

**What gets upvoted:**
- Technical project announcements with benchmarks (e.g., "ZINC -- LLM inference engine written in Zig, running 35B models on $550 AMD GPUs" — 79 engagement units)
- AI research analysis posts
- Solution requests and deployment advice

**Self-promotion rules:**
- Self-promotion allowed, but must be <10% of your total content in the sub
- Lead with technical substance, not marketing
- Demo video/GIF is critical
- First comment should: identify yourself as author, ask for feedback, describe technical details
- Write title matching subreddit style (technical, simple)

### 2.2 r/selfhosted (large, high activity)

**What works:**
- Open-source preferred (this is table stakes)
- Docker images and easy deployment
- Privacy-first, no telemetry, no mandatory accounts
- Detailed setups and configurations
- Share before you sell

**Self-promotion policy:**
- Allowed in context, promotional posts may be removed
- Moderators are lenient with genuinely helpful content even if it technically violates Rule #1
- Red flags: telemetry, mandatory cloud accounts, data dependencies
- Transparency about data handling is critical

### 2.3 r/privacy

- Very strict about commercial promotion
- Must be genuinely privacy-focused, not privacy-washing
- Open-source is almost a requirement
- Technical audits and transparency reports help
- Best approach: post about the privacy problem you solve, not your product

### 2.4 r/MachineLearning

- Academic/research focus
- Project announcements should include technical details, paper references
- "What is wrong with X" and benchmarking posts do well
- Self-promotion should be accompanied by substantive technical content

### 2.5 r/homeassistant

- Best to first post on the official Home Assistant Community forums (community.home-assistant.io)
- Reddit posts should reference working HACS integration
- Video demos of working integration are highly valued
- "Project Release" format with clear feature description works (see C.A.F.E. project example)

### 2.6 r/embedded

- Code-heavy content resonates
- Show the hardware, show the wiring, show the output
- ESP32 projects are popular
- "I built X with Y" format works well
- Technical deep-dives get more engagement than product announcements

### 2.7 Cross-posting across subreddits

- Disclose crossposting (include "x-post" in title)
- Tailor message for each community's culture
- Relevant subreddits for projects: r/reactjs, r/javascript, r/webdev, r/selfhosted, r/SideProject, r/InternetIsBeautiful
- Each sub has different norms — adapt language accordingly

**Sources:** [r/LocalLLaMA analysis](https://gummysearch.com/r/LocalLLaMA/), [r/selfhosted analysis](https://gummysearch.com/r/selfhosted/), [Reddit self-promotion guide](https://karmaguy.io/en/blog/reddit-self-promotion-rules)

---

## TOPIC 3: Hacker News Show HN — 2025-2026 Patterns

### 3.1 Show HN Growth Stats

- Show HN posts grew from ~1,000/month (Jan 2023) to 3,500/month (Dec 2025) to 6,200/month (Feb 2026)
- Share of Show HN stories tripled: 3.6% -> nearly 13% of all HN stories
- Growth accelerated after Claude Code, Opus 4.6, GPT-5.4 releases

### 3.2 Research Data: Launch-Day Diffusion Paper (arXiv, Nov 2025)

Analyzed **138 repository launches** from 2024-2025:
- **Average star gain: +121 stars within 24 hours of HN exposure**
- **+189 stars within 48 hours**
- **+289 stars within one week**
- **Posting hour is the dominant predictive factor** (even after controlling for project quality)
- **"Show HN" tag shows NO statistical advantage after controlling for other factors** — the content matters more than the tag

### 3.3 Optimal Posting Time

**Conventional wisdom:** Tuesday-Thursday, 8-10 AM PT

**2025 data challenge (Myriade analysis of 157,000+ Show HN posts since 2009):**
- **Weekend posts actually performed BETTER** than weekday posts
- **Best day: Sunday**
- **Best time: 11 AM - 12 PM (likely ET or PT)**
- Theory: less competition on weekends = longer time on front page

**Practical recommendation:**
- If risk-averse: Tuesday-Thursday, 8-10 AM PT (more data supporting this)
- If contrarian: Sunday 11 AM PT (less competition, longer front page time)

### 3.4 Successful Show HN Title Patterns

**What worked (high upvotes):**
- "I made an open-source laptop from scratch"
- "I 3D scanned the interior of the Great Pyramid at Giza"
- "I got laid off from Meta and created a minor hit on Steam"
- "I spent 3 years reverse-engineering a 40 yo stock market sim from 1986"
- "LocalGPT -- A local-first AI assistant in Rust with persistent memory"
- "Llama 3.1 70B on a single RTX 3090"
- "ZINC -- LLM inference engine written in Zig, running 35B models on $550 AMD GPUs"

**Pattern:** Personal story + specific technical detail + surprising constraint/achievement

**What HN crowd overindexes on:**
- Open-source
- Privacy-first
- Running locally / on unusual hardware
- Solo dev achievements
- Reverse engineering / resurrection projects

### 3.5 Demo vs README

- Link to GitHub repo = dev-audience signal (easy to run, working product, open source)
- GitHub README is minimum viable demo for HN
- Live demo / Gradio space / hosted version improves engagement significantly
- Video/GIF demos are shared more widely
- Best: GitHub + live demo + blog post explaining "how I built this"

### 3.6 What Causes Show HN Flops

- Posting at wrong time (night/early morning US)
- No founder comment within first 5 minutes
- Overly promotional language ("revolutionary", "game-changing")
- No working code / vapor-ware
- Closed-source or unclear licensing
- No clear differentiation from existing solutions
- README that reads like marketing copy instead of technical docs

**Sources:** [Launch-Day Diffusion paper](https://arxiv.org/abs/2511.04453), [Myriade Show HN timing analysis](https://www.myriade.ai/blogs/when-is-it-the-best-time-to-post-on-show-hn), [bestofshowhn.com](https://bestofshowhn.com/), [HN launch guide](https://dev.to/dfarrell/how-to-crush-your-hacker-news-launch-10jk)

---

## TOPIC 4: Cross-Posting Strategy

### 4.1 Recommended Sequence (Staggered, NOT simultaneous)

Based on multiple sources including the daily.dev launch guide:

1. **T+0 min: Hacker News** (Show HN post) — this is your anchor
2. **T+5 min: Add founder comment** on HN (context, technical details, ask for feedback)
3. **T+30 min: Reddit** (r/selfhosted, r/LocalLLaMA, or relevant sub)
4. **T+30 min: Twitter/X thread** (hook + problem + solution + demo GIF + CTA)
5. **T+1 day: dev.to / Hashnode** ("How I built X" article)
6. **T+2-3 days: Product Hunt** (if relevant)
7. **T+1 week: YouTube** (demo video or technical deep-dive)

### 4.2 Why Stagger

- Manage feedback without being overwhelmed
- Each platform amplifies the others (HN front page -> Reddit references -> Twitter shares)
- Avoid "spam" perception from simultaneous posts
- Fresh content for each platform keeps the story alive across days

### 4.3 Anti-Spam Practices

- **Different messaging per platform** (technical for HN, visual for Twitter, practical for r/selfhosted)
- **Be genuine community member first** (Reddit 10% rule: only 10% of activity should be self-promotion)
- **Respond to every comment** in the first 2 hours
- **Never use identical text** across platforms
- **Disclose authorship** naturally ("I built this because...")

### 4.4 The Usertour Case Study (Feb 2025)

- Founder Eason shared progress on r/selfhosted and r/webdev BEFORE the Show HN post
- Then posted Show HN on Hacker News
- Result: **1,200+ GitHub stars within 3 months**
- Key: building community presence BEFORE the launch, not during

**Sources:** [daily.dev launch guide](https://business.daily.dev/resources/promote-open-source-project-step-by-step-launch-guide/), [Reddit cross-posting guide](https://www.postpone.app/blog/crossposting-reddit), [Indie Hackers launch guide](https://www.indiehackers.com/post/how-to-launch-on-reddit-hn-in-2022-20k-visitors-70-sales-6b30437cf7)

---

## TOPIC 5: "Launch Week" Concept

### 5.1 Supabase — The Pioneer

- Invented the concept in **March 2021** with the question: "Why can't we ship one major feature every day for a week?"
- Format: 5 days, one major announcement per day at 8 AM PT
- Each day has: blog post + tweet thread + demo video
- Parallel hackathon: 10-day build challenge with prizes ($1,500 in GitHub sponsorships)
- Run quarterly (15 launch weeks by mid-2025)

**Typical daily content structure:**
- Day 1: New core feature (biggest announcement)
- Day 2: Developer experience improvement
- Day 3: Integration / partnership announcement
- Day 4: Community / open-source tooling
- Day 5: Platform/infrastructure update + recap

### 5.2 Industry Adoption

**launchweek.dev stats (2024):**
- **94 different companies** ran launch weeks in 2024
- Only 7 companies (7.4%) ran 3+ launch weeks per year
- Most active: Highlight, Daytona, Memfault, Mux, Outerbase, Supabase, Wasp
- April 2025: Supabase, Astro, Wasp, and 14+ others launching

**The format works for:**
- Solo makers
- Early-stage startups
- Late-stage companies
- ANY company shipping features regularly

### 5.3 What Makes Launch Weeks Work

- **Sustained attention** across 5 days vs. single-day spike
- **Daily HN/Reddit posts** without spam perception (each day is genuinely new content)
- **Community building**: hackathon creates user-generated content
- **Content cascade**: blog post + tweet + video + demo = 4 pieces per day = 20 pieces per week
- **FOMO effect**: "what's shipping tomorrow?" keeps audience returning

### 5.4 Practical Template for Small Projects

For a project like MeowBot, a modified "Launch Week" could be:

- **Day 1 (Monday):** Show HN — "Open-source AI companion robot brain" + core demo
- **Day 2 (Tuesday):** r/LocalLLaMA — "Running Ollama on a companion robot with emotion recognition"
- **Day 3 (Wednesday):** r/selfhosted — "Self-hosted AI pet: no cloud, your data stays home"
- **Day 4 (Thursday):** r/homeassistant — "MeowBot + Home Assistant: your AI cat controls your smart home"
- **Day 5 (Friday):** dev.to — "How I built an AI companion robot with ESP32 + Mac Mini" (technical deep-dive)

Each day targets a different community with tailored messaging while the GitHub star count compounds.

**Sources:** [Supabase Launch Week](https://supabase.com/launch-week), [launchweek.dev 2024 Wrapped](https://launchweek.dev/lw/2024/wrapped), [How we launch at Supabase](https://www.producthunt.com/stories/how-we-launch-at-supabase)

---

## KEY METRICS & BENCHMARKS

| Metric | Target | Source |
|--------|--------|--------|
| Stars in first 24h from HN | ~121 average | Launch-Day Diffusion paper |
| Stars in first week from HN | ~289 average | Launch-Day Diffusion paper |
| First 100 stars | From personal network | AFFiNE playbook |
| First 1,000 stars | "As fast as possible" — critical threshold | AFFiNE playbook |
| Monetization threshold | 500-2,000 stars | Clarm guide |
| 30-day targets | 1,000+ installs, 300+ weekly active users | daily.dev guide |
| Product-market fit signal | Hit 2/3: usage, contributions, community | daily.dev guide |

---

## TOP 2024 ROSS INDEX (GitHub Star Growth)

| Rank | Project | Total Stars | New Stars 2024 | Growth % |
|------|---------|-------------|----------------|----------|
| 1 | Ollama | 105.1K | +76.1K | 261% |
| 2 | Zed Industries | 52.1K | +52.1K | new |
| 3 | Langgenius (Dify) | 56.7K | +43.4K | — |
| 4 | ComfyUI | 61.9K | +40.9K | — |

---

## ACTIONABLE CHECKLIST FOR MEOWBOT LAUNCH

### Pre-Launch (2-4 weeks before)
- [ ] Build karma in r/LocalLLaMA, r/selfhosted, r/homeassistant (comment, help, share)
- [ ] Create polished README with GIF demo, one-line install, architecture diagram
- [ ] Record 60-second demo video
- [ ] Set up live demo (Gradio space or hosted instance)
- [ ] Write "How I built MeowBot" blog post draft for dev.to
- [ ] Prepare different messaging for each platform

### Launch Day
- [ ] Post Show HN at 8-10 AM PT on Tuesday-Thursday (OR Sunday 11 AM PT for less competition)
- [ ] Add founder comment within 5 minutes
- [ ] Post on r/LocalLLaMA 30 minutes later (technical angle)
- [ ] Tweet thread with demo GIF
- [ ] Monitor and respond to EVERY comment for first 2 hours

### Launch Week (Days 2-5)
- [ ] Day 2: r/selfhosted (privacy angle)
- [ ] Day 3: r/homeassistant (integration angle)
- [ ] Day 4: dev.to article
- [ ] Day 5: r/embedded or r/esp32 (hardware angle)

### Post-Launch (Week 2-4)
- [ ] Submit to awesome-selfhosted list
- [ ] Product Hunt launch
- [ ] YouTube technical demo
- [ ] Follow up with anyone who engaged
