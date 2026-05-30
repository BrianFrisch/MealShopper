```mermaid
graph TB
    %% Styling and Definitions
    classDef boundary fill:none,stroke:#777,stroke-width:2px,stroke-dasharray: 5 5;
    classDef external fill:#999,stroke:#666,color:#fff,font-weight:bold;
    classDef container fill:#438dd5,stroke:#3b7aa3,color:#fff;
    classDef database fill:#1168bd,stroke:#0b4e8f,color:#fff;
    classDef llm fill:#7b42bc,stroke:#5c2d91,color:#fff;

    %% Elements
    User((User)):::external
    
    subgraph Boundary_System [MealShopper System]
        UI["MealShopper UI<br>(Web/Mobile)"]:::container
        APIGateway["API Gateway"]:::container
        Orchestrator["Orchestrator Service<br>(State Machine/Workflow Manager)"]:::container

        %% Shopping Subgraph
        subgraph Boundary_Shopping [Shopping]
            StoreDiscovery["Store Discovery Service"]:::container
            ShopperDomain["Shopper Domain Service"]:::container
            LocationsDB[("Locations RDBMS")]:::database
            StoreAdIngestion["Store Ad Ingestion Service"]:::container
            StoreDealFinder["Store Deal Finder Service"]:::container
            FlyersStore[("Flyers Document Store")]:::database
            DealsStore[("Deals Document Store")]:::database
            DealFinderCache[("Deal Finder Cache<br>Pinecone")]:::database
            DealEvalLLM[["Deal Evaluation LLM"]]:::llm
        end

        %% Planning Subgraph
        subgraph Boundary_Planning [Planning]
            MealPlanning["Meal Planning Service"]:::container
            PlanningDomain["Planning Domain Service"]:::container
            DietaryValidation["Dietary Validation Service"]:::container
            PlannerCache[("Planner Cache<br>Redis")]:::database
            MealPlanLLM[["Meal Plan Generation LLM"]]:::llm
        end

        %% Utility Subgraph
        subgraph Boundary_Utility [Utility]
            UserService["User Service"]:::container
            SecurityService["Security Service"]:::container
            PIIEncryption["PII Encryption Service"]:::container
            UsersDB[("Users RDBMS")]:::database
            KMS["KMS<br>(OAuth2)"]:::external
            IdentityProvider["Identity Provider<br>(OAuth2)"]:::external
        end
    end

    %% External Services
    MappingService["Mapping Service<br>(Google Maps)"]:::external

    %% Relationships and Flows
    User --> UI
    UI --> APIGateway
    APIGateway --> Orchestrator

    %% Shopping Flows
    %%Orchestrator --> StoreDiscovery
    Orchestrator --> ShopperDomain
    ShopperDomain --> StoreDiscovery
    StoreDiscovery --> LocationsDB
    StoreDiscovery -- "If empty areas need searching" --> MappingService
    %%MappingService -- "Finds stores & stores them" --> LocationsDB
    ShopperDomain --> StoreAdIngestion
    StoreAdIngestion -- "Stores flyers locally & parses" --> FlyersStore
    %%StoreAdIngestion -- "Writes deals" --> StoreDealFinder
    ShopperDomain --> StoreDealFinder
    StoreDealFinder --> DealsStore
    StoreDealFinder --> DealFinderCache
    StoreDealFinder --> DealEvalLLM
    
    %% Planning Flows
    Orchestrator --> PlanningDomain
    PlanningDomain --> DietaryValidation
    PlanningDomain --> MealPlanning
    DietaryValidation -- "Retrieve User's Dietary Info" --> UserService
    MealPlanning --> PlannerCache
    MealPlanning --> MealPlanLLM
    %%DealEvalLLM -- "Assesses & identifies best deals" --> StoreDealFinder
    

    %% Utility Flows
    Orchestrator --> UserService
    UserService --> UsersDB
    
    UserService --> SecurityService
    SecurityService --> PIIEncryption
    PIIEncryption --> KMS
    SecurityService --> IdentityProvider