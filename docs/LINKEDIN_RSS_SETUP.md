# 🔗 LinkedIn RSS Feed Setup Guide

**Create your personalized LinkedIn job search RSS feed that refreshes every hour with 24+ PM jobs.**

## 🎯 Overview

Your LinkedIn RSS feed will become the #1 source for PM Watchman, delivering:
- **24+ jobs every hour** (150+ jobs every 6 hours)  
- **Personalized search** based on your keywords and location
- **Fresh opportunities** updated every 60 minutes
- **Domain-specific results** for your PM focus area

## 🚀 Quick Setup (5 minutes)

### Step 1: Create RSS.app Account
1. Go to **[RSS.app](https://rss.app)**
2. Sign up for **free account** (no payment needed)
3. Verify your email address

### Step 2: Create LinkedIn Job Search RSS Feed

1. **Click "Create Feed"** in RSS.app dashboard
2. **Choose "LinkedIn Jobs"** from the source options
3. **Configure your search parameters:**

#### For Fintech PM:
```
Keywords: "Product Manager" OR "PM" OR "APM" 
Location: San Francisco OR New York OR Remote
Company Keywords: fintech OR payments OR banking OR financial services
```

#### For Healthcare PM:
```  
Keywords: "Product Manager" OR "Healthcare PM" OR "Medical PM"
Location: Boston OR San Francisco OR Remote  
Company Keywords: healthcare OR medical OR clinical OR digital health
```

#### For Consulting/Enterprise PM:
```
Keywords: "Product Manager" OR "Strategy PM" OR "Enterprise PM"  
Location: New York OR San Francisco OR Chicago OR Remote
Company Keywords: consulting OR enterprise OR B2B OR platform
```

#### For Startup PM:
```
Keywords: "Product Manager" OR "Founding PM" OR "0-1 PM"
Location: San Francisco OR New York OR Remote
Company Keywords: startup OR early stage OR YC OR series A
```

#### For New Grad PM:
```
Keywords: "Associate Product Manager" OR "APM" OR "Junior PM" OR "New Grad PM"
Location: San Francisco OR New York OR Seattle OR Remote  
Company Keywords: APM program OR rotational OR new grad OR MBA
```

### Step 3: Advanced Filtering (Optional)
- **Date Range**: Last 24 hours (for freshest jobs)
- **Job Type**: Full-time  
- **Experience Level**: Based on your template choice
- **Salary Range**: Set your minimum if desired

### Step 4: Generate RSS Feed
1. **Preview your results** (should see 20-50 jobs)
2. **Click "Generate RSS Feed"**  
3. **Copy the RSS URL** (format: `https://rss.app/feeds/ABC123.xml`)
4. **Test the feed** by opening URL in browser

## 🔧 Integration with PM Watchman

### Automatic Integration
When you run `python3 scripts/quick_setup.py`, it will:
1. Ask for your LinkedIn RSS feed URL
2. Configure it as priority #1 source  
3. Set hourly refresh (matches RSS.app 60-minute updates)
4. Enable cache bypass for fresh data every time

### Manual Integration
If setting up manually, add to `config/job_sources.json`:

```json
{
  "rss_feeds": {
    "enabled": true,
    "priority": 1,
    "feeds": {
      "linkedin_rss_primary": {
        "url": "https://rss.app/feeds/YOUR_FEED_ID.xml",
        "enabled": true,
        "keywords": ["product manager", "PM", "APM"], 
        "priority": 1,
        "refresh_hours": 1,
        "linkedin_source": true,
        "high_frequency": true
      }
    }
  }
}
```

## 📊 Expected Performance

**With properly configured LinkedIn RSS:**
- **24+ jobs every hour** during business hours
- **150+ jobs over 6 hours** (6 hourly refreshes)
- **90%+ relevance rate** for your search criteria
- **Fresh opportunities** within 1 hour of posting
- **Top 20 delivered** based on your scoring system

## 🛠️ Troubleshooting

### No Jobs Found
**Problem**: RSS feed returns 0 jobs  
**Solution**: 
- Broaden keywords (use OR operators)
- Include more locations  
- Check LinkedIn has jobs for your criteria
- Verify RSS feed URL works in browser

### Too Many Jobs
**Problem**: RSS feed returns 100+ jobs/hour  
**Solution**:
- Narrow keywords to more specific roles
- Reduce location scope
- Add negative keywords to exclude unwanted roles
- PM Watchman will score and filter to top 20

### Jobs Not Relevant  
**Problem**: Jobs don't match your profile
**Solution**:
- Refine keywords in RSS.app
- Update your `pm_profile.json` scoring criteria  
- Adjust company and keyword bonuses in `system_settings.json`
- Use domain-specific templates for better targeting

### RSS Feed Stops Working
**Problem**: Feed becomes inactive
**Solution**:
- Check RSS.app account status
- Verify LinkedIn hasn't changed their structure
- Create new feed with same parameters  
- Update feed URL in configuration

## 🎯 Domain-Specific Tips

### Fintech Focus
- Include company names: `Stripe OR Square OR Plaid OR Coinbase`
- Add keywords: `payments OR cryptocurrency OR lending OR regtech`
- Target locations: `San Francisco OR New York OR London`

### Healthcare Focus  
- Include: `Epic OR Cerner OR Teladoc OR digital health`
- Add: `clinical OR medical device OR HIPAA OR FDA`
- Target: `Boston OR Research Triangle OR San Francisco`

### Consulting Focus
- Include: `McKinsey OR BCG OR Bain OR Deloitte` 
- Add: `strategy OR operations OR transformation`
- Target: `New York OR Boston OR Chicago OR DC`

### Startup Focus
- Include: `YC OR Y Combinator OR series A OR early stage`
- Add: `0-1 OR founding OR product-market fit`  
- Target: `San Francisco OR New York OR Austin`

### New Grad Focus
- Include: `APM OR associate product manager OR new grad`
- Add: `rotational OR MBA OR recent graduate`
- Target: `San Francisco OR Seattle OR New York`

## 🔄 Maintenance

### Weekly Tasks:
- [ ] Check RSS feed still active in RSS.app
- [ ] Review job quality from past week
- [ ] Adjust keywords if needed

### Monthly Tasks:  
- [ ] Analyze job discovery metrics
- [ ] Update search criteria based on results
- [ ] Consider creating additional specialized feeds

### As Needed:
- [ ] Create seasonal feeds (intern hiring, MBA recruiting)
- [ ] Add location-specific feeds for new markets
- [ ] Update company lists based on funding/growth

## 🎉 Success Metrics

**Your LinkedIn RSS feed is successful when:**
- ✅ 20+ jobs discovered every hour during business hours
- ✅ 80%+ of jobs match your target role and companies  
- ✅ Regular job opportunities from your target company list
- ✅ Mix of experience levels appropriate for your profile
- ✅ Geographic distribution matches your preferences

**Optimization complete when PM Watchman delivers 150+ jobs every 6 hours with 90%+ relevance!** 🚀