# Deprecated V1 Campaign Wizard Files

## Status: DEPRECATED - DO NOT USE

The Campaign Design Wizard V1 has been replaced by V2. These files are kept for reference only.

## Active V2 Implementation

**Active Files:**
- `campaigns/views.py` - `CampaignDesignerWizardView` class (line 1127+)
- `campaigns/wizard_views_v2.py` - V2 API endpoints
- `static/js/campaign_wizard_v2.js` - V2 JavaScript controller
- `templates/campaigns/campaign_designer_wizard_v2.html` - V2 UI template

**Active URL:**
- `/campaigns/designer/` → V2 wizard

## Deprecated V1 Files (Safe to Remove)

### Python Views
- ❌ `campaigns/wizard_views.py` - Old 4-step wizard views
  - Functions: `campaign_wizard_start()`, `campaign_wizard_init()`, `campaign_wizard_story_selection()`, etc.
  - **NOT IMPORTED OR USED** (checked urls.py)

### Templates
- ❌ `templates/campaigns/campaign_designer_wizard.html` - Old V1 single-page template
- ❌ `templates/campaigns/campaign_designer_wizard_BACKUP.html` - Backup copy
- ❌ `campaigns/templates/campaigns/wizard/base_wizard.html` - V1 base template
- ❌ `campaigns/templates/campaigns/wizard/step1_select_world.html` - V1 step 1
- ❌ `campaigns/templates/campaigns/wizard/step2_select_story.html` - V1 step 2
- ❌ `campaigns/templates/campaigns/wizard/step3_approve_core.html` - V1 step 3
- ❌ `campaigns/templates/campaigns/wizard/step4_progress.html` - V1 step 4

### JavaScript
- ❌ `static/js/campaign_wizard.js` - Old V1 JavaScript controller

## Verification

Checked `skillforge/urls.py` (lines 60-234):
- ✅ Line 175: `/campaigns/designer/` routes to `CampaignDesignerWizardView` (V2 in views.py)
- ✅ Lines 224-234: All API endpoints use `wizard_views_v2`
- ✅ Line 60: `wizard_views` is imported but **NOT USED** in any URL pattern

## Recommendation

**Safe to delete:**
```bash
rm services/django-web/campaigns/wizard_views.py
rm services/django-web/static/js/campaign_wizard.js
rm services/django-web/templates/campaigns/campaign_designer_wizard.html
rm services/django-web/templates/campaigns/campaign_designer_wizard_BACKUP.html
rm -r services/django-web/campaigns/templates/campaigns/wizard/
```

**Remove unused import from urls.py:**
```python
# Line 60-66 in skillforge/urls.py - Remove these lines:
from campaigns.wizard_views import (
    campaign_wizard_start,
    campaign_wizard_init,
    campaign_wizard_story_selection,
    # ... etc
)
```

## Migration Notes

V1 → V2 changes:
- **Steps**: 4 steps → 11 steps (more granular control)
- **Architecture**: Session-based → API-based with request_id tracking
- **Resume**: No resume → In-progress campaign detection
- **Approval Gates**: Core only → Core, Quests, Places, Scenes
- **Progress**: Simple polling → Phase-based progress with timers
- **Backend**: Direct orchestrator calls → Async workflow with status endpoint
