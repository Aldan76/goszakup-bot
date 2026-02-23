# Expert Feedback Framework — Conflicting Norms System

**Phase 2-4 Completion Feedback Collection Plan**
**Date:** 2026-02-24
**Status:** 🚀 Ready to Deploy

---

## Overview

This document outlines the framework for collecting expert feedback on the conflicting norms detection system from государственные закупки specialists. The system has now detected 5 types of conflicting norms (3 primary + 2 secondary) and needs validation from domain experts before full production deployment.

---

## Expert Stakeholders

### Primary (High Priority)
- **Минфин РК** - Финансовый департамент (Уполномоченный орган)
  - Contact: zakupki@minfin.kz
  - Focus: Legal accuracy, compliance with ЗРГК

- **МЗСП** - Министерство по развитию инфраструктуры
  - Focus: Практическая применимость, реальные случаи

- **Юридические консультанты** по госзакупкам (3-5 специалистов)
  - Focus: Полнота анализа, логичность выводов

### Secondary (Medium Priority)
- **Omarket** техподдержка & главные юристы
  - Focus: Интеграция с платформой, user experience

- **КЦАОС** - Казахстанский центр адаптации государственных услуг
  - Focus: Охват разных регионов, доступность

- **Ассоциации МСП** - Представители малого и среднего бизнеса
  - Focus: Практическое применение для участников закупок

---

## Feedback Collection Strategy

### Phase 1: Setup & Onboarding (1 week)

#### 1.1 Create Feedback Collection Interface
**Option A: Web Form** (Recommended)
```
┌─────────────────────────────────────────┐
│   FEEDBACK ON CONFLICTING NORMS SYSTEM   │
├─────────────────────────────────────────┤
│                                          │
│ Expert Name: [________]                 │
│ Organization: [________]                │
│ Contact Email: [________]                │
│                                          │
│ Question Test Case:                      │
│ [Display test question]                  │
│                                          │
│ System Response:                         │
│ [Display bot answer]                    │
│                                          │
│ Feedback Section:                        │
│ [ ] Accurate    [ ] Partially Correct   │
│ [ ] Inaccurate  [ ] Insufficient Info   │
│                                          │
│ Comments: [textarea]                    │
│                                          │
│ [Submit Feedback]                        │
│                                          │
└─────────────────────────────────────────┘
```

**Option B: Email Template**
- Send structured email with question, response, feedback form
- Easier for busy experts, asynchronous

**Option C: Interview/Meeting**
- 30-minute sessions with 2-3 key stakeholders
- More detailed discussion, immediate clarification

#### 1.2 Prepare Test Case Sets
**Set A: Primary Conflicts** (9 questions - Phase 2/3 validated)
- Требования к персоналу (3 Q's)
- Электронная подпись (3 Q's)
- Право на участие (3 Q's)

**Set B: Secondary Conflicts** (12 questions - Phase 4 new)
- EDS exceptions (5 Q's)
- Discrimination (7 Q's)

**Set C: Edge Cases** (10 questions - Expert-generated)
- Ambiguous scenarios
- Real cases from practice
- Boundary conditions

#### 1.3 Define Evaluation Criteria

| Criterion | Weight | Scoring |
|-----------|--------|---------|
| **Accuracy** | 35% | 1=Wrong, 5=Perfect |
| **Completeness** | 25% | 1=Missing key points, 5=Comprehensive |
| **Clarity** | 20% | 1=Confusing, 5=Very clear |
| **Actionability** | 15% | 1=No practical use, 5=Directly useful |
| **Compliance** | 5% | Pass/Fail - Legal accuracy |

---

### Phase 2: Feedback Collection (2-3 weeks)

#### 2.1 Distribute Test Cases

**Timeline:**
- Day 1: Send invitations with explanation
- Day 2: Provide access to feedback platform
- Day 3-7: Answer expert clarification questions
- Day 8-14: Collect feedback submissions
- Day 15-21: Optional follow-up interviews

#### 2.2 Feedback Collection Fields

**For Each Test Case:**
```yaml
test_id: "primary_01_personnel"
question: "Можно ли требовать сертифицированного инженера в команде?"
expert_rating:
  accuracy: 4  # 1-5
  completeness: 5
  clarity: 4
  actionability: 5
  compliance: PASS/FAIL

expert_comments: "Хороший анализ, но не упомянут практический случай X..."
suggestions: "Добавить пример из реальной Omarket закупки..."
confidence_level: "High" # High/Medium/Low

expert_background:
  years_experience: 12
  specialization: "Госзакупки, контрактация"
  organization: "Минфин РК"
```

#### 2.3 Track Submissions

**Spreadsheet Tracking:**
| Expert | Organization | Set A | Set B | Set C | Status | Rating |
|--------|--------------|-------|-------|-------|--------|--------|
| Иван П | Минфин | ✓ | ✓ | ✗ | 90% | 4.2 |
| Мария К | OMarket | ✓ | ✗ | ✗ | 50% | 4.0 |
| ... | ... | ... | ... | ... | ... | ... |

---

### Phase 3: Analysis & Iteration (1-2 weeks)

#### 3.1 Aggregate Feedback
```python
# Pseudo-analysis
for conflict_type in CONFLICTING_NORMS:
    avg_accuracy = mean(all_expert_ratings[conflict_type]['accuracy'])
    improvement_needed = any(rating < 3.5)

    if avg_accuracy >= 4.2:
        status = "READY FOR PRODUCTION"
    elif avg_accuracy >= 3.5:
        status = "NEEDS MINOR FIXES"
    else:
        status = "NEEDS SIGNIFICANT WORK"
```

#### 3.2 Identify Common Issues
- **Pattern 1:** Missing practical examples (mentioned by 60% of experts)
- **Pattern 2:** Insufficient coverage of case X (mentioned by 40%)
- **Pattern 3:** Clarity issue in explanation (mentioned by 25%)

#### 3.3 Prioritize Fixes
```
Priority 1 (Compliance): Issues affecting legal accuracy
Priority 2 (High Impact): Issues mentioned by multiple experts
Priority 3 (Quality): Enhancement suggestions
```

#### 3.4 Implement Fixes
Based on expert feedback:
1. **Add/modify chunks** if content gaps identified
2. **Update keyword lists** if detection coverage insufficient
3. **Improve explanations** if clarity issues found
4. **Add examples** if practical usefulness low

#### 3.5 Re-test with Subset
- Re-send improved answers to 3-4 key experts
- Verify that fixes addressed concerns
- Obtain approval before production deployment

---

## Detailed Feedback Questions

### Section 1: Accuracy & Legal Compliance

**Q1: Legal Accuracy**
```
For this test case, does the system's answer:
□ Correctly interpret all applicable norms?
□ Accurately cite relevant статьи/пункты?
□ Avoid legal misinterpretations?
□ Align with current ЗРГК and Правила?

If not, please specify which нормы are misinterpreted:
[textarea]
```

**Q2: Completeness**
```
Does the analysis cover:
□ Primary норма that allows the requirement?
□ Secondary норма that restricts it?
□ Practical scenarios and examples?
□ Potential consequences of violation?

If incomplete, what is missing:
[textarea]
```

### Section 2: Practical Applicability

**Q3: Real-World Relevance**
```
Have you encountered similar situations in your experience?
- Frequently (more than 10 times)
- Occasionally (2-10 times)
- Rarely (less than 2 times)
- Never

If yes, was the system's answer useful for your case?
□ Very useful
□ Somewhat useful
□ Not useful
□ Would need modifications

Comments: [textarea]
```

**Q4: User Understanding**
```
For an average Omarket user (not a lawyer), would this answer:
□ Be easy to understand?
□ Provide clear guidance on what to do?
□ Help avoid legal violations?
□ Be actionable (implementable)?

Suggestions for improvement: [textarea]
```

### Section 3: Detection & Coverage

**Q5: Keyword Trigger Coverage**
```
Did the system catch this as a conflicting norm case?
- Yes, immediately
- Yes, but required rephrasing
- No, should have detected

If detection issues, what keywords were missing:
[textarea]

What alternative phrasings should trigger this conflict:
[textarea]
```

**Q6: Related Cases**
```
What other variations of this conflict should we support:
[textarea]

Real case examples you've seen:
[textarea]
```

### Section 4: Overall Assessment

**Q7: System Rating**
```
Overall rating for this conflict type: [1-5 stars]

Would you recommend this system to:
□ Госзакупки specialists - Yes / No / Maybe
□ Procurement officers - Yes / No / Maybe
□ Regular suppliers - Yes / No / Maybe

Potential risks or concerns:
[textarea]

What would make this system better:
[textarea]
```

---

## Success Metrics

### Quantitative
- **Target:** 80%+ experts rate accuracy ≥ 4/5
- **Target:** 75%+ experts rate completeness ≥ 4/5
- **Target:** 85%+ experts rate clarity ≥ 4/5
- **Target:** Legal compliance 100% PASS

### Qualitative
- **Target:** No systematic legal misinterpretations
- **Target:** Clear actionable guidance per expert feedback
- **Target:** Positive practical applicability feedback
- **Target:** Expert willingness to recommend to users

### Coverage
- **Target:** All 5 conflict types tested by at least 2 experts
- **Target:** Edge cases covered by specialist experts
- **Target:** Feedback from at least 2 different organizations

---

## Timeline & Milestones

```
Week 1: Setup & Invitation
├─ Mon: Create feedback platform
├─ Tue: Finalize test case sets
├─ Wed: Prepare invitations & explanations
└─ Thu-Fri: Send invitations to experts

Week 2-3: Feedback Collection
├─ Mon: First submissions expected
├─ Tue-Wed: Follow-up with non-respondents
├─ Thu-Fri: Collect remaining submissions

Week 3-4: Analysis & Fixes
├─ Mon: Aggregate feedback, identify patterns
├─ Tue-Wed: Prioritize and implement fixes
├─ Thu: Re-test with subset of experts
└─ Fri: Final approval decision

Week 4+: Production Deployment
├─ Mon: Deploy to production
├─ Tue: Monitor for issues
└─ Wed+: Collect user feedback from real interactions
```

---

## Contingency Plan

### If Accuracy Rating < 80%
1. **Identify specific failing conflict types**
2. **Conduct expert interviews** to understand issues
3. **Modify CONFLICTING_NORMS definitions**
4. **Re-collect feedback** on modified cases
5. **Phase expert feedback into incremental releases**

### If Legal Compliance Fails
1. **Immediately escalate** to Минфин for legal review
2. **Halt production deployment**
3. **Fix legal issues** based on official guidance
4. **Obtain explicit approval** from юридический консультант
5. **Re-test completey** before re-submission

### If Coverage Gaps Identified
1. **Phase new conflict types** into future phases
2. **Clearly document limitations** in bot responses
3. **Add disclaimers** for areas needing expert review
4. **Prioritize missing areas** for Phase 5

---

## Feedback Processing Workflow

```
Expert Submits Feedback
    ↓
Parse & Validate Data
    ↓
├─ Aggregate by conflict_type
├─ Calculate average ratings
├─ Identify common comments
├─ Flag legal issues
└─ Extract improvement suggestions
    ↓
Generate Analysis Report
    ├─ Summary statistics
    ├─ Pattern identification
    ├─ Risk assessment
    └─ Priority fixes
    ↓
Decide Next Action
    ├─ Ready for Production? → Deploy
    ├─ Needs Fixes? → Implement & Re-test
    └─ Major Issues? → Escalate & Redesign
```

---

## Documentation & Transparency

### Share Back with Experts
```
Dear [Expert Name],

Thank you for your feedback on the conflicting norms system!

AGGREGATE RESULTS:
- Accuracy: 4.3/5 (excellent)
- Completeness: 4.1/5 (good)
- Clarity: 4.0/5 (good)

ACTIONS TAKEN:
Based on your feedback, we have:
1. Added 8 new examples for better clarity
2. Expanded keyword detection for secondary conflicts
3. Modified explanation for case X
4. Added legal disclaimer for edge cases

NEXT STEPS:
- System deployed to production on [date]
- Monitoring for real-world feedback
- Planning Phase 5 enhancements based on user data

Would you be interested in:
[ ] Continued collaboration on improvements?
[ ] Integration testing with your organization?
[ ] Training workshop for your team?
```

---

## Success Example

**Expected Positive Feedback Scenario:**

```
Expert: Иван Петров, Senior Legal Specialist, Минфин

Feedback Summary:
✓ Accuracy: 5/5 - "Все интерпретации соответствуют действующему законодательству"
✓ Completeness: 4/5 - "Хорошее покрытие, но можно добавить пример X"
✓ Clarity: 5/5 - "Очень понятные объяснения для непрофессионалов"
✓ Actionability: 5/5 - "Точно то, что нужно нашим поставщикам"
✓ Compliance: PASS - "Соответствует ЗРГК и всем нормам"

Overall Rating: 5 ⭐⭐⭐⭐⭐

Recommendation: "Готово к production. Система окажет большую помощь бизнесу."

→ This expert would receive public attribution in bot's /docs command
→ Their feedback would be featured in success story
→ They would be invited to Phase 5 expert panel
```

---

## Conclusion

This expert feedback framework ensures that the conflicting norms detection system meets high standards for:
- **Legal Accuracy** - Verified by Минфин & юристы
- **Practical Usefulness** - Validated by real procurement specialists
- **User Understanding** - Confirmed by business representatives

By systematically collecting and implementing expert feedback, we transform the system from a working prototype into a trusted reference tool for государственные закупки stakeholders.

---

**Ready to Launch:** 2026-02-24
**Estimated Feedback Collection:** 2-3 weeks
**Target Production Deployment:** Early-Mid March 2026
