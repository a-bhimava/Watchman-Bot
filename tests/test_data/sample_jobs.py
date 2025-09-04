"""
Sample PM Job Data for Testing

15 realistic Product Manager job scenarios covering the full spectrum
of scoring possibilities (0-100+ points) to validate the modular scoring system.
"""

from datetime import datetime, timedelta
from src.integrations.rss_processor import JobData


def create_test_jobs():
    """
    Create comprehensive test dataset of PM jobs.
    
    Returns:
        List of JobData instances covering all scoring scenarios
    """
    
    # Perfect Match Jobs (90-100+ points expected)
    perfect_jobs = [
        JobData(
            id="perfect_01",
            title="Senior Product Manager",
            company="Stripe",
            location="Remote",
            salary_range="$160,000 - $220,000",
            experience_required="5+ years PM experience",
            skills_mentioned=[
                "product strategy", "roadmapping", "user research", 
                "data analysis", "SQL", "A/B testing", "figma"
            ],
            industry="fintech",
            description="""
            We're looking for an experienced Senior Product Manager to lead our payments product suite.
            You'll work with engineering, design, and data teams to build features used by millions of businesses globally.
            
            Key responsibilities:
            - Develop product strategy and roadmap for payment processing features
            - Conduct user research and analyze customer feedback to identify opportunities  
            - Design and execute A/B tests to optimize conversion and user experience
            - Work with SQL and analytics tools to measure product performance
            - Collaborate with design team using Figma for wireframing and prototyping
            - Lead cross-functional teams through agile development process
            
            Requirements:
            - 5+ years of product management experience, preferably in fintech
            - Strong analytical skills with experience in data analysis and SQL
            - Experience with user research methodologies and A/B testing
            - Excellent stakeholder management and communication skills
            - Experience with design tools like Figma or similar
            
            We offer competitive salary, significant equity upside, and full remote work flexibility.
            """,
            apply_url="https://stripe.com/jobs/listing/senior-product-manager",
            source="linkedin",
            posted_date=datetime.now() - timedelta(hours=2),
            raw_data={"company_type": "public", "funding_stage": "public"}
        ),
        
        JobData(
            id="perfect_02", 
            title="Product Manager",
            company="Notion",
            location="San Francisco, CA (Remote OK)",
            salary_range="$140k-$180k + equity",
            experience_required="3-5 years",
            skills_mentioned=[
                "product strategy", "user research", "roadmapping",
                "analytics", "agile", "stakeholder management"
            ],
            industry="saas",
            description="""
            Join Notion as a Product Manager to help build the future of productivity software.
            We're looking for someone passionate about creating tools that help millions organize their work and life.
            
            What you'll do:
            - Own product strategy for key user-facing features
            - Conduct user research to understand customer needs and pain points  
            - Build comprehensive product roadmaps aligned with company objectives
            - Work closely with engineering teams in an agile environment
            - Analyze user behavior data to make data-driven product decisions
            - Manage stakeholder expectations and communicate updates across the organization
            
            What we're looking for:
            - 3-5 years of product management experience
            - Experience with B2B SaaS products preferred
            - Strong analytical mindset with experience using analytics tools
            - Excellent written and verbal communication skills
            - Experience with agile development methodologies
            
            Benefits: Competitive salary, meaningful equity, flexible work arrangements, comprehensive health benefits.
            """,
            apply_url="https://notion.so/careers/product-manager",
            source="company_direct",
            posted_date=datetime.now() - timedelta(hours=8),
            raw_data={"company_size": "201-500", "company_stage": "growth"}
        )
    ]
    
    # Good Match Jobs (70-85 points expected)  
    good_jobs = [
        JobData(
            id="good_01",
            title="Product Manager - Growth",
            company="Shopify",
            location="Toronto, ON (Hybrid)",
            salary_range="$130,000 - $160,000 CAD",
            experience_required="4+ years product management",
            skills_mentioned=[
                "product strategy", "A/B testing", "analytics", 
                "growth metrics", "experimentation"
            ],
            industry="e-commerce",
            description="""
            Lead growth initiatives for Shopify's merchant platform. Focus on user acquisition, 
            activation, and retention through data-driven product improvements.
            
            You'll work on:
            - Growth product strategy and experimentation roadmap
            - A/B testing framework and conversion optimization  
            - User onboarding and activation flows
            - Analytics and metrics dashboard development
            - Cross-functional collaboration with marketing and sales
            
            Requirements:
            - 4+ years PM experience with growth focus
            - Strong analytical skills and experience with experimentation
            - Knowledge of e-commerce or marketplace products preferred
            - Experience with analytics tools and SQL nice to have
            
            Hybrid work model with 2-3 days in office. Competitive compensation and stock options.
            """,
            apply_url="https://shopify.com/careers/product-manager-growth",
            source="linkedin",
            posted_date=datetime.now() - timedelta(days=1)
        ),
        
        JobData(
            id="good_02",
            title="Senior Product Manager",
            company="Zendesk", 
            location="Remote (US/Canada)",
            salary_range="$150,000 - $190,000",
            experience_required="6+ years PM experience",
            skills_mentioned=[
                "product roadmap", "customer research", "agile",
                "stakeholder management", "B2B software"
            ],
            industry="saas",
            description="""
            Drive product vision and strategy for Zendesk's customer support platform.
            Work with enterprise clients to build scalable support solutions.
            
            Key responsibilities:
            - Define product roadmap for customer support tools
            - Conduct customer research and gather market insights
            - Lead agile development teams and sprint planning
            - Manage relationships with key enterprise stakeholders
            - Analyze product performance metrics and user feedback
            
            Ideal candidate has:
            - 6+ years of B2B software product management experience  
            - Experience with customer support or service products
            - Strong leadership and stakeholder management skills
            - Analytical mindset with data-driven decision making
            
            Remote-first company with excellent benefits and career development opportunities.
            """,
            apply_url="https://zendesk.com/jobs/senior-product-manager",
            source="rss_feed",
            posted_date=datetime.now() - timedelta(days=2)
        ),
        
        JobData(
            id="good_03",
            title="Principal Product Manager",
            company="Atlassian",
            location="Mountain View, CA",
            salary_range="$180,000 - $240,000",
            experience_required="8+ years product management",
            skills_mentioned=[
                "product leadership", "strategic planning", "team management",
                "enterprise software", "jira", "confluence"
            ],
            industry="software",
            description="""
            Lead product strategy for Atlassian's collaboration tools suite.
            Senior role with significant autonomy and leadership responsibilities.
            
            What you'll do:
            - Set long-term product vision and strategy
            - Lead team of product managers and designers
            - Partner with engineering leadership on technical roadmap
            - Engage with enterprise customers for product feedback
            - Drive go-to-market strategy for major product launches
            
            Requirements:
            - 8+ years product management experience
            - 3+ years leading product teams
            - Deep knowledge of enterprise software markets
            - Experience with Atlassian products (Jira, Confluence) preferred
            - Strong technical background and API product experience
            
            On-site role in Mountain View with hybrid flexibility. Significant equity component.
            """,
            apply_url="https://atlassian.com/company/careers/principal-pm",
            source="linkedin", 
            posted_date=datetime.now() - timedelta(days=3)
        )
    ]
    
    # Marginal Match Jobs (60-70 points expected)
    marginal_jobs = [
        JobData(
            id="marginal_01",
            title="Product Owner - Agile Teams",
            company="Capital One",
            location="McLean, VA",
            salary_range="$120,000 - $150,000", 
            experience_required="3-5 years",
            skills_mentioned=[
                "agile", "scrum", "user stories", "backlog management",
                "stakeholder coordination"
            ],
            industry="fintech",
            description="""
            Product Owner role supporting multiple agile development teams in our digital banking platform.
            Focus on requirements gathering and backlog prioritization.
            
            Responsibilities:
            - Manage product backlog and sprint planning
            - Write detailed user stories and acceptance criteria  
            - Coordinate with stakeholders across business units
            - Support scrum ceremonies and team retrospectives
            - Ensure delivery aligns with business objectives
            
            Requirements:
            - 3-5 years experience in product ownership or business analysis
            - Strong understanding of agile/scrum methodologies
            - Financial services experience preferred
            - Excellent communication and stakeholder management
            
            Hybrid work model, competitive benefits, career development programs.
            """,
            apply_url="https://capitalone.com/careers/product-owner",
            source="linkedin",
            posted_date=datetime.now() - timedelta(days=5)
        ),
        
        JobData(
            id="marginal_02",
            title="Product Manager - Mobile App",
            company="Robinhood",
            location="Menlo Park, CA", 
            salary_range="$135,000 - $170,000",
            experience_required="4+ years mobile product",
            skills_mentioned=[
                "mobile product management", "iOS", "Android",
                "user experience", "app store optimization"
            ],
            industry="fintech",
            description="""
            Drive product strategy for Robinhood's mobile trading application.
            Focus on user experience and engagement optimization.
            
            Key areas:
            - Mobile app product roadmap and feature development
            - iOS and Android platform optimization
            - App store presence and user acquisition
            - User experience research and testing
            - Performance monitoring and crash analysis
            
            Looking for:
            - 4+ years mobile product management experience
            - Deep understanding of iOS and Android ecosystems  
            - Experience with trading or financial apps preferred
            - Strong analytical skills and user research background
            - Knowledge of app store optimization and mobile analytics
            
            Office-based role with some remote flexibility. Stock options and competitive benefits.
            """,
            apply_url="https://robinhood.com/careers/mobile-pm", 
            source="rss_feed",
            posted_date=datetime.now() - timedelta(days=4)
        ),
        
        JobData(
            id="marginal_03",
            title="Technical Product Manager",
            company="Snowflake",
            location="San Mateo, CA (Remote options)",
            salary_range="$155,000 - $200,000",
            experience_required="5+ years technical PM", 
            skills_mentioned=[
                "API product management", "developer tools", "technical documentation",
                "SDK development", "enterprise APIs"
            ],
            industry="software",
            description="""
            Technical Product Manager for Snowflake's developer platform and APIs.
            Work closely with engineering teams on technical product decisions.
            
            Responsibilities:
            - Define technical product requirements for APIs and SDKs
            - Create technical documentation and developer resources
            - Gather feedback from developer community and enterprise customers  
            - Work with engineering on API design and architecture decisions
            - Support go-to-market for developer-facing products
            
            Ideal background:
            - 5+ years technical product management experience
            - Strong engineering background or CS degree preferred
            - Experience with API products and developer tools
            - Knowledge of data platforms and enterprise software
            - Excellent technical communication skills
            
            Flexible work arrangements, equity participation, comprehensive benefits.
            """,
            apply_url="https://snowflake.com/careers/technical-pm",
            source="linkedin",
            posted_date=datetime.now() - timedelta(days=6)
        )
    ]
    
    # Poor Match Jobs (30-45 points expected)
    poor_jobs = [
        JobData(
            id="poor_01", 
            title="Project Manager - IT Operations",
            company="Accenture",
            location="Multiple Locations",
            salary_range="$95,000 - $125,000",
            experience_required="5+ years project management",
            skills_mentioned=[
                "project management", "waterfall", "risk management",
                "vendor management", "budget planning"
            ],
            industry="consulting", 
            description="""
            Project Manager role supporting large-scale IT transformation initiatives.
            Focus on traditional project management methodologies and vendor coordination.
            
            Key responsibilities:
            - Manage complex IT projects from initiation to closure
            - Coordinate with multiple vendors and internal stakeholders
            - Develop project plans, timelines, and budget tracking
            - Risk identification and mitigation planning
            - Status reporting and executive communication
            
            Requirements:
            - 5+ years project management experience in IT environments
            - PMP certification preferred
            - Experience with waterfall project methodologies
            - Strong vendor management and procurement experience
            - Excellent Excel and PowerPoint skills
            
            Travel required 50-75%. Consulting environment with varied client engagements.
            """,
            apply_url="https://accenture.com/careers/project-manager-it",
            source="rss_feed",
            posted_date=datetime.now() - timedelta(days=7)
        ),
        
        JobData(
            id="poor_02",
            title="Marketing Manager - Product Marketing",
            company="Oracle",
            location="Redwood City, CA",
            salary_range="$110,000 - $140,000",
            experience_required="4+ years marketing",
            skills_mentioned=[
                "product marketing", "go-to-market", "demand generation",
                "content marketing", "campaign management"
            ],
            industry="enterprise software",
            description="""
            Product Marketing Manager focused on go-to-market strategy and demand generation
            for Oracle's enterprise database solutions.
            
            What you'll do:
            - Develop go-to-market strategies for new product releases
            - Create marketing content and sales enablement materials
            - Execute demand generation campaigns and lead nurturing
            - Support sales team with competitive positioning
            - Analyze campaign performance and ROI metrics
            
            Looking for:
            - 4+ years product marketing experience
            - B2B enterprise software marketing background
            - Strong content creation and copywriting skills
            - Experience with marketing automation platforms
            - Database or technical product knowledge helpful
            
            On-site position with standard marketing benefits and bonus structure.
            """,
            apply_url="https://oracle.com/careers/marketing-manager",
            source="linkedin", 
            posted_date=datetime.now() - timedelta(days=10)
        )
    ]
    
    # Very Poor/Penalized Jobs (0-30 points expected)
    penalized_jobs = [
        JobData(
            id="penalized_01",
            title="Sales Manager - Enterprise Accounts", 
            company="Salesforce",
            location="New York, NY",
            salary_range="$80,000 base + commission",
            experience_required="3+ years sales",
            skills_mentioned=[
                "enterprise sales", "CRM", "quota management",
                "account planning", "relationship building"  
            ],
            industry="software",
            description="""
            Enterprise Sales Manager responsible for new business development
            and account growth in the NYC market.
            
            Role focuses on:
            - Prospecting and qualifying new enterprise opportunities
            - Managing full sales cycle from lead to close
            - Developing relationships with C-level executives
            - Achieving quarterly and annual quota targets
            - Using Salesforce CRM for pipeline management
            
            Ideal candidate:
            - 3+ years enterprise B2B sales experience
            - Proven track record of quota achievement
            - Strong presentation and negotiation skills
            - Experience selling to Fortune 500 companies
            - Hunter mentality with consultative selling approach
            
            Competitive base salary plus uncapped commission. Great benefits and career growth.
            """,
            apply_url="https://salesforce.com/careers/sales-manager",
            source="rss_feed",
            posted_date=datetime.now() - timedelta(days=12)
        ),
        
        JobData(
            id="penalized_02",
            title="Product Manager",
            company="Philip Morris International",  # Avoided industry
            location="Richmond, VA",
            salary_range="$130,000 - $160,000",
            experience_required="5+ years PM experience", 
            skills_mentioned=[
                "product management", "consumer goods", "market research",
                "brand management", "regulatory compliance"
            ],
            industry="tobacco",  # Avoided industry
            description="""
            Product Manager for tobacco and alternative products portfolio.
            Drive innovation in traditional and reduced-risk products.
            
            Responsibilities:
            - Develop product strategies for tobacco product lines
            - Conduct consumer research and market analysis
            - Manage regulatory compliance and approval processes
            - Coordinate with R&D on product development initiatives
            - Support brand marketing and positioning strategies
            
            Requirements:
            - 5+ years product management experience
            - Consumer goods or CPG background preferred
            - Understanding of regulatory environments
            - Strong analytical and market research skills
            - MBA preferred but not required
            
            Excellent benefits, stable industry, growth opportunities in international markets.
            """,
            apply_url="https://pmi.com/careers/product-manager",
            source="linkedin",
            posted_date=datetime.now() - timedelta(days=8)
        ),
        
        JobData(
            id="penalized_03", 
            title="Senior Product Manager",
            company="Robert Half Recruiting",  # Third-party recruiter penalty
            location="Various",
            salary_range="Competitive based on experience",  # Vague salary
            experience_required="7+ years", 
            skills_mentioned=[
                "product management", "leadership", "strategy"
            ],
            industry="technology",
            description="""
            Recruiting for Senior Product Manager role with leading technology company.
            Excellent opportunity for experienced PM professional.
            
            Role includes:
            - Strategic product planning and roadmap development
            - Leading cross-functional teams  
            - Market analysis and competitive research
            - Customer engagement and feedback collection
            - Product launch and go-to-market execution
            
            Seeking:
            - 7+ years product management experience
            - Technology product background required
            - Strong leadership and communication skills
            - Track record of successful product launches
            
            Competitive salary and benefits package. Great company culture and growth potential.
            Contact us for more details about this exciting opportunity.
            """,
            apply_url="https://roberthalf.com/job-posting/senior-pm",
            source="rss_feed",
            posted_date=datetime.now() - timedelta(days=20)  # Old posting
        )
    ]
    
    # Edge Case Jobs (testing unusual scenarios)
    edge_case_jobs = [
        JobData(
            id="edge_01",
            title="",  # Empty title
            company="Unknown Company",
            location="",
            salary_range=None,
            experience_required=None,
            skills_mentioned=[],
            industry=None,
            description="Minimal job description with no details provided.",
            apply_url="",
            source="unknown",
            posted_date=None
        ),
        
        JobData(
            id="edge_02", 
            title="URGENT: Product Manager Needed ASAP!!!",
            company="StartupXYZ",
            location="Remote/Anywhere", 
            salary_range="$50k-$200k depending on experience",  # Wide range
            experience_required="0-10 years welcome",
            skills_mentioned=[
                "everything", "all skills", "full stack", "ninja", "rockstar"
            ],
            industry="startup",
            description="""
            AMAZING OPPORTUNITY!!! Join our revolutionary startup that's disrupting everything!
            We need a product manager ninja rockstar who can do everything!
            
            You'll be responsible for:
            - All product decisions
            - Everything related to products  
            - Making our startup successful
            - Working 24/7 with unlimited passion
            - Changing the world with our amazing product
            
            Requirements:
            - Must be a rockstar ninja
            - Should know everything about products
            - Unlimited energy and passion required
            - Equity-only compensation initially but huge upside potential!!!
            
            This is the opportunity of a lifetime! Apply now!!!
            """,
            apply_url="https://startupxyz.com/jobs",
            source="startup_board",
            posted_date=datetime.now() - timedelta(hours=1)
        ),
        
        JobData(
            id="edge_03",
            title="Principal Product Manager - AI/ML Platform", 
            company="Google",
            location="Mountain View, CA",
            salary_range="$200,000 - $350,000 + equity",
            experience_required="10+ years PM, 5+ years AI/ML products",
            skills_mentioned=[
                "AI/ML product management", "machine learning", "data science",
                "technical product leadership", "platform products", "API design"
            ],
            industry="technology",
            description="""
            Lead product strategy for Google's AI/ML platform serving millions of developers.
            This is a highly technical role requiring deep ML product expertise.
            
            Key responsibilities:
            - Define product vision for next-generation AI/ML platform
            - Work with world-class ML researchers and engineers
            - Drive technical product decisions for platform architecture  
            - Engage with external developer community and enterprise customers
            - Lead product strategy for developer tools and APIs
            
            Qualifications:
            - 10+ years product management experience in technical domains
            - 5+ years specifically with AI/ML or data science products
            - Computer Science or related technical degree required
            - Deep understanding of machine learning algorithms and frameworks
            - Experience with platform products and developer ecosystems
            - Track record of shipping successful technical products at scale
            
            Exceptional compensation package with significant equity upside. 
            Work with the best minds in AI/ML. On-site in Mountain View.
            """,
            apply_url="https://google.com/careers/principal-pm-ai-ml", 
            source="linkedin",
            posted_date=datetime.now() - timedelta(hours=6)
        )
    ]
    
    # Combine all test jobs
    all_jobs = (
        perfect_jobs + good_jobs + marginal_jobs + 
        poor_jobs + penalized_jobs + edge_case_jobs
    )
    
    return all_jobs


def get_jobs_by_category():
    """Get jobs organized by expected score categories."""
    jobs = create_test_jobs()
    
    return {
        "perfect_match": [job for job in jobs if job.id.startswith("perfect_")],
        "good_match": [job for job in jobs if job.id.startswith("good_")], 
        "marginal_match": [job for job in jobs if job.id.startswith("marginal_")],
        "poor_match": [job for job in jobs if job.id.startswith("poor_")],
        "penalized": [job for job in jobs if job.id.startswith("penalized_")],
        "edge_cases": [job for job in jobs if job.id.startswith("edge_")]
    }


def get_expected_score_ranges():
    """Get expected score ranges for each job category."""
    return {
        "perfect_match": (90, 120),    # 90-100+ with bonuses
        "good_match": (70, 89),        # 70-89 points
        "marginal_match": (60, 69),    # 60-69 points  
        "poor_match": (30, 59),        # 30-59 points
        "penalized": (0, 29),          # 0-29 points with penalties
        "edge_cases": (0, 100)         # Wide range for edge cases
    }