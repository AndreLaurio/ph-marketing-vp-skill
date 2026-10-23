# ph-marketing-vp — a Senior VP of Marketing for the Philippines, as a Claude Code skill

Describe your business (what you sell, where, website, Facebook page, budget, how many
hours you have) and get back a 90-day marketing roadmap written by someone who thinks
like a seasoned Filipino marketer: which Facebook groups to join and how to post in them
without getting kicked, which channels to bet on and which to skip for now, Taglish
posts ready to copy, a peso budget, KPIs and the compliance traps (DTI promo permits,
FDA, Data Privacy Act, Internet Transactions Act).

```
marketing-roadmap-lutong-bahay-pasig.md: 90-day plan
  Bottleneck: replies take 6+ hours; fix with saved replies + price list first
  Primary channel: 6 Pasig/Marikina community & WFH-mom Facebook groups
  Supporting: FB page + Messenger, Google Maps listing
  Budget: ₱5,000/mo (₱3,000 boosts on proven posts, ₱1,500 food samples, ₱500 tools)
  Target by day 90: 25-40 orders/week, 60% repeat, 50 Google reviews
  Tomorrow: 1) set Messenger saved replies 2) join 3 groups 3) photograph 10 dishes
```

## What it does

1. **Reads your brief** and asks only what is missing (max 4 questions).
2. **Audits what you have**: runs a one-page website audit (Messenger/Viber path,
   GCash/COD mentions, Meta Pixel, mobile, Google Maps link), looks up competitors.
3. **Decides like a VP**: one bottleneck, a positioning line, 1 primary + 1-2
   supporting channels, an offer timed to PH paydays and sale days, and explains *why*
   each call fits the Philippine market so you learn the strategy.
4. **Writes the roadmap** (`marketing-roadmap-<business>.md`): week-by-week tasks for
   days 1-30, milestones for 31-90, Facebook group plan, content pillars and drafts,
   Messenger saved replies, budget, KPIs, compliance checklist.

## Install

**As a Claude Code plugin (recommended)**

```
/plugin install ph-marketing-vp --marketplace AndreLaurio/ph-marketing-vp-skill
```

**Or copy the skill folder**

```bash
git clone https://github.com/AndreLaurio/ph-marketing-vp-skill
mkdir -p ~/.claude/skills
cp -r ph-marketing-vp-skill/skills/ph-marketing-vp ~/.claude/skills/
```

Then ask in plain language, e.g. *"I run a milk tea shop in Davao, FB page
facebook.com/xyz, ₱10k/month budget. Paano ko i-market?"*, or call
`/ph-marketing-vp` with your brief.

## Use the audit script without Claude

```bash
python3 skills/ph-marketing-vp/scripts/audit_site.py yourshop.ph
python3 skills/ph-marketing-vp/scripts/audit_site.py yourshop.ph competitor.ph --json
```

## Limits worth knowing

- It does not log into or scrape Facebook, Shopee or TikTok. It gives you the exact
  group search terms and vetting checklist; you join and post as a real person.
- Platform stats, ad costs and regulations change. The skill cites current figures when
  it looks them up and labels everything else as an assumption. The compliance notes are
  a checklist, not legal advice.
- Works best with the [lead-scraper](https://github.com/AndreLaurio/lead-scraper-skill)
  skill for B2B plans that need a prospect list.

## Repo layout

```
.claude-plugin/                   plugin + marketplace manifests
skills/ph-marketing-vp/
  SKILL.md                        the VP persona and workflow
  references/                     PH market, Facebook groups, channels, archetypes,
                                  calendar, Taglish copywriting, compliance, roadmap template
  scripts/audit_site.py           website audit for PH conversion and tracking basics
  evals/                          test cases runnable with `claude plugin eval`
```

## License

MIT
