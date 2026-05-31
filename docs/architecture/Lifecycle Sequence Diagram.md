sequence diagram
    autonumber
    actor User as MealShopper Client (Mobile/Web)
    participant GW as API Gateway (Nginx/Envoy)
    participant IdP as Identity Provider (OAuth2/JWT)
    participant Orch as Orchestrator Service (Go/Temporal)
    participant UserSvc as User Service (C#/.NET)
    participant DB_User as Users RDBMS (PostgreSQL)
    participant StoreSvc as Store Discovery Service (Go/Python)
    participant DB_Loc as Locations DB (PostgreSQL+PostGIS)
    participant MapSvc as External Mapping Service (Google Maps)
    participant DealFinder as Store Deal Finder Service (Python/Instructor)
    participant Cache_Deal as Deal Finder Cache (Pinecone)
    participant LLM_Eval as Deal Evaluation LLM
    participant DB_Deals as Deals RDBMS (MongoDB/Doc Store)
    participant PlanSvc as Planning Domain Service (Python/LangChain)
    participant Cache_Plan as Planner Cache (Redis)
    participant LLM_Plan as Meal Plan Generation LLM

    %% Phase 1: Authentication & Initialization
    Note over User, Orch: Phase 1: Authentication & Initialization
    User->>GW: POST /v1/meal-plans (Proximity, Size, Meal Prefs)
    activate GW
    GW->>IdP: Validate Security Token (mTLS)
    activate IdP
    IdP-->>GW: Token Validated (Return JWT Claims)
    deactivate IdP
    GW->>Orch: Forward Request with JWT Claims (Async 202 Accepted Initialized)
    deactivate GW
    activate Orch
    Orch->>Orch: Initiate State Machine Execution Instance
    
    %% Phase 2: User Profile Enrichment
    Note over Orch, DB_User: Phase 2: User Profile Enrichment
    Orch->>UserSvc: Get Long-Term User Profile (Allergies, Exclusions)
    activate UserSvc
    UserSvc->>DB_User: Query User Profile by ID
    activate DB_User
    DB_User-->>UserSvc: Return Profile Data (PII Decrypted)
    deactivate DB_User
    UserSvc-->>Orch: Return Ingredient Restrictions & Preferences
    deactivate UserSvc

    %% Phase 3: Store Discovery (Geospatial)
    Note over Orch, MapSvc: Phase 3: Store Discovery Engine
    Orch->>StoreSvc: Find Local Stores (Coordinates, Proximity Prefs)
    activate StoreSvc
    StoreSvc->>DB_Loc: Geospatial Query (PostGIS Bounding Radius)
    activate DB_Loc
    
    alt Data Available
        DB_Loc-->>StoreSvc: Return Store List (Store_IDs)
    else Data Not Available (Cold Start Region)
        DB_Loc-->>StoreSvc: Empty Result Set
        deactivate DB_Loc
        StoreSvc->>MapSvc: Synchronous Geocode/Radius Lookup (Google Maps)
        activate MapSvc
        MapSvc-->>StoreSvc: Return Local Retail Metadata
        deactivate MapSvc
        StoreSvc->>DB_Loc: Persist Store Locations (Out-of-band Ingestion Sync Triggered)
    end
    StoreSvc-->>Orch: Return Clean Store_IDs Array
    deactivate StoreSvc

    %% Phase 4: Deal Fetching & Semantic Evaluation
    Note over Orch, DB_Deals: Phase 4: Local Deal Curation & Scoring
    Orch->>DealFinder: Process Scored Deals (Store_IDs, User Preferences)
    activate DealFinder
    DealFinder->>DB_Deals: Fetch Passive Active Deals for Store_IDs
    activate DB_Deals
    DB_Deals-->>DealFinder: Return Raw Normalized Items List
    deactivate DB_Deals
    
    DealFinder->>Cache_Deal: Check Embeddings Matrix (Pinecone)
    activate Cache_Deal
    alt Cache Hit
        Cache_Deal-->>DealFinder: Return Pre-Scored Deals
    else Cache Miss
        Cache_Deal-->>DealFinder: Entry Missing
        deactivate Cache_Deal
        DealFinder->>LLM_Eval: Call Fast LLM (Evaluate Value Density/Match Prefs)
        activate LLM_Eval
        LLM_Eval-->>DealFinder: Return Scored Deals JSON Schema
        deactivate LLM_Eval
        DealFinder->>Cache_Deal: Write Embeddings Cache Matrix
    end
    DealFinder-->>Orch: Return TopDeals JSON Payload
    deactivate DealFinder

    %% Phase 5: Menu Generation & Validation
    Note over Orch, LLM_Plan: Phase 5: Menu Generation & Validation
    Orch->>PlanSvc: Generate Optimized Menu (TopDeals, Meal Prefs, Allergies)
    activate PlanSvc
    PlanSvc->>PlanSvc: Execute Deterministic Allergy/Dietary Validation
    PlanSvc->>Cache_Plan: Check Exact-Match Query String (Redis Cache)
    activate Cache_Plan
    
    alt Cache Hit
        Cache_Plan-->>PlanSvc: Return MealPlanDraft
    else Cache Miss
        Cache_Plan-->>PlanSvc: Entry Missing
        deactivate Cache_Plan
        PlanSvc->>LLM_Plan: Call Advanced LLM (Construct Menu Recipes around Deals)
        activate LLM_Plan
        LLM_Plan-->>PlanSvc: Return MealPlanDraft JSON + Missing_Primary_Ingredients
        deactivate LLM_Plan
        PlanSvc->>Cache_Plan: Cache Final Output Segment (Redis)
    end
    PlanSvc-->>Orch: Return Menu + Missing Ingredients Array
    deactivate PlanSvc

    %% Phase 6: The Loop-Back Phase
    Note over Orch, DealFinder: Phase 6: The Loop-Back Phase (Fuzzy Matching Staples)
    Orch->>DealFinder: Find Deals on Missing Ingredients (Ingredients Array, Store_IDs)
    activate DealFinder
    DealFinder->>DB_Deals: Keyword/Fuzzy Query Missing Staples against Store Inventory
    activate DB_Deals
    DB_Deals-->>DealFinder: Return Secondary Product Matches & Pricing
    deactivate DB_Deals
    DealFinder-->>Orch: Return Aggregated Staple Deals JSON
    deactivate DealFinder

    %% Phase 7: Finalization
    Note over Orch, User: Phase 7: State Consolidation & Client Delivery
    Orch->>Orch: Compile Final Menu & Optimization Layout
    Orch->>UserSvc: Save Completed Transaction State
    Orch-->>User: Push Complete Meal Plan and Split Shopping List via Webhook/Polling
    deactivate Orch