```mermaid
sequenceDiagram
    autonumber
    actor User as MealShopper Client (Mobile/Web)
    participant GW as API Gateway (Nginx/Envoy)
    participant Orch as Orchestrator Service (Go/Temporal)
    participant StoreSvc as Store Discovery Service (Go/Python)
    participant DB_Loc as Locations DB (PostgreSQL+PostGIS)
    participant MapSvc as External Mapping Service (Google Maps)
    participant IngestSvc as Store Ad Ingestion Service (C#/.NET)
    participant DB_Deals as Deals RDBMS (MongoDB/Doc Store)
    participant DealFinder as Store Deal Finder Service (Python/Instructor)
    participant Cache_Deal as Deal Finder Cache (Pinecone)
    participant LLM_Eval as Deal Evaluation LLM
    participant PlanSvc as Planning Domain Service (Python/LangChain)
    participant Cache_Plan as Planner Cache (Redis)
    participant LLM_Plan as Meal Plan Generation LLM

    %% Phase 1: Dynamic Intake & Asynchronous Handoff
    Note over User, Orch: Phase 1: Dynamic Intake & Async Handoff
    User->>GW: POST /v1/meal-plans (Includes Preferences, Allergies, Proximity Overrides)
    activate GW
    GW->>Orch: Forward Request with Full Runtime Context Payload
    deactivate GW
    activate Orch
    Orch->>Orch: Initialize Stateful Workflow Instance
    Orch-->>User: Return 202 Accepted (Job_ID for UI Polling/WebSockets)
    Note over User: Frontend enters loading state,<br/>polling for Job_ID status

    %% Phase 2: Geospatial Store Discovery
    Note over Orch, MapSvc: Phase 2: Geospatial Store Discovery
    Orch->>StoreSvc: Find Local Stores (Coordinates, Radius Preference)
    activate StoreSvc
    StoreSvc->>DB_Loc: Geospatial Query (PostGIS Bounding Circle)
    activate DB_Loc
    
    alt Store Cache Hit
        DB_Loc-->>StoreSvc: Return Store List (Store_IDs)
    else Store Cache Miss (Cold Start Region)
        DB_Loc-->>StoreSvc: Empty Array
        deactivate DB_Loc
        StoreSvc->>MapSvc: Fetch Regional Store Locations (Google Maps)
        activate MapSvc
        MapSvc-->>StoreSvc: Return Local Retail Metadata
        deactivate MapSvc
        StoreSvc->>DB_Loc: Write Fresh Regional Store Coordinates
    end
    StoreSvc-->>Orch: Return Verified Store_IDs Array
    deactivate StoreSvc

    %% Phase 3: Cold Start On-Demand Deal Ingestion
    Note over Orch, DB_Deals: Phase 3: Synchronous/Asynchronous Deal Ingestion
    Orch->>IngestSvc: Ensure Fresh Deal Cache (Store_IDs)
    activate IngestSvc
    IngestSvc->>DB_Deals: Query Active Deals Valid for Today
    activate DB_Deals
    
    alt Current Deals Exist
        DB_Deals-->>IngestSvc: Active Deals Found
    else Cold Start / Deals Expired (Normal Early-Stage Behavior)
        DB_Deals-->>IngestSvc: Zero Active Records
        deactivate DB_Deals
        IngestSvc->>IngestSvc: Scrape Local Store Flyers/Circulars (Out-of-band Target)
        IngestSvc->>DB_Deals: Parse, Normalize, and Write Fresh Deal Items
    end
    IngestSvc-->>Orch: Ingestion Synced Successfully
    deactivate IngestSvc

    %% Phase 4: Deal Curation & Scoring
    Note over Orch, LLM_Eval: Phase 4: Deal Curation & Scoring
    Orch->>DealFinder: Fetch Ranked Deals (Store_IDs, Runtime Context)
    activate DealFinder
    DealFinder->>IngestSvc: Request Internal Raw Deals Dataset (Read-Only)
    activate IngestSvc
    IngestSvc->>DB_Deals: Read Transformed Line Items
    activate DB_Deals
    DB_Deals-->>IngestSvc: Raw Inventory List
    deactivate DB_Deals
    IngestSvc-->>DealFinder: Return Items Stream
    deactivate IngestSvc
    
    DealFinder->>Cache_Deal: Check Vector Similarity Cache (Pinecone)
    activate Cache_Deal
    alt Score Cache Hit
        Cache_Deal-->>DealFinder: Return Pre-Evaluated Scores
    else Score Cache Miss
        Cache_Deal-->>DealFinder: Entry Missing
        deactivate Cache_Deal
        DealFinder->>LLM_Eval: Evaluate Values vs Runtime Preferences
        activate LLM_Eval
        LLM_Eval-->>DealFinder: Return Evaluated Deals JSON Schema
        deactivate LLM_Eval
        DealFinder->>Cache_Deal: Save Evaluated Vectors to Matrix
    end
    DealFinder-->>Orch: Return TopDeals JSON Payload
    deactivate DealFinder

    %% Phase 5: Menu Generation & Validation
    Note over Orch, LLM_Plan: Phase 5: Menu Generation & Validation
    Orch->>PlanSvc: Generate Optimized Menu (TopDeals, Runtime Context)
    activate PlanSvc
    PlanSvc->>PlanSvc: Filter Out Active Allergies Deterministically
    PlanSvc->>Cache_Plan: Check Request Hash Match (Redis Cache)
    activate Cache_Plan
    
    alt Plan Cache Hit
        Cache_Plan-->>PlanSvc: Return Cached MealPlanDraft
    else Plan Cache Miss
        Cache_Plan-->>PlanSvc: Entry Missing
        deactivate Cache_Plan
        PlanSvc->>LLM_Plan: Construct Menu Recipes centered around TopDeals
        activate LLM_Plan
        LLM_Plan-->>PlanSvc: Return MealPlanDraft JSON + Missing_Primary_Ingredients Array
        deactivate LLM_Plan
        PlanSvc->>Cache_Plan: Cache Generated Menu Payload Segment (Redis)
    end
    PlanSvc-->>Orch: Return Menu + Missing Ingredients Array
    deactivate PlanSvc

    %% Phase 6: The Loop-Back Phase
    Note over Orch, DB_Deals: Phase 6: The Loop-Back Phase
    Orch->>DealFinder: Find Match for Missing Ingredients (Ingredients, Store_IDs)
    activate DealFinder
    DealFinder->>IngestSvc: Query Ingredients (Fuzzy Match / Keyword Search)
    activate IngestSvc
    IngestSvc->>DB_Deals: Scan Current Active Database Records
    activate DB_Deals
    DB_Deals-->>IngestSvc: Return Secondary Product Matches & Alternative Prices
    deactivate DB_Deals
    IngestSvc-->>DealFinder: Return Aggregated Staple Deals JSON
    deactivate IngestSvc
    DealFinder-->>Orch: Return Enriched Staple Matches
    deactivate DealFinder

    %% Phase 7: Final Delivery
    Note over Orch, User: Phase 7: Final Processing
    Orch->>Orch: Compile Finalized Menu & Optimization Routing Layout
    Orch->>Orch: Update Job Status to "Completed" in Shared State
    Note over User, Orch: Client Polling/WebSocket detects "Completed" status and renders dashboard