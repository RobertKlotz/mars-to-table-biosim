# Mars to Table Challenge - Project Checkpoint

**Last Updated:** February 3, 2026
**Team:** Bueché-Labs LLC
**Repository:** https://github.com/RobertKlotz/mars-to-table-biosim

---

## Current Status: AWAITING ABSTRACT APPROVAL

We have submitted our registration and Preliminary Concept Abstract. Awaiting approval from challenge administrators before proceeding to final deliverable preparation.

---

## Challenge Timeline

| Date | Milestone | Status |
|------|-----------|--------|
| Jan 12, 2026 | Challenge Opens | ✅ Complete |
| **Now** | Registration + Abstract Submitted | ⏳ **AWAITING RESPONSE** |
| May 22, 2026 | Solution Summary Due | 📄 Draft Ready |
| July 31, 2026 | Registration Closes | — |
| Aug 14, 2026 | Final Submission Deadline | — |
| Aug 26, 2026 | Top Teams Notified for Q&A | — |
| Aug 31 - Sep 4, 2026 | Judging Panel Q&A Sessions | — |
| Sep 2026 | Winners Announced | — |

---

## Deliverables Status

### Ready Now (Pre-Approval)

| Deliverable | File | Status | Notes |
|-------------|------|--------|-------|
| **Solution Summary v4** | `docs/Mars_to_Table_Solution_Summary_v4.docx` | ✅ Complete | Aggressive opening addressing livestock head-on. Ready for May 22 deadline. Export to PDF before submission. |
| **Python Simulation** | `mars_to_table/` | ✅ Complete | 170 tests passing. BioSim compatible. 15 PODs, 90% Earth-independence. |

### Draft Ready (Awaiting Official Templates)

| Deliverable | File | Status | Notes |
|-------------|------|--------|-------|
| **14-Sol Meal Plan v3** | `docs/Mars_to_Table_14Sol_Meal_Plan_v3.xlsx` | ⚠️ Draft | Content complete. Will transfer to official template after approval. |
| **Concept of Operations v2** | `docs/Mars_to_Table_ConOps_v2.docx` | ⚠️ Draft | Content complete as Word doc. **Must convert to slide deck format per rules.** |
| **Design Layout v4** | `docs/Mars_to_Table_Design_Layout_v4.docx` | ⚠️ Draft | Content complete. **Needs visual diagrams/CAD/illustrations added.** |

### Not Started (Post-Approval)

| Deliverable | Status | Notes |
|-------------|--------|-------|
| **Walkthrough Video** | ❌ Not Started | ≤10 min, YouTube/Vimeo. 15% of score (150 points). Requires visuals from Design Layout. |

---

## Key Technical Specs

| Specification | Value |
|---------------|-------|
| POD Count | 15 |
| Earth-Independence | 90% (40 points above 50% requirement) |
| Protein Sources | 6 (eggs, milk, cheese, fish, tempeh, meat) |
| Daily Calories In-Situ | 40,975 kcal |
| Crew Size | 15 |
| Mission Duration | 500+ sols |
| Test Coverage | 170 tests passing |
| Power Budget | 385 kW |

---

## Strategic Positioning

### Our Differentiator
We address the livestock "weakness" head-on in our opening. Key argument:

> "Hydroponics alone will not sustain a Mars settlement... NASA is not asking how to keep astronauts alive. They are asking how to build a civilization. This is our answer."

### Mass Argument
- **25 kg** of embryos/seeds produces **40,000+ kcal/day indefinitely**
- Same mass in prepackaged food lasts **~12 days**
- All technology exists TODAY (frozen embryos routine since 1980s)

### Morale Argument
- Real food (eggs, bread, cheese, fish) maintains crew psychological health
- Antarctic/submarine research proves food monotony breaks crews
- This is not complexity for its own sake—it's mission-critical

---

## Next Steps After Approval

1. **Receive official templates** from challenge administrators
2. **Convert ConOps to slide deck** format with appendix
3. **Add visual diagrams** to Design Layout (CAD/illustration)
4. **Transfer Meal Plan** to official template
5. **Create walkthrough video** (≤10 min)
6. **Export Solution Summary to PDF** (Arial 11pt, 5+1 pages)
7. **Final review** against scoring rubric (Appendix C of rules)

---

## File Structure

```
mars-to-table-biosim/
├── docs/
│   ├── Mars_to_Table_Solution_Summary_v4.docx    # Main submission doc
│   ├── Mars_to_Table_ConOps_v2.docx              # Convert to slides
│   ├── Mars_to_Table_Design_Layout_v4.docx       # Add visuals
│   └── Mars_to_Table_14Sol_Meal_Plan_v3.xlsx     # Transfer to template
├── mars_to_table/                                 # Python simulation
│   ├── core/                                      # Store, Module, Simulation
│   ├── systems/                                   # All POD systems
│   ├── crew/                                      # Crew modeling
│   ├── simulation/                                # Events, stress tests
│   ├── biosim/                                    # BioSim integration
│   └── tests/                                     # 170 tests
├── CHECKPOINT.md                                  # THIS FILE
├── HANDOFF_TO_CODE_TAB.md                        # Original project handoff
└── README.md                                      # Project overview
```

---

## Scoring Reference (1,000 points total)

| Category | Weight | Our Strength |
|----------|--------|--------------|
| Overall (Form/Fit/STD-3001) | 200 | Strong - 15 PODs, 90% independence |
| Operational Protocols | 300 | Good - 4 phases, HACCP, crew roles |
| Design/Feasibility | 200 | Good - needs visuals |
| Meal Plan/Nutrition | 150 | Strong - 6 proteins, variety |
| Communications/Presentation | 150 | **TBD - Video not done** |

---

## Contact / Resources

- **Challenge Website:** https://deepspacefood.org
- **BioSim Repository:** https://github.com/scottbell/biosim
- **NASA STD-3001:** Referenced in docs
- **Rules Document:** `FNL_Mars to Table Challenge Rules_V2.pdf` (in Downloads)

---

## Session Notes

**February 3, 2026 Session Summary:**
- Updated all documentation from v3.1 to v4 to reflect simulation additions
- Added Aquaponics POD and Food Processing POD (13 → 15 PODs)
- Updated Earth-independence from 84% to 90%
- Rewrote Solution Summary abstract with aggressive opening
- Committed all changes to GitHub
- Identified remaining deliverables needed after approval

**Key Decision:** Swing for the fences on morale argument. Livestock is our differentiator, not our weakness.

---

*This checkpoint document should be updated after each working session.*
