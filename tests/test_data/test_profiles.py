"""
Test PM Profiles for Scoring Validation

Different Product Manager profiles representing various experience levels,
industries, and preferences to test scoring accuracy.
"""

from src.core.config_loader import PMProfile


def create_junior_pm_profile() -> PMProfile:
    """
    Junior PM Profile (1-3 years experience)
    Recent graduate or career changer, eager to learn.
    """
    return PMProfile(
        years_of_pm_experience=2,
        current_title="Associate Product Manager",
        seniority_level="junior",
        
        # Target roles - open to various PM titles
        primary_titles=[
            "Product Manager",
            "Associate Product Manager", 
            "Junior Product Manager"
        ],
        secondary_titles=[
            "Product Owner",
            "Product Analyst",
            "Business Analyst"
        ],
        avoid_titles=[
            "Senior Product Manager",
            "Principal Product Manager",
            "Director of Product",
            "Sales Manager",
            "Marketing Manager"
        ],
        
        # Skills - foundational PM skills
        core_pm_skills=[
            "product strategy",
            "user research", 
            "roadmapping",
            "agile",
            "stakeholder management",
            "data analysis",
            "wireframing"
        ],
        technical_skills=[
            "SQL",
            "Excel",
            "Google Analytics",
            "Jira", 
            "Confluence",
            "Figma"
        ],
        domain_expertise=[
            "B2B SaaS",
            "mobile apps",
            "web platforms"
        ],
        
        # Industries - open to learning new areas
        primary_industries=[
            "technology",
            "software",
            "SaaS"
        ],
        interested_industries=[
            "fintech",
            "healthtech", 
            "edtech",
            "e-commerce",
            "social"
        ],
        avoid_industries=[
            "tobacco",
            "gambling",
            "adult content"
        ],
        
        # Geographic - flexible, open to remote
        remote_preference="remote_first",
        preferred_locations=[
            "Remote",
            "San Francisco",
            "New York", 
            "Austin",
            "Seattle"
        ],
        
        # Company - prefer growth stage, learning opportunities
        company_stages=[
            "startup",
            "growth"
        ],
        company_sizes=[
            "11-50",
            "51-200",
            "201-500"
        ],
        preferred_companies=[
            "Stripe",
            "Notion", 
            "Linear",
            "Figma",
            "Vercel"
        ],
        avoid_companies=[
            "Facebook",
            "TikTok"
        ],
        
        # Compensation - entry level expectations
        minimum_base_salary=90000,
        target_total_comp=130000,
        equity_importance="high"  # Willing to take equity for upside
    )


def create_mid_level_pm_profile() -> PMProfile:
    """
    Mid-Level PM Profile (3-7 years experience)
    Experienced PM looking for growth and impact.
    """
    return PMProfile(
        years_of_pm_experience=5,
        current_title="Product Manager",
        seniority_level="mid",
        
        # Target roles - ready for senior responsibilities
        primary_titles=[
            "Senior Product Manager",
            "Product Manager"
        ],
        secondary_titles=[
            "Product Lead",
            "Principal Product Manager"
        ],
        avoid_titles=[
            "Associate Product Manager",
            "Junior Product Manager",
            "Product Owner",
            "Project Manager",
            "Marketing Manager"
        ],
        
        # Skills - comprehensive PM toolkit
        core_pm_skills=[
            "product strategy",
            "roadmapping",
            "user research",
            "data analysis",
            "A/B testing",
            "stakeholder management",
            "market research",
            "competitive analysis",
            "product metrics",
            "go-to-market"
        ],
        technical_skills=[
            "SQL",
            "Python",
            "Tableau",
            "Mixpanel",
            "Google Analytics",
            "Figma",
            "Jira",
            "Confluence",
            "Amplitude"
        ],
        domain_expertise=[
            "B2B SaaS",
            "API products", 
            "platform products",
            "data products"
        ],
        
        # Industries - focused expertise with some openness
        primary_industries=[
            "fintech",
            "SaaS",
            "technology"
        ],
        interested_industries=[
            "healthtech",
            "climate tech",
            "developer tools"
        ],
        avoid_industries=[
            "tobacco",
            "gambling",
            "adult content",
            "oil & gas"
        ],
        
        # Geographic - prefer remote but open to great opportunities
        remote_preference="remote_first",
        preferred_locations=[
            "Remote",
            "San Francisco",
            "New York",
            "Austin"
        ],
        
        # Company - growth to public companies  
        company_stages=[
            "growth",
            "public"
        ],
        company_sizes=[
            "201-500",
            "501-1000", 
            "1000+"
        ],
        preferred_companies=[
            "Stripe",
            "Notion",
            "Linear",
            "Figma",
            "Vercel",
            "DataDog",
            "MongoDB"
        ],
        avoid_companies=[
            "Meta",
            "TikTok",
            "Palantir"
        ],
        
        # Compensation - market rate expectations
        minimum_base_salary=140000,
        target_total_comp=200000,
        equity_importance="medium"
    )


def create_senior_pm_profile() -> PMProfile:
    """
    Senior PM Profile (7+ years experience)  
    Seasoned PM looking for leadership opportunities and high impact.
    """
    return PMProfile(
        years_of_pm_experience=9,
        current_title="Senior Product Manager",
        seniority_level="senior",
        
        # Target roles - senior leadership positions
        primary_titles=[
            "Principal Product Manager",
            "Staff Product Manager",
            "Senior Product Manager"
        ],
        secondary_titles=[
            "Director of Product",
            "VP of Product",
            "Head of Product"
        ],
        avoid_titles=[
            "Product Manager",
            "Associate Product Manager",
            "Product Owner",
            "Project Manager",
            "Program Manager"
        ],
        
        # Skills - advanced PM capabilities
        core_pm_skills=[
            "product strategy",
            "strategic planning", 
            "roadmapping",
            "user research",
            "data analysis",
            "A/B testing",
            "stakeholder management",
            "team leadership",
            "market research",
            "competitive analysis",
            "product metrics",
            "OKRs",
            "go-to-market",
            "pricing strategy",
            "product launch",
            "customer interviews"
        ],
        technical_skills=[
            "SQL",
            "Python",
            "R",
            "Tableau",
            "Looker",
            "Mixpanel",
            "Amplitude",
            "Google Analytics",
            "Figma",
            "Sketch",
            "Jira",
            "Confluence",
            "GitHub"
        ],
        domain_expertise=[
            "B2B SaaS",
            "platform products",
            "API products",
            "data products",
            "developer tools",
            "enterprise software"
        ],
        
        # Industries - deep expertise in specific areas
        primary_industries=[
            "fintech",
            "developer tools",
            "enterprise software"
        ],
        interested_industries=[
            "climate tech",
            "AI/ML",
            "data infrastructure"
        ],
        avoid_industries=[
            "tobacco",
            "gambling", 
            "adult content",
            "oil & gas",
            "defense"
        ],
        
        # Geographic - selective about location
        remote_preference="remote_only",
        preferred_locations=[
            "Remote"
        ],
        
        # Company - established companies with scale
        company_stages=[
            "growth",
            "public"
        ],
        company_sizes=[
            "501-1000",
            "1000+"
        ],
        preferred_companies=[
            "Stripe",
            "Databricks",
            "Snowflake",
            "MongoDB",
            "Atlassian",
            "Twilio",
            "DataDog"
        ],
        avoid_companies=[
            "Meta",
            "TikTok", 
            "Palantir",
            "Uber"
        ],
        
        # Compensation - senior level expectations
        minimum_base_salary=180000,
        target_total_comp=300000,
        equity_importance="medium"
    )


def create_fintech_specialist_profile() -> PMProfile:
    """
    Fintech Specialist PM Profile
    Deep fintech experience, focused on payments and financial services.
    """
    return PMProfile(
        years_of_pm_experience=6,
        current_title="Senior Product Manager - Payments",
        seniority_level="senior",
        
        # Target roles - fintech focused
        primary_titles=[
            "Senior Product Manager",
            "Principal Product Manager"
        ],
        secondary_titles=[
            "Product Lead",
            "Staff Product Manager"
        ],
        avoid_titles=[
            "Marketing Manager",
            "Sales Manager",
            "Project Manager"
        ],
        
        # Skills - fintech specialized
        core_pm_skills=[
            "product strategy",
            "payments product management",
            "fintech regulations",
            "risk management",
            "fraud prevention",
            "user research",
            "data analysis",
            "A/B testing",
            "financial modeling"
        ],
        technical_skills=[
            "SQL",
            "Python",
            "Tableau",
            "Looker",
            "Mixpanel",
            "payments APIs",
            "blockchain",
            "KYC/AML systems"
        ],
        domain_expertise=[
            "payments",
            "financial services",
            "regulatory compliance",
            "risk management",
            "cryptocurrency",
            "banking APIs"
        ],
        
        # Industries - fintech focused with some flexibility
        primary_industries=[
            "fintech",
            "payments",
            "financial services"
        ],
        interested_industries=[
            "cryptocurrency",
            "banking",
            "insurance"
        ],
        avoid_industries=[
            "tobacco",
            "gambling",
            "adult content"
        ],
        
        # Geographic - major fintech hubs
        remote_preference="hybrid",
        preferred_locations=[
            "San Francisco",
            "New York", 
            "London",
            "Remote"
        ],
        
        # Company - fintech companies of all stages
        company_stages=[
            "startup",
            "growth",
            "public"
        ],
        company_sizes=[
            "51-200",
            "201-500",
            "501-1000"
        ],
        preferred_companies=[
            "Stripe",
            "Square", 
            "Plaid",
            "Coinbase",
            "Robinhood",
            "Affirm",
            "Chime"
        ],
        avoid_companies=[],
        
        # Compensation - fintech market rates
        minimum_base_salary=160000,
        target_total_comp=250000,
        equity_importance="high"
    )


def create_healthcare_pm_profile() -> PMProfile:
    """
    Healthcare PM Profile
    Passionate about health technology and improving patient outcomes.
    """
    return PMProfile(
        years_of_pm_experience=4,
        current_title="Product Manager - Health Tech",
        seniority_level="mid",
        
        # Target roles - health focused
        primary_titles=[
            "Product Manager",
            "Senior Product Manager"
        ],
        secondary_titles=[
            "Health Product Manager",
            "Clinical Product Manager"
        ],
        avoid_titles=[
            "Sales Manager",
            "Marketing Manager"
        ],
        
        # Skills - healthcare specific
        core_pm_skills=[
            "product strategy",
            "user research",
            "clinical workflows",
            "healthcare regulations",
            "HIPAA compliance",
            "patient experience",
            "provider experience",
            "data analysis"
        ],
        technical_skills=[
            "SQL",
            "R",
            "Tableau",
            "clinical data standards",
            "HL7",
            "FHIR",
            "EMR integration"
        ],
        domain_expertise=[
            "healthcare technology",
            "clinical workflows",
            "patient engagement",
            "telemedicine", 
            "health data",
            "medical devices"
        ],
        
        # Industries - healthcare focused
        primary_industries=[
            "healthtech",
            "healthcare",
            "biotech"
        ],
        interested_industries=[
            "medical devices",
            "pharmaceuticals",
            "mental health"
        ],
        avoid_industries=[
            "tobacco",
            "gambling",
            "adult content"
        ],
        
        # Geographic - healthcare hubs
        remote_preference="hybrid",
        preferred_locations=[
            "Boston",
            "San Francisco",
            "Remote",
            "Research Triangle"
        ],
        
        # Company - health tech companies
        company_stages=[
            "startup",
            "growth"
        ],
        company_sizes=[
            "11-50",
            "51-200",
            "201-500"
        ],
        preferred_companies=[
            "Teladoc",
            "Veracyte",
            "23andMe",
            "Oscar Health",
            "One Medical"
        ],
        avoid_companies=[],
        
        # Compensation - healthcare market
        minimum_base_salary=125000,
        target_total_comp=175000,
        equity_importance="medium"
    )


def get_all_test_profiles():
    """Get all test PM profiles."""
    return {
        "junior_pm": create_junior_pm_profile(),
        "mid_level_pm": create_mid_level_pm_profile(), 
        "senior_pm": create_senior_pm_profile(),
        "fintech_specialist": create_fintech_specialist_profile(),
        "healthcare_pm": create_healthcare_pm_profile()
    }


def get_profile_descriptions():
    """Get descriptions of each test profile."""
    return {
        "junior_pm": {
            "experience": "2 years",
            "level": "Associate PM", 
            "focus": "Learning and growth opportunities",
            "industries": "Open to various tech sectors",
            "compensation": "$90k-$130k",
            "work_style": "Remote-first, flexible"
        },
        "mid_level_pm": {
            "experience": "5 years",
            "level": "Product Manager",
            "focus": "Impact and career advancement", 
            "industries": "Fintech, SaaS, technology",
            "compensation": "$140k-$200k",
            "work_style": "Remote-first"
        },
        "senior_pm": {
            "experience": "9 years", 
            "level": "Senior/Principal PM",
            "focus": "Leadership and strategic impact",
            "industries": "Fintech, developer tools, enterprise",
            "compensation": "$180k-$300k",
            "work_style": "Remote-only"
        },
        "fintech_specialist": {
            "experience": "6 years",
            "level": "Senior PM - Payments",
            "focus": "Deep fintech expertise",
            "industries": "Fintech, payments, financial services",
            "compensation": "$160k-$250k", 
            "work_style": "Hybrid, fintech hubs"
        },
        "healthcare_pm": {
            "experience": "4 years",
            "level": "Health Tech PM",
            "focus": "Patient and provider experience",
            "industries": "Healthcare, biotech, health tech",
            "compensation": "$125k-$175k",
            "work_style": "Hybrid, healthcare hubs"
        }
    }